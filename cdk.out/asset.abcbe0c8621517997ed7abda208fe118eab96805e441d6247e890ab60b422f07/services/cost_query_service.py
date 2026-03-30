"""Cost query service — aggregation, filtering, and summary logic."""

import calendar
import datetime
from decimal import ROUND_HALF_UP, Decimal

from models.service_breakdown import ServiceBreakdown
from repositories.budget_repository import BudgetRepository
from repositories.cost_record_repository import CostRecordRepository
from utils.date_utils import (
    get_current_month,
    get_last_n_periods,
    get_previous_month,
    get_yesterday,
)


class CostQueryService:
    """Reads cost data from DynamoDB and returns aggregated views."""

    def __init__(
        self,
        cost_repo: CostRecordRepository,
        budget_repo: BudgetRepository,
    ) -> None:
        self._cost_repo = cost_repo
        self._budget_repo = budget_repo

    def get_summary(self) -> dict:
        """Return today's cost, MTD total, previous month total, and forecast.

        All amounts are returned in both USD and BRL.
        """
        # Today's cost (yesterday's ingested daily record)
        yesterday = get_yesterday()
        today_records = self._cost_repo.query_by_gran_period("DAILY", yesterday)
        today_usd = sum(r.amount_usd for r in today_records)
        today_brl = sum(r.amount_brl for r in today_records)

        # Month-to-date: sum all daily records for the current month
        current_month = get_current_month()
        daily_periods = get_last_n_periods("DAILY", 31)
        mtd_usd = Decimal("0")
        mtd_brl = Decimal("0")
        for period in daily_periods:
            if period.startswith(current_month):
                records = self._cost_repo.query_by_gran_period("DAILY", period)
                mtd_usd += sum(r.amount_usd for r in records)
                mtd_brl += sum(r.amount_brl for r in records)

        # Previous month total
        prev_month = get_previous_month()
        prev_records = self._cost_repo.query_by_gran_period("MONTHLY", prev_month)
        prev_usd = sum(r.amount_usd for r in prev_records)
        prev_brl = sum(r.amount_brl for r in prev_records)

        # Simple forecast: MTD spend / days elapsed * days in month
        today = datetime.date.today()
        days_elapsed = today.day
        days_in_month = calendar.monthrange(today.year, today.month)[1]
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

        return {
            "today_usd": today_usd,
            "today_brl": today_brl,
            "mtd_usd": mtd_usd,
            "mtd_brl": mtd_brl,
            "prev_month_usd": prev_usd,
            "prev_month_brl": prev_brl,
            "forecast_usd": forecast_usd,
            "forecast_brl": forecast_brl,
        }

    def get_service_breakdown(
        self, granularity: str, period: str
    ) -> list[ServiceBreakdown]:
        """Query by granularity+period, aggregate by service, compute percentages."""
        records = self._cost_repo.query_by_gran_period(granularity, period)

        # Aggregate by service name
        agg: dict[str, dict] = {}
        for r in records:
            if r.service_name not in agg:
                agg[r.service_name] = {"usd": Decimal("0"), "brl": Decimal("0")}
            agg[r.service_name]["usd"] += r.amount_usd
            agg[r.service_name]["brl"] += r.amount_brl

        total_usd = sum(v["usd"] for v in agg.values())

        breakdowns = []
        for svc, amounts in agg.items():
            pct = (
                (amounts["usd"] / total_usd * 100).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if total_usd > 0
                else Decimal("0")
            )
            breakdowns.append(
                ServiceBreakdown(
                    service_name=svc,
                    amount_usd=amounts["usd"],
                    amount_brl=amounts["brl"],
                    percentage_of_total=pct,
                )
            )

        breakdowns.sort(key=lambda b: b.amount_usd, reverse=True)
        return breakdowns

    def get_trend(self, granularity: str, n: int) -> list[dict]:
        """Return aggregated totals for the last n periods."""
        periods = get_last_n_periods(granularity, n)
        trend = []
        for period in periods:
            records = self._cost_repo.query_by_gran_period(granularity, period)
            total_usd = sum(r.amount_usd for r in records)
            total_brl = sum(r.amount_brl for r in records)
            trend.append({
                "period": period,
                "total_usd": total_usd,
                "total_brl": total_brl,
            })
        return trend
