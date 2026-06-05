#!/usr/bin/env python3
"""Validate location names for all configured feeds without loading geoip databases."""

from geofeed_monitor.config import FEEDS
from geofeed_monitor.geofeed import load_geofeed, group_by_location
import geofeed_monitor.geonames as _gn
from geofeed_monitor.unlocode import validate_locode


def main():
    _gn._load_geonames()
    print(f"GeoNames: {len(_gn._lookup)} entries loaded\n")

    total_issues = 0

    for feed in FEEDS:
        print(f"=== {feed['title']} ===")
        try:
            geofeed = load_geofeed(feed["url"], feed.get("geofeed_format", "rfc8805"))
        except Exception as e:
            print(f"  Feed unreachable: {e}\n")
            continue

        feed_issues = 0
        seen = set()

        for _country_code, _display, prefixes in group_by_location(geofeed):
            _, gf_country, gf_subdiv, gf_city = prefixes[0]
            loc_key = (gf_country, gf_subdiv, gf_city)
            if not gf_city or loc_key in seen:
                continue
            seen.add(loc_key)

            issues = validate_locode(gf_country, gf_subdiv, gf_city)
            if issues:
                loc_str = f"{gf_country}/{gf_subdiv}/{gf_city}" if gf_subdiv else f"{gf_country}/{gf_city}"
                print(f"  [ISSUE] {loc_str}: {issues[0]}")
                feed_issues += 1

        print(f"  {feed_issues} issue(s).\n" if feed_issues else "  No issues.\n")
        total_issues += feed_issues

    print(f"=== Total: {total_issues} issue(s) across all feeds ===")


if __name__ == "__main__":
    main()
