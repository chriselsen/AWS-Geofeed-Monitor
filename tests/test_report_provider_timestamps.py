"""Unit tests for provider timestamp rendering in prefix rows."""

import re
from pathlib import Path
from unittest.mock import MagicMock

from geofeed_monitor.report import generate_html, _provider_timestamp_html, match_cell_with_timestamp


def _minimal_feed():
    """Create a minimal feed config for testing."""
    logo_file = MagicMock()
    logo_file.exists.return_value = False
    return {
        "title": "Test Feed",
        "topbar_title": "Test Feed",
        "output": Path("/tmp/test_report.html"),
        "logo_file": logo_file,
        "logo_type": "svg",
        "url": "https://example.com/geofeed.csv",
    }


def _minimal_results():
    """Create minimal results with one location and one prefix."""
    entry = (
        "192.0.2.0/24",  # 0: prefix
        False,            # 1: is_v6
        "US",             # 2: gf_c
        "US-VA",          # 3: gf_sub
        "Ashburn",        # 4: gf_ci
        "US", "Ashburn", True, True,      # 5-8: mm_c, mm_ci, mm_c_m, mm_ci_m
        "US", True,                       # 9-10: ip_c, ip_c_m
        "US", "Ashburn", True, True,      # 11-14: i2l_c, i2l_ci, i2l_c_m, i2l_ci_m
        None,             # 15: locode_issues
        True,             # 16: routed
        "192.0.2.0/24",   # 17: route_match
        False,            # 18: too_specific
        None,             # 19: rdap_url
        None,             # 20: (unused col)
        "US", "Ashburn", True, True,      # 21-24: dbip_c, dbip_ci, dbip_c_m, dbip_ci_m
        "US", True,                       # 25-26: iplocate_c, iplocate_c_m
    )
    return [("US", "Ashburn, VA, US", [entry])]


def _minimal_stats():
    """Create minimal stats for testing."""
    return {
        "total": 1, "v4": 1, "v6": 0,
        "country_pct": 100.0, "country_pct_v4": 100.0, "country_pct_v6": None,
        "city_pct": 100.0, "city_pct_v4": 100.0, "city_pct_v6": None,
        "v4_addrs": 256, "v6_addrs": 0,
        "w_country_pct": 100.0, "w_country_pct_v4": 100.0, "w_country_pct_v6": None,
        "w_city_pct": 100.0, "w_city_pct_v4": 100.0, "w_city_pct_v6": None,
    }


class TestProviderTimestampHtml:
    """Tests for the _provider_timestamp_html helper function."""

    def test_na_when_provider_changed_at_is_none(self):
        """Should show N/A when provider has no timestamp."""
        result = _provider_timestamp_html(None, "2025-01-15T08:30:00Z")
        assert "N/A" in result

    def test_na_when_both_are_none(self):
        """Should show N/A when both are None."""
        result = _provider_timestamp_html(None, None)
        assert "N/A" in result

    def test_relative_time_when_provider_has_timestamp(self):
        """Should show relative time when provider has a timestamp."""
        result = _provider_timestamp_html("2025-01-17T12:00:00Z", "2025-01-15T08:30:00Z")
        assert "N/A" not in result
        assert "ago" in result or "just now" in result

    def test_full_iso_in_title_attribute(self):
        """Should include full ISO timestamp in title for tooltip."""
        result = _provider_timestamp_html("2025-01-17T12:00:00Z", "2025-01-15T08:30:00Z")
        assert 'title="2025-01-17T12:00:00Z"' in result

    def test_no_ingestion_indicators(self):
        """Should not contain ✓ or ⏳ indicators."""
        result = _provider_timestamp_html("2025-01-17T12:00:00Z", "2025-01-15T08:30:00Z")
        assert "✓" not in result
        assert "⏳" not in result


class TestMatchCellWithTimestamp:
    """Tests for the match_cell_with_timestamp function."""

    def test_good_match_with_timestamp(self):
        """Good match cell should show relative time below the icon."""
        result = match_cell_with_timestamp(
            True, "US", "2025-01-17T12:00:00Z", "2025-01-15T08:30:00Z", True
        )
        assert 'class="good provider-start"' in result
        assert "2025-01-17T12:00:00Z" in result
        assert "✓" not in result.split("</span>", 1)[-1]  # no ingestion indicator

    def test_bad_match_with_timestamp(self):
        """Bad match cell should show relative time below the icon."""
        result = match_cell_with_timestamp(
            False, "DE", "2025-01-14T06:00:00Z", "2025-01-15T08:30:00Z", True
        )
        assert 'class="bad provider-start"' in result
        assert "⏳" not in result

    def test_na_match_with_timestamp(self):
        """N/A match cell should still show timestamp info."""
        result = match_cell_with_timestamp(
            None, None, "2025-01-17T12:00:00Z", "2025-01-15T08:30:00Z", True
        )
        assert 'class="na provider-start"' in result

    def test_no_provider_start_class(self):
        """Cell without provider_start should not have provider-start class."""
        result = match_cell_with_timestamp(
            True, "US", "2025-01-17T12:00:00Z", "2025-01-15T08:30:00Z", False, is_city=True
        )
        assert "provider-start" not in result
        assert 'class="good"' in result


class TestFullReportProviderTimestamps:
    """Integration tests for provider timestamps in generate_html output."""

    def test_provider_timestamp_shown_in_prefix_row(self, tmp_path):
        """Provider cells should show relative time when timestamp is available."""
        output = tmp_path / "report.html"
        feed = _minimal_feed()
        feed["output"] = output

        change_tracking = {
            "192.0.2.0/24": {
                "geofeed_changed_at": "2025-01-15T08:30:00Z",
                "providers": {
                    "maxmind": {"country": "US", "city": "Ashburn", "changed_at": "2025-01-17T12:00:00Z"},
                    "ipinfo": {"country": "US", "city": "", "changed_at": "2025-01-16T06:00:00Z"},
                    "ip2location": {"country": "US", "city": "Ashburn", "changed_at": "2025-01-18T00:00:00Z"},
                    "dbip": {"country": "US", "city": "Ashburn", "changed_at": "2025-01-18T00:00:00Z"},
                    "iplocate": {"country": "US", "city": "", "changed_at": "2025-01-16T06:00:00Z"},
                },
            }
        }

        generate_html(
            _minimal_results(), _minimal_stats(),
            has_mm=True, has_ip=True, has_i2l=True, has_dbip=True, has_iplocate=True,
            feed=feed, change_tracking=change_tracking,
        )
        html = output.read_text()

        # Full ISO timestamps should be in the HTML (in title attributes or JS lookup)
        assert "2025-01-17T12:00:00Z" in html
        # Should NOT contain ingestion indicators
        prefix_row_match = re.search(r'class="prefix-row".*?</tr>', html, re.DOTALL)
        assert prefix_row_match is not None
        prefix_row = prefix_row_match.group()
        assert "⏳" not in prefix_row

    def test_provider_timestamp_na_when_provider_has_no_timestamp(self, tmp_path):
        """Provider cells should show N/A when provider has no changed_at."""
        output = tmp_path / "report.html"
        feed = _minimal_feed()
        feed["output"] = output

        change_tracking = {
            "192.0.2.0/24": {
                "geofeed_changed_at": "2025-01-15T08:30:00Z",
                "providers": {
                    "maxmind": {"country": "US", "city": "Ashburn", "changed_at": None},
                },
            }
        }

        generate_html(
            _minimal_results(), _minimal_stats(),
            has_mm=True, has_ip=False, has_i2l=False, has_dbip=False, has_iplocate=False,
            feed=feed, change_tracking=change_tracking,
        )
        html = output.read_text()

        prefix_row_match = re.search(r'class="prefix-row".*?</tr>', html, re.DOTALL)
        assert prefix_row_match is not None
        prefix_row = prefix_row_match.group()
        assert prefix_row.count("N/A") >= 1

    def test_no_provider_timestamps_when_change_tracking_none(self, tmp_path):
        """When change_tracking is None, no provider timestamps should appear."""
        output = tmp_path / "report.html"
        feed = _minimal_feed()
        feed["output"] = output

        generate_html(
            _minimal_results(), _minimal_stats(),
            has_mm=True, has_ip=True, has_i2l=True, has_dbip=True, has_iplocate=True,
            feed=feed, change_tracking=None,
        )
        html = output.read_text()

        prefix_row_match = re.search(r'class="prefix-row".*?</tr>', html, re.DOTALL)
        assert prefix_row_match is not None
        prefix_row = prefix_row_match.group()
        assert "⏳" not in prefix_row
        assert "#037f0c" not in prefix_row
