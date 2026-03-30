"""Tests for date_utils.py period computation functions."""

import datetime
from unittest.mock import patch

import pytest

from utils.date_utils import (
    get_current_month,
    get_last_n_periods,
    get_previous_month,
    get_previous_week,
    get_yesterday,
)


class TestGetYesterday:
    def test_returns_yesterday(self):
        fake_today = datetime.date(2025, 3, 15)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            mock_dt.timedelta = datetime.timedelta
            assert get_yesterday() == "2025-03-14"

    def test_year_boundary(self):
        fake_today = datetime.date(2025, 1, 1)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            mock_dt.timedelta = datetime.timedelta
            assert get_yesterday() == "2024-12-31"


class TestGetPreviousWeek:
    def test_mid_week(self):
        # Wednesday 2025-03-12 → previous week Mon 2025-03-03 to Sun 2025-03-09
        fake_today = datetime.date(2025, 3, 12)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            mock_dt.timedelta = datetime.timedelta
            start, end = get_previous_week()
            assert start == "2025-03-03"
            assert end == "2025-03-09"

    def test_on_monday(self):
        # Monday 2025-03-10 → previous week Mon 2025-03-03 to Sun 2025-03-09
        fake_today = datetime.date(2025, 3, 10)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            mock_dt.timedelta = datetime.timedelta
            start, end = get_previous_week()
            assert start == "2025-03-03"
            assert end == "2025-03-09"

    def test_year_boundary(self):
        # Wednesday 2025-01-01 → previous week Mon 2024-12-23 to Sun 2024-12-29
        fake_today = datetime.date(2025, 1, 1)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            mock_dt.timedelta = datetime.timedelta
            start, end = get_previous_week()
            assert start == "2024-12-23"
            assert end == "2024-12-29"


class TestGetPreviousMonth:
    def test_mid_year(self):
        fake_today = datetime.date(2025, 6, 15)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            mock_dt.timedelta = datetime.timedelta
            assert get_previous_month() == "2025-05"

    def test_january(self):
        fake_today = datetime.date(2025, 1, 10)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            mock_dt.timedelta = datetime.timedelta
            assert get_previous_month() == "2024-12"


class TestGetCurrentMonth:
    def test_returns_current_month(self):
        fake_today = datetime.date(2025, 7, 20)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            assert get_current_month() == "2025-07"


class TestGetLastNPeriods:
    def test_daily(self):
        fake_today = datetime.date(2025, 3, 5)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            mock_dt.timedelta = datetime.timedelta
            result = get_last_n_periods("DAILY", 3)
            assert result == ["2025-03-03", "2025-03-04", "2025-03-05"]

    def test_daily_across_month_boundary(self):
        fake_today = datetime.date(2025, 3, 1)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            mock_dt.timedelta = datetime.timedelta
            result = get_last_n_periods("DAILY", 3)
            assert result == ["2025-02-27", "2025-02-28", "2025-03-01"]

    def test_weekly(self):
        # Wednesday 2025-03-12 → this Monday is 2025-03-10
        fake_today = datetime.date(2025, 3, 12)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            mock_dt.timedelta = datetime.timedelta
            result = get_last_n_periods("WEEKLY", 3)
            assert result == ["2025-02-24", "2025-03-03", "2025-03-10"]

    def test_monthly(self):
        fake_today = datetime.date(2025, 3, 15)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            result = get_last_n_periods("MONTHLY", 4)
            assert result == ["2024-12", "2025-01", "2025-02", "2025-03"]

    def test_monthly_across_year_boundary(self):
        fake_today = datetime.date(2025, 2, 1)
        with patch("utils.date_utils.datetime") as mock_dt:
            mock_dt.date.today.return_value = fake_today
            result = get_last_n_periods("MONTHLY", 3)
            assert result == ["2024-12", "2025-01", "2025-02"]

    def test_invalid_granularity(self):
        with pytest.raises(ValueError, match="Unknown granularity"):
            get_last_n_periods("HOURLY", 5)
