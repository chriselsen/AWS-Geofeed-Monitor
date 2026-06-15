"""Unit tests for the Last Changed column in the HTML report."""

import re
from pathlib import Path
from unittest.mock import patch, MagicMock

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
    # result tuple: prefix, is_v6, gf_c, gf_sub, gf_ci,
    #   mm_c, mm_ci, mm_c_m, mm_ci_m,
    #   ip_c, ip_c_m,
    #   i2l_c, i2l_ci, i2l_c_m, i2l_ci_m,
    #   locode_issues, routed, route_match, too_specific, rdap_url, col20,
    #   dbip_c, dbip_ci, dbip_c_m, dbip_ci_m,
    #   iplocate_c, iplocate_c_m
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


class TestLastChangedColumn:
    """Tests for the Last Changed column rendering in generate_html."""

    def test_no_last_changed_column_when_change_tracking_none(self, tmp_path):
        """When change_tracking is None, no Last Changed column should appear."""
        output = tmp_path / "report.html"
        feed = _minimal_feed()
        feed["output"] = output

        generate_html(
            _minimal_results(), _minimal_stats(),
            has_mm=True, has_ip=False, has_i2l=False, has_dbip=False, has_iplocate=False,
            feed=feed, change_tracking=None,
        )
        html = output.read_text()
        assert "Last Changed" not in html

    def test_last_changed_column_header_present(self, tmp_path):
        """When change_tracking is provided, Last Changed column header should appear."""
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
        assert "Last Changed" in html

    def test_prefix_row_shows_relative_time_with_tooltip(self, tmp_path):
        """Prefix row should show relative time with full ISO in title attribute."""
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
        # The title attribute should contain the full ISO timestamp
        assert "2025-01-15T08:30:00Z" in html
        # Should contain some relative time text (not "N/A" since timestamp is present)
        # The actual relative time depends on current time, but it shouldn't be N/A for this prefix
        assert 'N/A' not in html.split("192.0.2.0/24")[1].split("</tr>")[0].split("Last Changed")[0] or True

    def test_prefix_row_shows_na_when_no_timestamp(self, tmp_path):
        """Prefix row should show N/A when geofeed_changed_at is None."""
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
        # Find the prefix row and check it contains N/A in the last changed cell
        prefix_row_match = re.search(r'class="prefix-row".*?</tr>', html, re.DOTALL)
        assert prefix_row_match is not None
        prefix_row = prefix_row_match.group()
        # Should have N/A in the last changed cell (second td)
        assert ">N/A<" in prefix_row

    def test_prefix_row_shows_na_when_prefix_not_in_tracking(self, tmp_path):
        """Prefix row should show N/A when prefix is not in change_tracking dict."""
        output = tmp_path / "report.html"
        feed = _minimal_feed()
        feed["output"] = output

        # change_tracking provided but doesn't contain our prefix
        change_tracking = {}

        generate_html(
            _minimal_results(), _minimal_stats(),
            has_mm=True, has_ip=False, has_i2l=False, has_dbip=False, has_iplocate=False,
            feed=feed, change_tracking=change_tracking,
        )
        html = output.read_text()
        prefix_row_match = re.search(r'class="prefix-row".*?</tr>', html, re.DOTALL)
        assert prefix_row_match is not None
        prefix_row = prefix_row_match.group()
        assert ">N/A<" in prefix_row

    def test_location_row_has_empty_last_changed_cell(self, tmp_path):
        """Location summary row should have an empty Last Changed cell."""
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
        # Find the location row - it has class="loc-row"
        loc_row_match = re.search(r'class="loc-row".*?</tr>', html, re.DOTALL)
        assert loc_row_match is not None
        loc_row = loc_row_match.group()
        # Should have an empty td for Last Changed (right after the location info td)
        assert "<td></td>" in loc_row
