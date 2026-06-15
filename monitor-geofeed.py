#!/usr/bin/env python3
"""Geofeed Monitor — entry point."""

import json
import maxminddb
import IP2Location
from pathlib import Path

from geofeed_monitor.config import MAXMIND_DB_FILE, IPINFO_DB_FILE, IP2LOCATION_DB_FILE, FEEDS
from geofeed_monitor.providers import update_maxmind, update_ipinfo, update_ip2location, update_dbip, update_iplocate, download_assets
from geofeed_monitor.geofeed import load_geofeed, group_by_location
from geofeed_monitor.matching import validate_prefixes
from geofeed_monitor.stats import compute_stats
from geofeed_monitor.report import generate_html, generate_index
from geofeed_monitor.alerting import check_and_alert, alert_unreachable
from geofeed_monitor.timestamps import compute_timestamps

STATE_DIR = Path("./state")


def main():
    update_maxmind()
    update_ipinfo()
    update_ip2location()
    update_dbip()
    update_iplocate()
    download_assets()

    print("Loading databases...")
    mm_reader = maxminddb.open_database(str(MAXMIND_DB_FILE)) if MAXMIND_DB_FILE.exists() else None
    ip_reader = maxminddb.open_database(str(IPINFO_DB_FILE)) if IPINFO_DB_FILE.exists() else None
    i2l_reader = IP2Location.IP2Location(str(IP2LOCATION_DB_FILE)) if IP2LOCATION_DB_FILE.exists() else None
    from geofeed_monitor.config import DBIP_DB_FILE, IPLOCATE_DB_FILE
    dbip_reader = maxminddb.open_database(str(DBIP_DB_FILE)) if DBIP_DB_FILE.exists() else None
    iplocate_reader = maxminddb.open_database(str(IPLOCATE_DB_FILE)) if IPLOCATE_DB_FILE.exists() else None

    if not mm_reader:
        print("  MaxMind database not available — skipping")
    if not ip_reader:
        print("  IPinfo database not available — skipping")
    if not i2l_reader:
        print("  IP2Location database not available — skipping")
    if not dbip_reader:
        print("  DB-IP database not available — skipping")
    if not iplocate_reader:
        print("  IPLocate database not available — skipping")

    has_mm = mm_reader is not None
    has_ip = ip_reader is not None
    has_i2l = i2l_reader is not None
    has_dbip = dbip_reader is not None
    has_iplocate = iplocate_reader is not None

    feed_stats = []
    for feed in FEEDS:
        print(f"\n=== {feed['title']} ===")
        state_file = STATE_DIR / f"{feed['output'].stem}.json"
        prev_state = json.loads(state_file.read_text()) if state_file.exists() else None
        try:
            geofeed = load_geofeed(feed["url"], feed.get("geofeed_format", "rfc8805"))
        except Exception as e:
            print(f"  Feed unreachable: {e}")
            alert_unreachable(feed)
            feed_stats.append({})
            continue
        locations = group_by_location(geofeed)
        print("Validating prefixes...")
        results = validate_prefixes(locations, mm_reader, ip_reader, i2l_reader, dbip_reader, iplocate_reader, feed.get("check_rdap", False))
        prev_change_tracking = prev_state.get("change_tracking", {}) if prev_state else {}
        change_tracking = compute_timestamps(geofeed, results, prev_change_tracking)
        stats = compute_stats(results, has_mm, has_ip, has_i2l)
        feed_stats.append(stats)
        print("Checking alerts...")
        new_state = check_and_alert(feed, results, stats, prev_state, has_mm, has_ip, has_i2l, has_dbip, has_iplocate)
        new_state["change_tracking"] = change_tracking
        STATE_DIR.mkdir(exist_ok=True)
        state_file.write_text(json.dumps(new_state, indent=2))
        print("Generating HTML report...")
        generate_html(results, stats, has_mm, has_ip, has_i2l, has_dbip, has_iplocate, feed, change_tracking=change_tracking)
        print(f"Report written to {feed['output']}")

    if mm_reader:
        mm_reader.close()
    if ip_reader:
        ip_reader.close()
    if i2l_reader:
        i2l_reader.close()
    if dbip_reader:
        dbip_reader.close()
    if iplocate_reader:
        iplocate_reader.close()

    generate_index(FEEDS, feed_stats)


if __name__ == "__main__":
    main()
