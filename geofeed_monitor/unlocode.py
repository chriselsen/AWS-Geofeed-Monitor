"""Geofeed location validation using GeoNames cities1000.

Checks that the city name in a geofeed entry is recognised as a real place
in the claimed country. Flags:
  - City not found anywhere in GeoNames
  - City found in GeoNames but not in the claimed country
"""

import functools

import geofeed_monitor.geonames as _gn


def _all_countries_for_city(norm_city):
    """Return set of country codes where this normalised city name is known."""
    _gn._load_geonames()
    return {c for (c, n) in _gn._lookup if n == norm_city}


@functools.lru_cache(maxsize=None)
def validate_locode(gf_country, gf_subdiv, gf_city):
    """
    Validate a geofeed city/country pair against GeoNames.
    Returns a tuple of issue strings, empty if all OK or city is blank.
    """
    if not gf_city:
        return ()

    _gn._load_geonames()
    norm_city = _gn._norm(gf_city)

    # Check if this city is known in the claimed country
    if _gn._lookup.get((gf_country, norm_city)) is not None:
        return ()

    # Not found in the claimed country — check if it exists elsewhere
    known_in = {c for (c, n) in _gn._lookup if n == norm_city}
    if known_in:
        known_str = ", ".join(sorted(known_in))
        return (f'Unrecognized city name "{gf_city}" in {gf_country} (known in: {known_str})',)

    return (f'Unrecognized city name "{gf_city}"',)
