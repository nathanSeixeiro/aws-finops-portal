"""Date utility functions for period computation across granularities."""

import datetime


def get_yesterday() -> str:
    """Return yesterday's date as YYYY-MM-DD string."""
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    return yesterday.isoformat()


def get_previous_week() -> tuple[str, str]:
    """Return (monday, sunday) of the previous ISO week as YYYY-MM-DD strings."""
    today = datetime.date.today()
    # ISO weekday: Monday=1, Sunday=7
    days_since_monday = today.weekday()  # Monday=0
    this_monday = today - datetime.timedelta(days=days_since_monday)
    prev_monday = this_monday - datetime.timedelta(weeks=1)
    prev_sunday = prev_monday + datetime.timedelta(days=6)
    return prev_monday.isoformat(), prev_sunday.isoformat()


def get_previous_month() -> str:
    """Return previous month as YYYY-MM string."""
    today = datetime.date.today()
    first_of_current = today.replace(day=1)
    last_of_prev = first_of_current - datetime.timedelta(days=1)
    return last_of_prev.strftime("%Y-%m")


def get_current_month() -> str:
    """Return current month as YYYY-MM string."""
    return datetime.date.today().strftime("%Y-%m")


def get_last_n_periods(granularity: str, n: int) -> list[str]:
    """Return last n period strings for the given granularity, oldest first.

    - DAILY: last n days as YYYY-MM-DD
    - WEEKLY: last n ISO week start dates (Mondays) as YYYY-MM-DD
    - MONTHLY: last n months as YYYY-MM
    """
    today = datetime.date.today()

    if granularity == "DAILY":
        return [
            (today - datetime.timedelta(days=i)).isoformat()
            for i in range(n - 1, -1, -1)
        ]

    if granularity == "WEEKLY":
        # Current week's Monday
        this_monday = today - datetime.timedelta(days=today.weekday())
        return [
            (this_monday - datetime.timedelta(weeks=i)).isoformat()
            for i in range(n - 1, -1, -1)
        ]

    if granularity == "MONTHLY":
        periods: list[str] = []
        year, month = today.year, today.month
        for _ in range(n):
            periods.append(f"{year:04d}-{month:02d}")
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        periods.reverse()
        return periods

    raise ValueError(f"Unknown granularity: {granularity}")
