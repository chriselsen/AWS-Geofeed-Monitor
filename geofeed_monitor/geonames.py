"""City name normalization using GeoNames cities1000 dataset.

Used to normalize city names before comparing geofeed claims against
geolocation provider results, and for location name validation.

Maps alternate/local names to a canonical English name per country, so that
e.g. 'Al Manamah' and 'Manama' both normalize to 'manama' for BH,
and 'Tel Aviv-Yafo' and 'Tel Aviv' both normalize to 'tel aviv' for IL.
"""

import re
import subprocess
import time
import unicodedata
import zipfile
from pathlib import Path

GEONAMES_URL = "https://download.geonames.org/export/dump/cities1000.zip"
GEONAMES_FILE = Path("./data/geonames/cities1000.zip")
CACHE_TTL = 86400 * 30  # refresh monthly

_lookup = None  # (country_code, norm_name) -> norm_canonical


def _norm(s):
    """Normalize a city name: strip parentheticals, diacritics, lowercase."""
    s = re.sub(r'\s*\(.*?\)', '', s)
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().strip().lower()


# Manual overrides for well-known cases not covered by GeoNames alternate names.
# Format: (country_code, norm_name) -> norm_canonical
_MANUAL_OVERRIDES = {
    ("GB", "city of london"): "london",
}


def _load_geonames():
    global _lookup
    if _lookup is not None:
        return

    GEONAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not GEONAMES_FILE.exists() or (time.time() - GEONAMES_FILE.stat().st_mtime) > CACHE_TTL:
        print("Downloading GeoNames cities1000...", flush=True)
        subprocess.run(
            ["curl", "-sS", "-L", "--progress-bar", "-o", str(GEONAMES_FILE), GEONAMES_URL],
            check=True,
        )

    _lookup = {**_MANUAL_OVERRIDES}
    with zipfile.ZipFile(GEONAMES_FILE) as zf:
        with zf.open("cities1000.txt") as f:
            for line in f:
                cols = line.decode("utf-8", errors="replace").rstrip("\n").split("\t")
                if len(cols) < 9:
                    continue
                country = cols[8].strip()
                canonical = cols[1].strip()
                alternates = cols[3].strip().split(",")
                norm_canonical = _norm(canonical)
                for alt in [canonical] + alternates:
                    alt = alt.strip()
                    if alt:
                        key = (country, _norm(alt))
                        # Prefer shorter canonical (more general) on conflict
                        if key not in _lookup or len(norm_canonical) < len(_lookup[key]):
                            _lookup[key] = norm_canonical


def normalize_city(country, city):
    """
    Return the normalized canonical city name for comparison purposes.
    Falls back to the standard _norm() result if not found in GeoNames.
    """
    _load_geonames()
    norm_city = _norm(city)
    return _lookup.get((country, norm_city), norm_city)
