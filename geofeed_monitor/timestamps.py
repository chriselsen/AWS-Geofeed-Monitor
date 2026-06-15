"""Change detection and timestamp tracking for geofeed and provider data."""

from datetime import datetime, timezone
from typing import Optional

# Provider result tuple indices within loc_results entries
_PROVIDER_INDICES = {
    "maxmind": {"country": 5, "city": 6},
    "ipinfo": {"country": 9, "city": None},
    "ip2location": {"country": 11, "city": 12},
    "dbip": {"country": 21, "city": 22},
    "iplocate": {"country": 25, "city": None},
}


def format_relative_time(iso_timestamp: str, now: Optional[datetime] = None) -> str:
    """
    Convert ISO 8601 timestamp to human-readable relative time string.

    Thresholds:
        < 60 seconds: "just now"
        < 60 minutes: "N minutes ago"  (or "1 minute ago")
        < 24 hours:   "N hours ago"    (or "1 hour ago")
        < 30 days:    "N days ago"     (or "1 day ago")
        < 365 days:   "N months ago"   (or "1 month ago")
        >= 365 days:  "N years ago"    (or "1 year ago")
    """
    if now is None:
        now = datetime.now(timezone.utc)

    ts = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    diff = now - ts
    total_seconds = int(diff.total_seconds())

    if total_seconds < 60:
        return "just now"

    minutes = total_seconds // 60
    if minutes < 60:
        if minutes == 1:
            return "1 minute ago"
        return f"{minutes} minutes ago"

    hours = total_seconds // 3600
    if hours < 24:
        if hours == 1:
            return "1 hour ago"
        return f"{hours} hours ago"

    days = total_seconds // 86400
    if days < 30:
        if days == 1:
            return "1 day ago"
        return f"{days} days ago"

    if days < 365:
        months = days // 30
        if months == 1:
            return "1 month ago"
        return f"{months} months ago"

    years = days // 365
    if years == 1:
        return "1 year ago"
    return f"{years} years ago"


def detect_geofeed_change(
    prefix: str,
    current_values: tuple[str, str, str],
    prev_entry: Optional[dict],
) -> bool:
    """
    Detect whether geofeed values changed for a prefix.
    Comparison: case-sensitive after strip() on both sides.
    Missing fields treated as empty string.
    """
    if prev_entry is None:
        return False

    prev_geofeed = prev_entry.get("geofeed_values", {})
    prev_country = prev_geofeed.get("country", "").strip()
    prev_subdivision = prev_geofeed.get("subdivision", "").strip()
    prev_city = prev_geofeed.get("city", "").strip()

    current_country = (current_values[0] or "").strip()
    current_subdivision = (current_values[1] or "").strip()
    current_city = (current_values[2] or "").strip()

    return (
        current_country != prev_country
        or current_subdivision != prev_subdivision
        or current_city != prev_city
    )


def detect_provider_change(
    current_country: Optional[str],
    current_city: Optional[str],
    prev_country: Optional[str],
    prev_city: Optional[str],
) -> bool:
    """
    Detect whether a provider's data changed for a prefix.
    None is treated as empty string for comparison.
    """
    curr_country = (current_country or "").strip()
    curr_city = (current_city or "").strip()
    p_country = (prev_country or "").strip()
    p_city = (prev_city or "").strip()

    return curr_country != p_country or curr_city != p_city


def compute_timestamps(
    geofeed: dict[str, tuple[str, str, str]],
    results: list[tuple[str, str, list]],
    prev_change_tracking: dict,
    now: Optional[datetime] = None,
) -> dict:
    """
    Compare current geofeed values and provider values against previously
    stored values. Return updated change_tracking dict.

    Parameters:
        geofeed: prefix -> (country, subdivision, city) from load_geofeed()
        results: output of validate_prefixes() — list of (country_code, display_name, loc_results)
        prev_change_tracking: the "change_tracking" dict from the previous state file (or {})
        now: current UTC time (injectable for testing)

    Returns:
        dict keyed by prefix, each value containing:
            - geofeed_values: {country, subdivision, city}
            - geofeed_changed_at: ISO 8601 string or None
            - providers: dict keyed by provider name, each containing:
                - country: str
                - city: str
                - changed_at: ISO 8601 string or None
    """
    if now is None:
        now = datetime.now(timezone.utc)

    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build a mapping from prefix to its result tuple by iterating all location groups
    prefix_to_result = {}
    for _country_code, _display_name, loc_results in results:
        for entry in loc_results:
            prefix = entry[0]
            prefix_to_result[prefix] = entry

    change_tracking = {}

    for prefix, current_values in geofeed.items():
        prev_entry = prev_change_tracking.get(prefix)
        result_entry = prefix_to_result.get(prefix)

        # Current geofeed values (trimmed)
        current_country = (current_values[0] or "").strip()
        current_subdivision = (current_values[1] or "").strip()
        current_city = (current_values[2] or "").strip()

        # Extract current provider values from the result tuple
        current_providers = {}
        for provider_name, indices in _PROVIDER_INDICES.items():
            if result_entry is not None:
                country_val = result_entry[indices["country"]] if indices["country"] is not None else ""
                city_val = result_entry[indices["city"]] if indices["city"] is not None else ""
            else:
                country_val = ""
                city_val = ""
            current_providers[provider_name] = {
                "country": country_val or "",
                "city": city_val or "",
            }

        if prev_entry is None:
            # New prefix — store current values as baseline, null geofeed timestamp
            # Provider timestamps set to now (first observation baseline)
            providers_output = {}
            for provider_name, vals in current_providers.items():
                providers_output[provider_name] = {
                    "country": vals["country"],
                    "city": vals["city"],
                    "changed_at": now_iso,
                }

            change_tracking[prefix] = {
                "geofeed_values": {
                    "country": current_country,
                    "subdivision": current_subdivision,
                    "city": current_city,
                },
                "geofeed_changed_at": None,
                "providers": providers_output,
            }
        else:
            # Existing prefix — detect changes
            geofeed_changed = detect_geofeed_change(prefix, current_values, prev_entry)

            if geofeed_changed:
                geofeed_changed_at = now_iso
            else:
                geofeed_changed_at = prev_entry.get("geofeed_changed_at")

            # Provider change detection
            providers_output = {}
            prev_providers = prev_entry.get("providers", {})

            for provider_name, vals in current_providers.items():
                prev_provider = prev_providers.get(provider_name, {})
                prev_country = prev_provider.get("country")
                prev_city = prev_provider.get("city")

                provider_changed = detect_provider_change(
                    vals["country"], vals["city"],
                    prev_country, prev_city,
                )

                if provider_changed:
                    changed_at = now_iso
                else:
                    changed_at = prev_provider.get("changed_at")

                providers_output[provider_name] = {
                    "country": vals["country"],
                    "city": vals["city"],
                    "changed_at": changed_at,
                }

            change_tracking[prefix] = {
                "geofeed_values": {
                    "country": current_country,
                    "subdivision": current_subdivision,
                    "city": current_city,
                },
                "geofeed_changed_at": geofeed_changed_at,
                "providers": providers_output,
            }

    return change_tracking
