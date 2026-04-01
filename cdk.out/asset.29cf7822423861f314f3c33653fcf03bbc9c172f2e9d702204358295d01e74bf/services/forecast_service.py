"""Forecast service — projects current month's total based on daily spending rate."""

import calendar
import datetime
from decimal import ROUND_HALF_UP, Decimal

from repositories.cost_record_repository import CostRecordRepository
from utils.date_utils import get_current_month, get_last_n_periods


class ForecastService:
    """Generates a projected monthly cost based on MTD daily spending."""

    def __init__(self, cost_repo: CostRecordRepository) -> None:
        self._cost_repo = cost_repo

    def get_forecast(self) -> dict:
        """Calculate projected monthly cost: (MTD spend / days elapsed) * days in month.

        Returns both USD and BRL amounts along with method and confidence metadata.
        """
        today = datetime.date.today()
        days_elapsed = today.day
        days_in_month = calendar.monthrange(today.year, today.month)[1]

        current_month = get_current_month()
        daily_periods = get_last_n_periods("DAILY", 31)

        mtd_usd = Decimal("0")
        mtd_brl = Decimal("0")
        for period in daily_periods:
            if period.startswith(current_month):
                records = self._cost_repo.query_by_gran_period("DAILY", period)
                mtd_usd += sum(r.amount_usd for r in records)
                mtd_brl += sum(r.amount_brl for r in records)

        if days_elapsed > 0:
            forecast_usd = (mtd_usd / days_elapsed * days_in_month).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            forecast_brl = (mtd_brl / days_elapsed * days_in_month).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
        else:
            forecast_usd = Decimal("0")
            forecast_brl = Decimal("0")

        # Confidence is higher when more days of data are available
        confidence = round(min(days_elapsed / days_in_month, 1.0), 2)

        return {
            "forecast_usd": forecast_usd,
            "forecast_brl": forecast_brl,
            "method": "linear_projection",
            "confidence": confidence,
        }
