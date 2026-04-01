"""Cost query service — aggregation, filtering, and summary logic."""

import calendar
import datetime
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from models.cost_record import CostRecord
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

        Uses a single range query for all daily records in the current month
        instead of querying each day individually.
        """
        today = datetime.date.today()
        current_month = get_current_month()
        yesterday = get_yesterday()

        # Single range query: all daily records for the current month
        month_start = f"{current_month}-01"
        month_end = f"{current_month}-{calendar.monthrange(today.year, today.month)[1]:02d}"
        daily_records = self._cost_repo.query_by_gran_period_range(
            "DAILY", month_start, month_end
        )

        # Compute today (yesterday's data) and MTD from the same result set
        today_usd = Decimal("0")
        today_brl = Decimal("0")
        mtd_usd = Decimal("0")
        mtd_brl = Decimal("0")
        for r in daily_records:
            mtd_usd += r.amount_usd
            mtd_brl += r.amount_brl
            if r.period == yesterday:
                today_usd += r.amount_usd
                today_brl += r.amount_brl

        # Previous month total — single query
        prev_month = get_previous_month()
        prev_records = self._cost_repo.query_by_gran_period("MONTHLY", prev_month)
        prev_usd = sum(r.amount_usd for r in prev_records)
        prev_brl = sum(r.amount_brl for r in prev_records)

        # Forecast: MTD spend / days elapsed * days in month
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

        confidence = round(min(days_elapsed / days_in_month, 1.0), 2)

        return {
            "today_usd": today_usd,
            "today_brl": today_brl,
            "mtd_usd": mtd_usd,
            "mtd_brl": mtd_brl,
            "prev_month_usd": prev_usd,
            "prev_month_brl": prev_brl,
            "forecast_usd": forecast_usd,
            "forecast_brl": forecast_brl,
            "forecast_method": "linear_projection",
            "forecast_confidence": confidence,
        }

    def get_service_breakdown(
        self, granularity: str, period: str
    ) -> list[ServiceBreakdown]:
        """Query by granularity+period, aggregate by service, compute percentages."""
        records = self._cost_repo.query_by_gran_period(granularity, period)
        return self._aggregate_by_service(records)

    def get_service_breakdown_range(
        self, granularity: str, period_start: str, period_end: str
    ) -> dict[str, list[ServiceBreakdown]]:
        """Query a range of periods and return service breakdowns grouped by period.

        Returns a dict like {"2026-03-25": [...], "2026-03-26": [...], ...}
        """
        records = self._cost_repo.query_by_gran_period_range(
            granularity, period_start, period_end
        )
        by_period: dict[str, list[CostRecord]] = defaultdict(list)
        for r in records:
            by_period[r.period].append(r)

        result = {}
        for period, period_records in sorted(by_period.items()):
            result[period] = self._aggregate_by_service(period_records)
        return result

    def _aggregate_by_service(self, records: list[CostRecord]) -> list[ServiceBreakdown]:
        """Aggregate records by service name and compute percentages."""
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
        """Return aggregated totals for the last n periods using a single range query."""
        periods = get_last_n_periods(granularity, n)
        if not periods:
            return []

        period_start = periods[0]
        period_end = periods[-1]

        records = self._cost_repo.query_by_gran_period_range(
            granularity, period_start, period_end
        )

        # Group by period and aggregate
        by_period: dict[str, dict] = {}
        for r in records:
            if r.period not in by_period:
                by_period[r.period] = {"usd": Decimal("0"), "brl": Decimal("0")}
            by_period[r.period]["usd"] += r.amount_usd
            by_period[r.period]["brl"] += r.amount_brl

        # Return in chronological order, including periods with no data
        trend = []
        for period in periods:
            totals = by_period.get(period, {"usd": Decimal("0"), "brl": Decimal("0")})
            trend.append({
                "period": period,
                "total_usd": totals["usd"],
                "total_brl": totals["brl"],
            })
        return trend

    def get_account_breakdown(self, granularity: str, period: str) -> list[dict]:
        """Aggregate costs by account_id for a given granularity and period."""
        records = self._cost_repo.query_by_gran_period(granularity, period)
        agg: dict[str, dict] = {}
        for r in records:
            aid = r.account_id or "unknown"
            if aid not in agg:
                agg[aid] = {"usd": Decimal("0"), "brl": Decimal("0")}
            agg[aid]["usd"] += r.amount_usd
            agg[aid]["brl"] += r.amount_brl

        total_usd = sum(v["usd"] for v in agg.values())
        result = []
        for acct, amounts in agg.items():
            pct = (
                (amounts["usd"] / total_usd * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if total_usd > 0 else Decimal("0")
            )
            result.append({
                "account_id": acct,
                "amount_usd": amounts["usd"],
                "amount_brl": amounts["brl"],
                "percentage_of_total": pct,
            })
        result.sort(key=lambda x: x["amount_usd"], reverse=True)
        return result
