"""Unit tests for format_relative_time function."""

from datetime import datetime, timedelta, timezone

from geofeed_monitor.timestamps import format_relative_time


class TestFormatRelativeTime:
    """Tests for format_relative_time boundary conditions and singular/plural forms."""

    def _iso(self, dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_just_now_zero_seconds(self):
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        ts = self._iso(now)
        assert format_relative_time(ts, now) == "just now"

    def test_just_now_59_seconds(self):
        now = datetime(2025, 1, 15, 12, 0, 59, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(seconds=59))
        assert format_relative_time(ts, now) == "just now"

    def test_1_minute_ago_at_60_seconds(self):
        now = datetime(2025, 1, 15, 12, 1, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(seconds=60))
        assert format_relative_time(ts, now) == "1 minute ago"

    def test_minutes_plural(self):
        now = datetime(2025, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(minutes=30))
        assert format_relative_time(ts, now) == "30 minutes ago"

    def test_59_minutes_ago(self):
        now = datetime(2025, 1, 15, 12, 59, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(minutes=59))
        assert format_relative_time(ts, now) == "59 minutes ago"

    def test_1_hour_ago_at_60_minutes(self):
        now = datetime(2025, 1, 15, 13, 0, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(hours=1))
        assert format_relative_time(ts, now) == "1 hour ago"

    def test_hours_plural(self):
        now = datetime(2025, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(hours=5))
        assert format_relative_time(ts, now) == "5 hours ago"

    def test_23_hours_ago(self):
        now = datetime(2025, 1, 16, 11, 0, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(hours=23))
        assert format_relative_time(ts, now) == "23 hours ago"

    def test_1_day_ago_at_24_hours(self):
        now = datetime(2025, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(hours=24))
        assert format_relative_time(ts, now) == "1 day ago"

    def test_days_plural(self):
        now = datetime(2025, 1, 25, 12, 0, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(days=10))
        assert format_relative_time(ts, now) == "10 days ago"

    def test_29_days_ago(self):
        now = datetime(2025, 2, 13, 12, 0, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(days=29))
        assert format_relative_time(ts, now) == "29 days ago"

    def test_1_month_ago_at_30_days(self):
        now = datetime(2025, 2, 14, 12, 0, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(days=30))
        assert format_relative_time(ts, now) == "1 month ago"

    def test_months_plural(self):
        now = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(days=180))
        assert format_relative_time(ts, now) == "6 months ago"

    def test_1_year_ago_at_365_days(self):
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(days=365))
        assert format_relative_time(ts, now) == "1 year ago"

    def test_years_plural(self):
        now = datetime(2028, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        ts = self._iso(now - timedelta(days=730))
        assert format_relative_time(ts, now) == "2 years ago"

    def test_iso_with_z_suffix(self):
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert format_relative_time("2025-01-15T11:00:00Z", now) == "1 hour ago"

    def test_iso_with_offset(self):
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert format_relative_time("2025-01-15T11:00:00+00:00", now) == "1 hour ago"
