"""Unit tests for the Last Changed display in the HTML report."""

import re
from pathlib import Path
from unittest.mock import MagicMock

from geofeed_monitor.report import generate_html


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


class TestLastChangedInline:
    """Tests for the Last Changed inline display in the Location cell."""

    def test_no_change_info_when_change_tracking_none(self, tmp_path):
        """When change_tracking is None, no change info should appear in prefix rows."""
        output = tmp_path / "report.html"
        feed = _minimal_feed()
        feed["output"] = output

        generate_html(
            _minimal_results(), _minimal_stats(),
            has_mm=True, has_ip=False, has_i2l=False, has_dbip=False, has_iplocate=False,
            feed=feed, change_tracking=None,
        )
        html = output.read_text()
        assert "changed" not in html.lower() or "Last Changed" not in html

    def test_prefix_row_shows_changed_inline(self, tmp_path):
        """Prefix row should show 'changed X ago' inline when timestamp exists."""
        output = tmp_path / "report.html"
        feed = _minimal_feed()
        feed["output"] = output

        change_tracking = {
            "192.0.2.0/24": {
                "geofeed_changed_at": "2025-01-15T08:30:00Z",
                "providers": {},
            }
        }

        generate_html(
            _minimal_results(), _minimal_stats(),
            has_mm=True, has_ip=False, has_i2l=False, has_dbip=False, has_iplocate=False,
            feed=feed, change_tracking=change_tracking,
        )
        html = output.read_text()
        # Should contain the ISO timestamp in a title attribute
        assert "2025-01-15T08:30:00Z" in html
        # Should contain "changed" text
        assert "changed" in html

    def test_no_change_text_when_geofeed_changed_at_is_none(self, tmp_path):
        """Prefix row should not show change text when geofeed_changed_at is None."""
        output = tmp_path / "report.html"
        feed = _minimal_feed()
        feed["output"] = output

        change_tracking = {
            "192.0.2.0/24": {
                "geofeed_changed_at": None,
                "providers": {},
            }
        }

        generate_html(
            _minimal_results(), _minimal_stats(),
            has_mm=True, has_ip=False, has_i2l=False, has_dbip=False, has_iplocate=False,
            feed=feed, change_tracking=change_tracking,
        )
        html = output.read_text()
        # Find prefix row
        prefix_row_match = re.search(r'class="prefix-row".*?</tr>', html, re.DOTALL)
        assert prefix_row_match is not None
        prefix_row = prefix_row_match.group()
        # Should not contain "changed ... ago" text
        assert "changed" not in prefix_row

    def test_no_separate_last_changed_column(self, tmp_path):
        """There should be no separate 'Last Changed' column header."""
        output = tmp_path / "report.html"
        feed = _minimal_feed()
        feed["output"] = output

        change_tracking = {
            "192.0.2.0/24": {
                "geofeed_changed_at": "2025-01-15T08:30:00Z",
                "providers": {},
            }
        }

        generate_html(
            _minimal_results(), _minimal_stats(),
            has_mm=True, has_ip=False, has_i2l=False, has_dbip=False, has_iplocate=False,
            feed=feed, change_tracking=change_tracking,
        )
        html = output.read_text()
        assert "Last Changed" not in html
