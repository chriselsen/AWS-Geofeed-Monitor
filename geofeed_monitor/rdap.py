"""RFC 9092 geofeed discovery via geolocatemuch.com validated CSV + ARIN bulk whois fallback + RDAP cache for URLs."""

import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
import ipaddress

import pytricia

VALIDATED_CSV_URL = "https://geolocatemuch.com/geofeeds/validated-all.csv"
VALIDATED_CSV_FILE = Path("./data/whois/validated-all.csv")
ARIN_BULK_WHOIS_FILE = Path("./data/whois/arin_nets.txt")
RDAP_CACHE_FILE = Path("./data/rdap_cache.json")
CACHE_TTL = 86400  # 24 hours
REQUEST_DELAY = 0.1

_trie4 = None
_trie6 = None
_arin_trie4 = None
_arin_trie6 = None
_rdap_cache = None
_last_request = 0

_GEOFEED_RE = re.compile(r'[Gg]eofeed:?\s+(https?://\S+)', re.IGNORECASE)


def _load_rdap_cache():
    global _rdap_cache
    if _rdap_cache is not None:
        return
    if RDAP_CACHE_FILE.exists():
        try:
            _rdap_cache = json.loads(RDAP_CACHE_FILE.read_text())
        except Exception:
            _rdap_cache = {}
    else:
        _rdap_cache = {}


def _save_rdap_cache():
    RDAP_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RDAP_CACHE_FILE.write_text(json.dumps(_rdap_cache))


def _fetch_validated_csv():
    VALIDATED_CSV_FILE.parent.mkdir(parents=True, exist_ok=True)
    if VALIDATED_CSV_FILE.exists() and (time.time() - VALIDATED_CSV_FILE.stat().st_mtime) < CACHE_TTL:
        return
    print("downloading...", flush=True)
    subprocess.run(
        ["curl", "-sS", "-L", "--progress-bar", "-o", str(VALIDATED_CSV_FILE), VALIDATED_CSV_URL],
        check=True,
    )


def _fetch_arin_bulk_whois():
    """Download ARIN bulk whois nets file if ARIN_API_KEY is set and cache is stale."""
    api_key = os.environ.get("ARIN_API_KEY")
    if not api_key:
        return False
    ARIN_BULK_WHOIS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if ARIN_BULK_WHOIS_FILE.exists() and (time.time() - ARIN_BULK_WHOIS_FILE.stat().st_mtime) < CACHE_TTL:
        return True
    print("downloading ARIN bulk whois...", flush=True)
    url = f"https://accountws.arin.net/public/rest/downloads/bulkwhois/nets.txt?apikey={api_key}"
    try:
        subprocess.run(
            ["curl", "-sS", "-L", "--progress-bar", "-o", str(ARIN_BULK_WHOIS_FILE), url],
            check=True,
            timeout=300,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"  ARIN bulk whois download failed: {e}")
        return False


def _parse_arin_bulk_whois():
    """Parse ARIN bulk whois nets file, extract records with geofeed comments.

    Returns a list of (cidr_prefix, geofeed_url) tuples.
    """
    if not ARIN_BULK_WHOIS_FILE.exists():
        return []

    results = []
    current_range = None
    current_geofeed = None

    with open(ARIN_BULK_WHOIS_FILE, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")

            # Blank line = end of record
            if not line.strip():
                if current_range and current_geofeed:
                    try:
                        parts = current_range.split(" - ")
                        start = ipaddress.ip_address(parts[0].strip())
                        end = ipaddress.ip_address(parts[1].strip())
                        for net in ipaddress.summarize_address_range(start, end):
                            results.append((str(net), current_geofeed))
                    except (ValueError, IndexError):
                        pass
                current_range = None
                current_geofeed = None
                continue

            if line.startswith("NetRange:"):
                current_range = line.split(":", 1)[1].strip()
            elif line.startswith("Comment:"):
                comment = line.split(":", 1)[1].strip()
                m = _GEOFEED_RE.search(comment)
                if m:
                    current_geofeed = m.group(1).rstrip(".")

    # Handle last record if file doesn't end with blank line
    if current_range and current_geofeed:
        try:
            parts = current_range.split(" - ")
            start = ipaddress.ip_address(parts[0].strip())
            end = ipaddress.ip_address(parts[1].strip())
            for net in ipaddress.summarize_address_range(start, end):
                results.append((str(net), current_geofeed))
        except (ValueError, IndexError):
            pass

    return results


def _load_arin_bulk_whois():
    """Load ARIN bulk whois data into separate tries."""
    global _arin_trie4, _arin_trie6
    if _arin_trie4 is not None:
        return

    _arin_trie4 = pytricia.PyTricia(32)
    _arin_trie6 = pytricia.PyTricia(128)

    if not _fetch_arin_bulk_whois():
        return

    print("Loading ARIN bulk whois geofeed data...", end=" ", flush=True)
    entries = _parse_arin_bulk_whois()
    count = 0
    for prefix, url in entries:
        try:
            net = ipaddress.ip_network(prefix, strict=False)
            trie = _arin_trie6 if net.version == 6 else _arin_trie4
            trie[str(net)] = url
            count += 1
        except ValueError:
            pass
    print(f"{count:,} prefixes with geofeed in ARIN whois")


def load_whois_geofeed_db():
    global _trie4, _trie6
    if _trie4 is not None:
        return
    _trie4 = pytricia.PyTricia(32)
    _trie6 = pytricia.PyTricia(128)
    _load_rdap_cache()

    cached = VALIDATED_CSV_FILE.exists() and (time.time() - VALIDATED_CSV_FILE.stat().st_mtime) < CACHE_TTL
    print(f"Loading RFC 9092 validated prefix list ({'cached' if cached else 'downloading'})...", end=" ", flush=True)
    _fetch_validated_csv()

    count = 0
    with open(VALIDATED_CSV_FILE, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            prefix = line.split(",")[0].strip()
            try:
                net = ipaddress.ip_network(prefix, strict=False)
                trie = _trie6 if net.version == 6 else _trie4
                trie[str(net)] = True  # normalize to compressed form
                count += 1
            except ValueError:
                pass
    print(f"{count:,} prefixes with RFC 9092 geofeed data")

    # Load ARIN bulk whois as fallback
    _load_arin_bulk_whois()


def _query_rdap(prefix):
    """Query RDAP for the geofeed URL, trying the prefix and its covering supernet."""
    global _last_request

    for query_prefix in _candidates(prefix):
        wait = REQUEST_DELAY - (time.time() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.time()

        for base_url in [
            f"https://rdap.arin.net/registry/ip/{query_prefix}",
            f"https://rdap.db.ripe.net/ip/{query_prefix}",
        ]:
            try:
                data = json.loads(urlopen(base_url, timeout=10).read())
                for link in data.get("links", []):
                    if link.get("rel") == "geofeed":
                        return link["href"]
                for remark in data.get("remarks", []):
                    for line in remark.get("description", []):
                        m = _GEOFEED_RE.search(line)
                        if m:
                            return m.group(1).rstrip(".")
                break  # queried successfully, no geofeed — try supernet
            except (URLError, Exception):
                continue
    return None


def _candidates(prefix):
    """Yield the prefix and progressively shorter covering supernets to try."""
    yield prefix
    try:
        net = ipaddress.ip_network(prefix, strict=False)
        while net.prefixlen > 0:
            net = net.supernet()
            yield str(net)
            if net.prefixlen <= (8 if net.version == 4 else 32):
                break
    except Exception:
        pass


def lookup_rdap(prefix, is_v6):
    """
    Look up RFC 9092 geofeed URL for a prefix.
    1. Check validated-all.csv trie — if present, use RDAP cache/query for URL.
    2. If not in validated list, check ARIN bulk whois trie as fallback.
    3. If found in ARIN bulk whois, return the URL directly (no RDAP query needed).
    Returns (geofeed_url, None) or (None, None).
    """
    load_whois_geofeed_db()
    trie = _trie6 if is_v6 else _trie4
    # Normalize prefix to compressed form
    try:
        norm_prefix = str(ipaddress.ip_network(prefix, strict=False))
    except ValueError:
        return (None, None)
    host = norm_prefix.split("/")[0]

    # Check validated-all.csv trie first
    in_validated = False
    if trie.has_key(norm_prefix):
        in_validated = True
    else:
        try:
            key = trie.get_key(host)
            if key:
                in_validated = True
        except Exception:
            pass

    if in_validated:
        # Present in validated list — get URL from cache or RDAP
        _load_rdap_cache()
        if norm_prefix in _rdap_cache:
            return (_rdap_cache[norm_prefix][0], None)

        geofeed_url = _query_rdap(norm_prefix)
        _rdap_cache[norm_prefix] = [geofeed_url, None]
        _save_rdap_cache()
        return (geofeed_url, None)

    # Fallback: check ARIN bulk whois trie
    arin_trie = _arin_trie6 if is_v6 else _arin_trie4
    if arin_trie is not None:
        # Try exact match first, then longest-prefix-match on host
        if arin_trie.has_key(norm_prefix):
            return (arin_trie[norm_prefix], None)
        try:
            key = arin_trie.get_key(host)
            if key:
                return (arin_trie[key], None)
        except Exception:
            pass

    return (None, None)
