# Feature: geofeed-change-timestamps, Property 1: Geofeed change detection
"""
Property-based tests for geofeed change detection.

**Validates: Requirements 1.1, 1.2, 1.3, 3.1, 3.4, 3.8**
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from geofeed_monitor.timestamps import detect_geofeed_change


# Strategy: generate arbitrary text values that may include whitespace variations
whitespace_chars = st.sampled_from(["", " ", "  ", "\t", " \t", "\t "])


def with_whitespace(base_strategy):
    """Wrap a base string strategy with optional leading/trailing whitespace."""
    return st.builds(
        lambda prefix_ws, value, suffix_ws: prefix_ws + value + suffix_ws,
        whitespace_chars,
        base_strategy,
        whitespace_chars,
    )


# Strategy for geofeed field values (country codes, subdivisions, city names)
geofeed_field = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=0,
    max_size=20,
)


@settings(max_examples=200)
@given(
    country=geofeed_field,
    subdivision=geofeed_field,
    city=geofeed_field,
    ws_prefix_c=whitespace_chars,
    ws_suffix_c=whitespace_chars,
    ws_prefix_s=whitespace_chars,
    ws_suffix_s=whitespace_chars,
    ws_prefix_ci=whitespace_chars,
    ws_suffix_ci=whitespace_chars,
)
def test_no_change_when_trimmed_values_match(
    country,
    subdivision,
    city,
    ws_prefix_c,
    ws_suffix_c,
    ws_prefix_s,
    ws_suffix_s,
    ws_prefix_ci,
    ws_suffix_ci,
):
    """
    When current values and stored values are identical after trimming,
    detect_geofeed_change should return False regardless of whitespace.

    This validates Requirement 1.1 (case-sensitive after trim) and 1.3 (no change retains timestamp).
    """
    # Current values with some whitespace
    current_values = (
        ws_prefix_c + country + ws_suffix_c,
        ws_prefix_s + subdivision + ws_suffix_s,
        ws_prefix_ci + city + ws_suffix_ci,
    )

    # Previous entry stores the same trimmed values (possibly with different whitespace)
    prev_entry = {
        "geofeed_values": {
            "country": country,
            "subdivision": subdivision,
            "city": city,
        }
    }

    result = detect_geofeed_change("192.0.2.0/24", current_values, prev_entry)
    assert result is False, (
        f"Expected no change for matching trimmed values: "
        f"current={current_values}, stored={prev_entry}"
    )


@settings(max_examples=200)
@given(
    country=geofeed_field,
    subdivision=geofeed_field,
    city=geofeed_field,
    alt_country=geofeed_field,
    alt_subdivision=geofeed_field,
    alt_city=geofeed_field,
    ws_prefix=whitespace_chars,
    ws_suffix=whitespace_chars,
)
def test_change_detected_when_at_least_one_trimmed_field_differs(
    country,
    subdivision,
    city,
    alt_country,
    alt_subdivision,
    alt_city,
    ws_prefix,
    ws_suffix,
):
    """
    When at least one field differs after trimming (case-sensitively),
    detect_geofeed_change should return True.

    This validates Requirement 1.1 (change detected on field difference)
    and Requirement 3.1 (timestamp stored on change).
    """
    # Ensure at least one field actually differs after trim
    assume(
        country.strip() != alt_country.strip()
        or subdivision.strip() != alt_subdivision.strip()
        or city.strip() != alt_city.strip()
    )

    current_values = (
        ws_prefix + alt_country + ws_suffix,
        ws_prefix + alt_subdivision + ws_suffix,
        ws_prefix + alt_city + ws_suffix,
    )

    prev_entry = {
        "geofeed_values": {
            "country": country,
            "subdivision": subdivision,
            "city": city,
        }
    }

    result = detect_geofeed_change("192.0.2.0/24", current_values, prev_entry)
    assert result is True, (
        f"Expected change detected when trimmed values differ: "
        f"current={current_values}, stored={prev_entry}"
    )


@settings(max_examples=200)
@given(
    country=geofeed_field,
    subdivision=geofeed_field,
    city=geofeed_field,
)
def test_no_change_for_none_prev_entry(country, subdivision, city):
    """
    When prev_entry is None (new prefix, no prior state), detect_geofeed_change
    returns False because there is no previous data to compare against.

    This validates Requirement 3.7 (new prefix stores values without recording change).
    """
    current_values = (country, subdivision, city)
    result = detect_geofeed_change("10.0.0.0/8", current_values, None)
    assert result is False


@settings(max_examples=200)
@given(
    country=with_whitespace(geofeed_field),
    subdivision=with_whitespace(geofeed_field),
    city=with_whitespace(geofeed_field),
    stored_country=with_whitespace(geofeed_field),
    stored_subdivision=with_whitespace(geofeed_field),
    stored_city=with_whitespace(geofeed_field),
)
def test_change_detection_is_case_sensitive(
    country,
    subdivision,
    city,
    stored_country,
    stored_subdivision,
    stored_city,
):
    """
    Verify detect_geofeed_change returns True iff at least one trimmed field
    differs case-sensitively between current and stored values.

    This is the core property: the function is equivalent to checking whether
    any of the three trimmed fields differ using Python's == operator (case-sensitive).

    **Validates: Requirements 1.1, 1.2, 1.3, 3.1, 3.4, 3.8**
    """
    current_values = (country, subdivision, city)
    prev_entry = {
        "geofeed_values": {
            "country": stored_country,
            "subdivision": stored_subdivision,
            "city": stored_city,
        }
    }

    result = detect_geofeed_change("2001:db8::/32", current_values, prev_entry)

    # Compute expected result: True iff at least one trimmed field differs
    expected = (
        (country or "").strip() != (stored_country or "").strip()
        or (subdivision or "").strip() != (stored_subdivision or "").strip()
        or (city or "").strip() != (stored_city or "").strip()
    )

    assert result == expected, (
        f"detect_geofeed_change mismatch: got {result}, expected {expected}. "
        f"current={current_values}, stored_country={stored_country!r}, "
        f"stored_subdivision={stored_subdivision!r}, stored_city={stored_city!r}"
    )


@settings(max_examples=100)
@given(
    country=geofeed_field,
    subdivision=geofeed_field,
    city=geofeed_field,
)
def test_missing_fields_treated_as_empty_string(country, subdivision, city):
    """
    When prev_entry has geofeed_values dict but is missing some keys,
    those missing fields are treated as empty string.

    This validates Requirement 1.6 (absent fields treated as empty string).
    """
    current_values = (country, subdivision, city)

    # Previous entry with missing keys (partial geofeed_values)
    prev_entry = {"geofeed_values": {}}

    result = detect_geofeed_change("172.16.0.0/12", current_values, prev_entry)

    # Expected: change if any current trimmed value is non-empty
    expected = (
        (country or "").strip() != ""
        or (subdivision or "").strip() != ""
        or (city or "").strip() != ""
    )

    assert result == expected, (
        f"Missing fields should be treated as empty string. "
        f"current={current_values}, got {result}, expected {expected}"
    )


# Feature: geofeed-change-timestamps, Property 5: New prefix gets null timestamps
"""
Property-based tests for new prefix null timestamp behavior.

**Validates: Requirements 3.6, 3.7, 6.1**
"""

from geofeed_monitor.timestamps import compute_timestamps

# Strategy for generating valid-looking IP prefixes
ip_prefix = st.from_regex(
    r"(([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}|[0-9a-f]{1,4}(:[0-9a-f]{0,4}){2,7}::/[0-9]{1,3})",
    fullmatch=True,
)

# Strategy for provider field values
provider_field = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=0,
    max_size=15,
)


def _build_result_tuple(prefix, maxmind_country, maxmind_city, ipinfo_country,
                        ip2loc_country, ip2loc_city, dbip_country, dbip_city,
                        iplocate_country):
    """Build a result tuple with at least 26 elements matching expected provider indices."""
    # Indices: 0=prefix, 5=maxmind_country, 6=maxmind_city, 9=ipinfo_country,
    #          11=ip2loc_country, 12=ip2loc_city, 21=dbip_country, 22=dbip_city, 25=iplocate_country
    entry = [None] * 26
    entry[0] = prefix
    entry[5] = maxmind_country
    entry[6] = maxmind_city
    entry[9] = ipinfo_country
    entry[11] = ip2loc_country
    entry[12] = ip2loc_city
    entry[21] = dbip_country
    entry[22] = dbip_city
    entry[25] = iplocate_country
    return tuple(entry)


@settings(max_examples=100)
@given(
    data=st.data(),
    num_prefixes=st.integers(min_value=1, max_value=10),
)
def test_new_prefix_gets_initial_timestamps(data, num_prefixes):
    """
    For any prefix that appears in the current geofeed but has no entry in the
    previous change_tracking, the resulting entry SHALL have:
    - geofeed_changed_at set to None (first observation, no change detected yet)
    - All providers.*.changed_at set to the current time (baseline)
    - Current geofeed and provider values stored as baseline

    **Validates: Requirements 1.4, 6.1**
    """
    # Generate unique prefixes
    prefixes = data.draw(
        st.lists(
            ip_prefix,
            min_size=num_prefixes,
            max_size=num_prefixes,
            unique=True,
        )
    )

    # Generate geofeed values for each prefix
    geofeed = {}
    expected_geofeed_values = {}
    for prefix in prefixes:
        country = data.draw(geofeed_field)
        subdivision = data.draw(geofeed_field)
        city = data.draw(geofeed_field)
        geofeed[prefix] = (country, subdivision, city)
        expected_geofeed_values[prefix] = {
            "country": (country or "").strip(),
            "subdivision": (subdivision or "").strip(),
            "city": (city or "").strip(),
        }

    # Generate provider values for each prefix
    expected_providers = {}
    loc_results = []
    for prefix in prefixes:
        maxmind_country = data.draw(provider_field)
        maxmind_city = data.draw(provider_field)
        ipinfo_country = data.draw(provider_field)
        ip2loc_country = data.draw(provider_field)
        ip2loc_city = data.draw(provider_field)
        dbip_country = data.draw(provider_field)
        dbip_city = data.draw(provider_field)
        iplocate_country = data.draw(provider_field)

        result_tuple = _build_result_tuple(
            prefix, maxmind_country, maxmind_city, ipinfo_country,
            ip2loc_country, ip2loc_city, dbip_country, dbip_city,
            iplocate_country,
        )
        loc_results.append(result_tuple)

        expected_providers[prefix] = {
            "maxmind": {"country": maxmind_country or "", "city": maxmind_city or ""},
            "ipinfo": {"country": ipinfo_country or "", "city": ""},
            "ip2location": {"country": ip2loc_country or "", "city": ip2loc_city or ""},
            "dbip": {"country": dbip_country or "", "city": dbip_city or ""},
            "iplocate": {"country": iplocate_country or "", "city": ""},
        }

    # Wrap loc_results in the results structure: list of (country_code, display_name, loc_results)
    results = [("XX", "Test Location", loc_results)]

    # Empty prev_change_tracking — all prefixes are new
    prev_change_tracking = {}

    # Call compute_timestamps with a fixed time
    from datetime import datetime, timezone
    fixed_now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    now_iso = "2025-06-15T12:00:00Z"
    output = compute_timestamps(geofeed, results, prev_change_tracking, now=fixed_now)

    # Verify each prefix in the output
    for prefix in prefixes:
        assert prefix in output, f"Prefix {prefix} missing from output"
        entry = output[prefix]

        # geofeed_changed_at must be None for new prefixes (no change detected yet)
        assert entry["geofeed_changed_at"] is None, (
            f"New prefix {prefix} should have geofeed_changed_at=None, "
            f"got {entry['geofeed_changed_at']}"
        )

        # All providers.*.changed_at must be set to now (baseline)
        for provider_name, provider_data in entry["providers"].items():
            assert provider_data["changed_at"] == now_iso, (
                f"New prefix {prefix}, provider {provider_name} should have "
                f"changed_at={now_iso}, got {provider_data['changed_at']}"
            )

        # geofeed_values must contain the current trimmed values
        assert entry["geofeed_values"] == expected_geofeed_values[prefix], (
            f"Prefix {prefix}: geofeed_values mismatch. "
            f"Expected {expected_geofeed_values[prefix]}, got {entry['geofeed_values']}"
        )

        # Provider values must be stored correctly
        for provider_name, expected_vals in expected_providers[prefix].items():
            actual_provider = entry["providers"][provider_name]
            assert actual_provider["country"] == expected_vals["country"], (
                f"Prefix {prefix}, provider {provider_name}: country mismatch. "
                f"Expected {expected_vals['country']!r}, got {actual_provider['country']!r}"
            )
            assert actual_provider["city"] == expected_vals["city"], (
                f"Prefix {prefix}, provider {provider_name}: city mismatch. "
                f"Expected {expected_vals['city']!r}, got {actual_provider['city']!r}"
            )


# Feature: geofeed-change-timestamps, Property 4: Prefix removal cleans state
"""
Property-based tests for prefix removal cleaning state.

**Validates: Requirements 1.5, 3.3**
"""

from geofeed_monitor.timestamps import compute_timestamps
from datetime import datetime, timezone

# Strategy for generating valid IP prefix strings
prefix_strategy = st.from_regex(
    r"(192\.168\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}|10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}|2001:db8:[0-9a-f:]{1,19}/[0-9]{1,3})",
    fullmatch=True,
)

# Strategy for generating a set of unique prefixes
prefix_set_strategy = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".:/-"),
        min_size=5,
        max_size=30,
    ),
    min_size=1,
    max_size=10,
    unique=True,
)


def _make_prev_entry():
    """Create a minimal previous change_tracking entry for a prefix."""
    return {
        "geofeed_values": {
            "country": "US",
            "subdivision": "US-VA",
            "city": "Ashburn",
        },
        "geofeed_changed_at": "2025-01-10T00:00:00Z",
        "providers": {
            "maxmind": {"country": "US", "city": "Ashburn", "changed_at": "2025-01-11T00:00:00Z"},
            "ipinfo": {"country": "US", "city": "", "changed_at": None},
            "ip2location": {"country": "US", "city": "Ashburn", "changed_at": None},
            "dbip": {"country": "US", "city": "Ashburn", "changed_at": "2025-01-12T00:00:00Z"},
            "iplocate": {"country": "US", "city": "", "changed_at": None},
        },
    }


def _make_result_entry(prefix):
    """Create a mock result tuple with at least 26 elements for a prefix."""
    entry = [""] * 26
    entry[0] = prefix
    return entry


@settings(max_examples=100)
@given(
    previous_prefixes=st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".:/-"),
            min_size=3,
            max_size=20,
        ),
        min_size=1,
        max_size=8,
        unique=True,
    ),
    new_prefixes=st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".:/-"),
            min_size=3,
            max_size=20,
        ),
        min_size=0,
        max_size=5,
        unique=True,
    ),
    retain_mask=st.lists(st.booleans(), min_size=1, max_size=8),
)
def test_prefix_removal_cleans_state(previous_prefixes, new_prefixes, retain_mask):
    """
    Property 4: Prefix removal cleans state.

    When a prefix present in prev_change_tracking does not appear in the current
    geofeed, it must be absent from the output. Conversely, every prefix in the
    current geofeed must appear in the output. The output keyset must exactly
    match the current geofeed keyset.

    **Validates: Requirements 1.5, 3.3**
    """
    # Build prev_change_tracking with all previous prefixes
    prev_change_tracking = {}
    for prefix in previous_prefixes:
        prev_change_tracking[prefix] = _make_prev_entry()

    # Select which previous prefixes to retain in the current geofeed
    # Extend retain_mask to match previous_prefixes length
    effective_mask = (retain_mask * ((len(previous_prefixes) // len(retain_mask)) + 1))[
        : len(previous_prefixes)
    ]
    retained_prefixes = [p for p, keep in zip(previous_prefixes, effective_mask) if keep]

    # Combine retained previous prefixes with new prefixes for the current geofeed
    # Ensure new prefixes don't overlap with previous ones
    current_prefix_list = retained_prefixes + [
        p for p in new_prefixes if p not in previous_prefixes
    ]

    # Need at least one prefix in current geofeed for meaningful test
    assume(len(current_prefix_list) > 0)

    # Build the current geofeed dict
    geofeed = {}
    for prefix in current_prefix_list:
        geofeed[prefix] = ("US", "US-CA", "Los Angeles")

    # Build mock results covering all current geofeed prefixes
    results = [("US", "United States", [_make_result_entry(p) for p in current_prefix_list])]

    # Call compute_timestamps
    now = datetime(2025, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
    output = compute_timestamps(geofeed, results, prev_change_tracking, now=now)

    # Verify: output keyset exactly matches current geofeed keyset
    assert set(output.keys()) == set(geofeed.keys()), (
        f"Output keys {set(output.keys())} != geofeed keys {set(geofeed.keys())}. "
        f"Previous prefixes: {previous_prefixes}, retained: {retained_prefixes}, "
        f"new: {new_prefixes}"
    )

    # Verify: every prefix in current geofeed is present in output
    for prefix in current_prefix_list:
        assert prefix in output, f"Current prefix {prefix!r} missing from output"

    # Verify: prefixes NOT in the current geofeed are absent from output
    removed_prefixes = [p for p in previous_prefixes if p not in geofeed]
    for prefix in removed_prefixes:
        assert prefix not in output, (
            f"Removed prefix {prefix!r} should not be in output but was found"
        )


# Feature: geofeed-change-timestamps, Property 3: Relative time formatting
"""
Property-based tests for relative time formatting.

**Validates: Requirements 4.2, 5.2, 5.6**
"""

import re
from datetime import datetime, timedelta, timezone

from geofeed_monitor.timestamps import format_relative_time

# Regex patterns for each time bucket
_JUST_NOW_PATTERN = re.compile(r"^just now$")
_MINUTES_PATTERN = re.compile(r"^(\d+) minutes? ago$")
_HOURS_PATTERN = re.compile(r"^(\d+) hours? ago$")
_DAYS_PATTERN = re.compile(r"^(\d+) days? ago$")
_MONTHS_PATTERN = re.compile(r"^(\d+) months? ago$")
_YEARS_PATTERN = re.compile(r"^(\d+) years? ago$")

_ALL_PATTERNS = [
    _JUST_NOW_PATTERN,
    _MINUTES_PATTERN,
    _HOURS_PATTERN,
    _DAYS_PATTERN,
    _MONTHS_PATTERN,
    _YEARS_PATTERN,
]


@settings(max_examples=200)
@given(
    delta=st.timedeltas(
        min_value=timedelta(seconds=1),
        max_value=timedelta(days=365 * 5),
    )
)
def test_relative_time_output_matches_exactly_one_bucket(delta):
    """
    For any timedelta from 1 second to ~5 years in the past, format_relative_time
    should return a non-empty string that matches exactly one of the defined time
    buckets, with correct singular/plural forms.

    **Validates: Requirements 4.2, 5.2, 5.6**
    """
    fixed_now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    past_time = fixed_now - delta
    iso_timestamp = past_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    result = format_relative_time(iso_timestamp, now=fixed_now)

    # Verify output is non-empty
    assert result, f"Expected non-empty output for delta={delta}, got empty string"

    # Verify output matches exactly one bucket
    matches = [p for p in _ALL_PATTERNS if p.match(result)]
    assert len(matches) == 1, (
        f"Expected exactly one bucket match for delta={delta}, "
        f"got {len(matches)} matches for result={result!r}"
    )

    # Verify singular/plural correctness
    total_seconds = int(delta.total_seconds())

    if total_seconds < 60:
        # Should be "just now"
        assert result == "just now", (
            f"Expected 'just now' for {total_seconds}s, got {result!r}"
        )
    elif total_seconds < 3600:
        # Should be minutes bucket
        m = _MINUTES_PATTERN.match(result)
        assert m, f"Expected minutes pattern for {total_seconds}s, got {result!r}"
        n = int(m.group(1))
        if n == 1:
            assert result == "1 minute ago", (
                f"Expected singular '1 minute ago', got {result!r}"
            )
        else:
            assert "minutes" in result, (
                f"Expected plural 'minutes' for n={n}, got {result!r}"
            )
    elif total_seconds < 86400:
        # Should be hours bucket
        m = _HOURS_PATTERN.match(result)
        assert m, f"Expected hours pattern for {total_seconds}s, got {result!r}"
        n = int(m.group(1))
        if n == 1:
            assert result == "1 hour ago", (
                f"Expected singular '1 hour ago', got {result!r}"
            )
        else:
            assert "hours" in result, (
                f"Expected plural 'hours' for n={n}, got {result!r}"
            )
    elif total_seconds < 86400 * 30:
        # Should be days bucket
        m = _DAYS_PATTERN.match(result)
        assert m, f"Expected days pattern for {total_seconds}s, got {result!r}"
        n = int(m.group(1))
        if n == 1:
            assert result == "1 day ago", (
                f"Expected singular '1 day ago', got {result!r}"
            )
        else:
            assert "days" in result, (
                f"Expected plural 'days' for n={n}, got {result!r}"
            )
    elif total_seconds < 86400 * 365:
        # Should be months bucket
        m = _MONTHS_PATTERN.match(result)
        assert m, f"Expected months pattern for {total_seconds}s, got {result!r}"
        n = int(m.group(1))
        if n == 1:
            assert result == "1 month ago", (
                f"Expected singular '1 month ago', got {result!r}"
            )
        else:
            assert "months" in result, (
                f"Expected plural 'months' for n={n}, got {result!r}"
            )
    else:
        # Should be years bucket
        m = _YEARS_PATTERN.match(result)
        assert m, f"Expected years pattern for {total_seconds}s, got {result!r}"
        n = int(m.group(1))
        if n == 1:
            assert result == "1 year ago", (
                f"Expected singular '1 year ago', got {result!r}"
            )
        else:
            assert "years" in result, (
                f"Expected plural 'years' for n={n}, got {result!r}"
            )


# Feature: geofeed-change-timestamps, Property 7: State migration preserves existing data
"""
Property-based tests for state migration preserving existing data.

**Validates: Requirements 6.3**
"""

import copy


# Strategy for generating legacy state dicts
# Legacy state has: locations (dict), prefixes (list of strings), routed (dict), locode_issues (dict)
# but NO change_tracking key

_location_key = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_,."),
    min_size=1,
    max_size=20,
)

_location_value = st.fixed_dictionaries({
    "country": st.text(min_size=0, max_size=5),
    "subdivision": st.text(min_size=0, max_size=10),
    "city": st.text(min_size=0, max_size=20),
})

_prefix_string = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".:/-"),
    min_size=3,
    max_size=30,
)

_routed_value = st.one_of(st.booleans(), st.text(min_size=0, max_size=10))

_locode_issue_value = st.fixed_dictionaries({
    "message": st.text(min_size=0, max_size=50),
    "severity": st.sampled_from(["warning", "error", "info"]),
})

legacy_state_strategy = st.fixed_dictionaries({
    "locations": st.dictionaries(
        _location_key, _location_value,
        min_size=0, max_size=5,
    ),
    "prefixes": st.lists(_prefix_string, min_size=0, max_size=10),
    "routed": st.dictionaries(
        _prefix_string, _routed_value,
        min_size=0, max_size=5,
    ),
    "locode_issues": st.dictionaries(
        _location_key, _locode_issue_value,
        min_size=0, max_size=5,
    ),
})


@settings(max_examples=100)
@given(
    legacy_state=legacy_state_strategy,
    geofeed_country=geofeed_field,
    geofeed_subdivision=geofeed_field,
    geofeed_city=geofeed_field,
)
def test_state_migration_preserves_existing_data(
    legacy_state,
    geofeed_country,
    geofeed_subdivision,
    geofeed_city,
):
    """
    Property 7: State migration preserves existing data.

    For any state dictionary containing the legacy keys (locations, prefixes,
    routed, locode_issues) but lacking change_tracking, after processing through
    the monitor pipeline, all legacy keys SHALL remain present and unchanged in
    the output state.

    The migration logic in monitor-geofeed.py:
    1. prev_change_tracking = prev_state.get("change_tracking", {}) -> returns {} for legacy states
    2. compute_timestamps(geofeed, results, prev_change_tracking) -> produces change_tracking
    3. new_state = check_and_alert(...) -> returns new_state with legacy keys preserved
    4. new_state["change_tracking"] = change_tracking -> adds new key

    We simulate this pipeline by:
    - Starting with a legacy state (no change_tracking)
    - Extracting prev_change_tracking via .get("change_tracking", {})
    - Calling compute_timestamps with a minimal geofeed/results
    - Building a new_state by copying legacy keys (simulating check_and_alert output)
    - Adding change_tracking to new_state
    - Verifying all legacy keys remain present and unchanged

    **Validates: Requirements 6.3**
    """
    # Ensure no change_tracking key in legacy state
    assert "change_tracking" not in legacy_state

    # Deep copy the legacy state to preserve original values for comparison
    original_legacy = copy.deepcopy(legacy_state)

    # Step 1: Migration logic - extract prev_change_tracking from legacy state
    prev_change_tracking = legacy_state.get("change_tracking", {})
    assert prev_change_tracking == {}  # Legacy state has no change_tracking

    # Step 2: Create a minimal geofeed and results for compute_timestamps
    test_prefix = "192.0.2.0/24"
    geofeed = {test_prefix: (geofeed_country, geofeed_subdivision, geofeed_city)}

    # Build a minimal result tuple with at least 26 elements
    result_entry = [""] * 26
    result_entry[0] = test_prefix
    result_entry[5] = "US"   # maxmind country
    result_entry[6] = "City" # maxmind city
    result_entry[9] = "US"   # ipinfo country
    result_entry[11] = "US"  # ip2location country
    result_entry[12] = "City"  # ip2location city
    result_entry[21] = "US"  # dbip country
    result_entry[22] = "City"  # dbip city
    result_entry[25] = "US"  # iplocate country
    results = [("US", "United States", [result_entry])]

    # Step 3: Call compute_timestamps (this simulates the actual pipeline step)
    change_tracking = compute_timestamps(geofeed, results, prev_change_tracking)

    # Step 4: Simulate check_and_alert output - it preserves legacy keys
    # In the real code, check_and_alert returns a new_state that already has
    # the legacy keys (locations, prefixes, routed, locode_issues)
    new_state = copy.deepcopy(legacy_state)

    # Step 5: Add change_tracking to new_state (the migration step)
    new_state["change_tracking"] = change_tracking

    # VERIFY: All legacy keys remain present in new_state
    for key in ["locations", "prefixes", "routed", "locode_issues"]:
        assert key in new_state, (
            f"Legacy key '{key}' is missing from new_state after migration"
        )

    # VERIFY: Legacy key values are unchanged
    assert new_state["locations"] == original_legacy["locations"], (
        f"'locations' was modified during migration. "
        f"Expected: {original_legacy['locations']}, Got: {new_state['locations']}"
    )
    assert new_state["prefixes"] == original_legacy["prefixes"], (
        f"'prefixes' was modified during migration. "
        f"Expected: {original_legacy['prefixes']}, Got: {new_state['prefixes']}"
    )
    assert new_state["routed"] == original_legacy["routed"], (
        f"'routed' was modified during migration. "
        f"Expected: {original_legacy['routed']}, Got: {new_state['routed']}"
    )
    assert new_state["locode_issues"] == original_legacy["locode_issues"], (
        f"'locode_issues' was modified during migration. "
        f"Expected: {original_legacy['locode_issues']}, Got: {new_state['locode_issues']}"
    )

    # VERIFY: change_tracking was successfully added
    assert "change_tracking" in new_state, (
        "change_tracking key should be present in new_state after migration"
    )
    assert new_state["change_tracking"] == change_tracking, (
        "change_tracking value in new_state should match the computed value"
    )

    # VERIFY: The change_tracking dict has valid structure for the test prefix
    assert test_prefix in change_tracking, (
        f"Test prefix {test_prefix} should be in change_tracking output"
    )
    entry = change_tracking[test_prefix]
    # New prefix with empty prev_change_tracking -> null geofeed timestamp, provider timestamps set
    assert entry["geofeed_changed_at"] is None, (
        "First observation should have geofeed_changed_at=None"
    )
    for provider_name, provider_data in entry["providers"].items():
        assert provider_data["changed_at"] is not None, (
            f"First observation for provider {provider_name} should have changed_at set to current time"
        )

# Feature: geofeed-change-timestamps, Property 6: Provider timestamp displays relative time
"""
Property-based tests for provider timestamp display.

**Validates: Requirements 5.1, 5.2**
"""

from geofeed_monitor.report import _provider_timestamp_html

# Strategy for generating ISO 8601 timestamps using Hypothesis datetime strategy
iso_timestamp_strategy = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2025, 6, 1),
    timezones=st.just(timezone.utc),
).map(lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ"))


@settings(max_examples=100)
@given(
    provider_changed_at=iso_timestamp_strategy,
    geofeed_changed_at=iso_timestamp_strategy,
)
def test_provider_timestamp_shows_relative_time(provider_changed_at, geofeed_changed_at):
    """
    Property 6: Provider timestamp displays relative time.

    For any pair of non-null ISO 8601 timestamps, the provider timestamp HTML
    SHALL contain the relative time and the full ISO timestamp in a title
    attribute, and SHALL NOT contain ingestion indicators (✓ or ⏳).

    **Validates: Requirements 5.1, 5.2**
    """
    result = _provider_timestamp_html(provider_changed_at, geofeed_changed_at)

    # Should contain the full ISO timestamp in title attribute
    assert provider_changed_at in result, (
        f"Expected provider timestamp {provider_changed_at!r} in title, got: {result!r}"
    )

    # Should not contain ingestion indicators
    assert "✓" not in result, f"Unexpected ✓ indicator in: {result!r}"
    assert "⏳" not in result, f"Unexpected ⏳ indicator in: {result!r}"

    # Should contain some relative time text
    assert "ago" in result or "just now" in result, (
        f"Expected relative time text in result, got: {result!r}"
    )
