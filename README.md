# Geofeed Monitor

Monitors the accuracy of [RFC 8805 geofeeds](https://datatracker.ietf.org/doc/html/rfc8805) by validating geolocation claims against third-party geolocation databases, routing tables, the GeoNames location registry, and RIR whois data.

## What it does

1. Fetches geofeed CSVs — lists of IP prefixes with their claimed country, subdivision, and city.
2. Looks up each prefix in multiple geolocation providers (MaxMind GeoLite2, IPinfo Lite, IP2Location Lite, DB-IP City Lite, IPLocate) and compares the results.
3. Validates each location entry against the [GeoNames cities1000](https://download.geonames.org/export/dump/cities1000.zip) dataset — checking that the city exists and belongs to the claimed country.
4. Checks each prefix for visibility in the global routing table using [RIPE RIS](https://www.ripe.net/analyse/internet-measurements/routing-information-service-ris) whois dumps.
5. Checks each prefix for a registered geofeed URL in RIR whois (RFC 9092/9632) using the [geolocatemuch.com](https://geolocatemuch.com/) validated prefix list and [ARIN Bulk Whois](https://www.arin.net/reference/research/bulkwhois/) data as fallback.
6. Tracks when geofeed source data and provider data last changed for each prefix, showing ingestion lag indicators.
7. Generates self-contained HTML reports with:
   - Global accuracy statistics (by prefix and by address count)
   - Per-location breakdown with expandable prefix details
   - Location name validation warnings per location
   - Routing visibility indicators per prefix (visible / not visible / too specific)
   - Geofeed in RIR indicators per prefix (matches / mismatches / not registered)
   - Change timestamps with relative time display and provider ingestion status
   - Search by prefix or IP address
   - Filter to show only inaccurate entries
8. Generates a landing page (`index.html`) with per-feed summary cards showing prefix count, accuracy, routing, location name, and Geofeed in RIR stats.
9. Sends Slack alerts on detected changes or issues (see [Alerting](#alerting)).

## Monitored Geofeeds

| Network | Geofeed | Report |
|---------|---------|--------|
| [AWS](https://aws.amazon.com/) (Official) | [geo-ip-feed.csv](https://ip-ranges.amazonaws.com/geo-ip-feed.csv) | [aws.html](https://chriselsen.github.io/Geofeed-Monitor/aws.html) |
| [Google Cloud](https://cloud.google.com/) | [cloud_geofeed](https://www.gstatic.com/ipranges/cloud_geofeed) | [gcp.html](https://chriselsen.github.io/Geofeed-Monitor/gcp.html) |
| [Microsoft](https://www.microsoft.com/) | [geoloc-Microsoft.csv](https://www.microsoft.com/en-us/download/details.aspx?id=53601) | [microsoft.html](https://chriselsen.github.io/Geofeed-Monitor/microsoft.html) |
| [AWS](https://aws.amazon.com/) (Christian Elsen) | [aws-geofeed.txt](https://raw.githubusercontent.com/chriselsen/AWS-Geofeed/main/data/aws-geofeed.txt) | [aws-ce.html](https://chriselsen.github.io/Geofeed-Monitor/aws-ce.html) |
| [AS213151](https://as213151.net/) | [geofeed.as213151.net](https://geofeed.as213151.net/geofeed.txt) | [as213151.html](https://chriselsen.github.io/Geofeed-Monitor/as213151.html) |
| [Starlink](https://www.starlink.com/) | [geoip.starlinkisp.net](https://geoip.starlinkisp.net/) | [starlink.html](https://chriselsen.github.io/Geofeed-Monitor/starlink.html) |

Note: The Microsoft feed is not a strict RFC 8805 geofeed — it uses a CSV with a header row and uppercase city names. The download URL is resolved dynamically from the Microsoft Download Center page on each run.

## Live Report

The reports are published via GitHub Pages and refreshed daily:

**https://chriselsen.github.io/Geofeed-Monitor/**

## Running locally

```bash
pip install -r requirements.txt

export MAXMIND_ACCOUNT_ID="<your_account_id>"
export MAXMIND_LICENSE_KEY="<your_license_key>"
export IPINFO_TOKEN="<your_token>"
export IP2LOCATION_TOKEN="<your_token>"
export ARIN_API_KEY="<your_api_key>"   # optional, for ARIN bulk whois

python3 monitor-geofeed.py
```

Provider credentials are optional — if unset, that provider is skipped. Reports are written to `aws.html`, `gcp.html`, `microsoft.html`, `aws-ce.html`, `as213151.html`, `starlink.html`, and a landing page `index.html`.

## Providers

| Provider | Database | Coverage |
|----------|----------|----------|
| [MaxMind](https://www.maxmind.com/) | GeoLite2-City | Country + City |
| [IPinfo](https://ipinfo.io/) | IPinfo Lite | Country only |
| [IP2Location](https://www.ip2location.com/) | DB3 Lite | Country + City |
| [DB-IP](https://db-ip.com/) | City Lite | Country + City |
| [IPLocate](https://www.iplocate.io/) | IP-to-Country | Country only (City when upgraded) |

## Validation

### Location Name Validation

Each geofeed location entry is validated against the [GeoNames cities1000](https://download.geonames.org/export/dump/cities1000.zip) dataset (places with population ≥ 1,000). The following issues are flagged with a warning icon on the location row:

- City name not found anywhere in GeoNames (e.g. typos like "Colombus", "Abdijan")
- City found but not in the claimed country (e.g. Hong Kong claimed as `CN` instead of `HK`) — with a "known in" hint

City name matching is diacritic- and case-insensitive and leverages GeoNames alternate names, so that local/alternate spellings (e.g. "München" / "Munich", "Tel Aviv-Yafo" / "Tel Aviv") are recognised correctly.

You can run location validation standalone (without loading geolocation databases) via:

```bash
python3 validate-locode.py
```

### Routing Visibility

Each prefix is checked against [RIPE RIS](https://www.ris.ripe.net/dumps/) whois dumps (updated every ~5 minutes), requiring visibility by at least 2 peers. A prefix is considered routed if:

- The exact prefix is announced, **or**
- A covering supernet is announced (e.g. geofeed has `/24`, BGP has `/23`), **or**
- A more-specific is announced (e.g. geofeed has `/23`, BGP has `/24`)

Prefixes more specific than `/24` (IPv4) or `/48` (IPv6) are marked as too specific to appear in the global routing table and shown with a grey indicator.

### Geofeed in RIR (RFC 9092/9632)

Each prefix is checked against the [geolocatemuch.com](https://geolocatemuch.com/geofeeds/validated-all.csv) daily-updated validated prefix list (sourced from all RIR whois databases). If a prefix is found, its registered geofeed URL is retrieved via RDAP and compared to the monitored feed URL. Results are cached locally to avoid repeated RDAP queries.

**ARIN Bulk Whois Fallback:** If the `ARIN_API_KEY` environment variable is set, the monitor downloads the [ARIN Bulk Whois](https://www.arin.net/reference/research/bulkwhois/) nets file (cached for 24 hours) and extracts geofeed URLs from network record comments. This covers prefixes that geolocatemuch.com hasn't indexed yet, including child prefixes that inherit the geofeed URL from a parent allocation. The bulk whois data is only used as a fallback when a prefix is not found in the geolocatemuch.com validated list.

Per-prefix indicators:
- 🟢 Green shield — geofeed URL in RIR whois matches the monitored feed URL
- 🟡 Amber shield — geofeed URL in RIR whois points to a different URL
- ⚫ Grey shield — no geofeed entry found in RIR whois

Per-location summary icons reflect the proportion of prefixes with registered geofeed entries.

This check is opt-in per feed via the `check_rdap` config key. Currently enabled for: AWS (Official), AS213151.

### Change Timestamps

The monitor tracks when geofeed source data and provider data last changed for each prefix. On each run, current values are compared against previously stored values in the state file.

- **Last Changed column** — shows when the geofeed data (country, subdivision, or city) last changed for each prefix, displayed as a relative time (e.g. "5 days ago") with full ISO timestamp on hover. Shows "N/A" until a change is detected.
- **Provider timestamps** — below each provider match cell, shows when that provider last changed its data for the prefix as a relative time (e.g. "3 days ago") with full ISO timestamp on hover.

## Alerting

Slack alerts are sent via webhooks on a per-feed, per-alert-type basis. Each alert type has a fixed JSON schema for use with Slack Workflows.

### Alert types

| Type | Trigger | Key fields |
|------|---------|------------|
| `UNREACHABLE` | Feed URL failed to load | `feed`, `url` |
| `EMBARGO` | Location claims a sanctioned country | `feed`, `location`, `country`, `prefix_count`, `prefixes` |
| `NEW_LOCATION` | A new location group appeared | `feed`, `location`, `country`, `prefix_count`, `prefixes` |
| `REMOVED_LOCATION` | A previously known location is gone | `feed`, `location`, `country`, `prefix_count`, `prefixes` |
| `NEW_PREFIX` | Prefixes added to an existing location | `feed`, `location`, `country`, `prefix_count`, `prefixes` |
| `REMOVED_PREFIX` | Prefixes removed from an existing location | `feed`, `location`, `country`, `prefix_count`, `prefixes` |
| `ACCURACY_DROP` | Country or city accuracy dropped ≥5pp or fell below 80% | `feed`, `location`, `metric`, `previous_pct`, `current_pct`, `drop_pp` |
| `UNROUTED` | A previously routed prefix is no longer visible | `feed`, `prefix`, `proto` |
| `LOCODE` | A new location name issue was introduced | `feed`, `prefix`, `location`, `issue` |

### Webhook configuration

Webhooks are resolved per feed and alert type with a fallback chain:

```
SLACK_WEBHOOK_<FEED>_<TYPE>  →  SLACK_WEBHOOK_<TYPE>
```

Where `<FEED>` is the feed's output filename uppercased (e.g. `AWS`, `GCP`, `MICROSOFT`, `STARLINK`) and `<TYPE>` is one of the alert types above.

Example — AWS embargo alerts with global fallback:
```
SLACK_WEBHOOK_AWS_EMBARGO   (feed-specific)
SLACK_WEBHOOK_EMBARGO       (global fallback)
```

Sanctioned countries default to the OFAC comprehensive list: `IR`, `CU`, `KP`, `SY`. This can be overridden per feed via the `embargo_countries` config key. The AWS Official feed uses an extended list that also includes `RU` and `BY`.

### State

Alert state is stored in `state/<feed>.json` and committed to the repository by the GitHub Action after each run. This tracks known locations, prefixes, routing status, and location name issues to detect changes between runs.

## License

This project is for monitoring purposes. The geolocation databases are subject to their respective licenses.
