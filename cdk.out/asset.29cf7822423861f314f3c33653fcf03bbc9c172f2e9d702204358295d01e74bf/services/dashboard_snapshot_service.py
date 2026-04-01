"""Dashboard snapshot service — pre-computes all frontend data into a single DynamoDB item."""

import calendar
import datetime
import logging
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from repositories.cost_record_repository import CostRecordRepository
from utils.date_utils import get_current_month, get_last_n_periods, get_previous_month, get_yesterday

logger = logging.getLogger(__name__)


class DashboardSnapshotService:
    """Builds a complete dashboard snapshot and stores it in DynamoDB."""

    SNAPSHOT_PK = "SNAPSHOT#DASHBOARD"
    SNAPSHOT_SK = "LATEST"

    def __init__(self, cost_repo: CostRecordRepository, snapshot_table) -> None:
        self._cost_repo = cost_repo
        self._snapshot_table = snapshot_table

    def build_and_store(self) -> dict:
        """Compute the full dashboard payload and write it as a single item."""
        snapshot = self._build_snapshot()
        self._snapshot_table.put_item(Item={
            "pk": self.SNAPSHOT_PK,
            "sk": self.SNAPSHOT_SK,
            "data": snapshot,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        logger.info("Dashboard snapshot stored successfully")
        return snapshot

    def get_snapshot(self) -> dict | None:
        """Read the latest dashboard snapshot."""
        resp = self._snapshot_table.get_item(Key={
            "pk": self.SNAPSHOT_PK,
            "sk": self.SNAPSHOT_SK,
        })
        item = resp.get("Item")
        if not item:
            return None
        return item.get("data")

    def _build_snapshot(self) -> dict:
        """Compute all dashboard sections."""
        today = datetime.date.today()
        current_month = get_current_month()
        yesterday = get_yesterday()

        # --- KPIs: single range query for current month daily records ---
        month_start = f"{current_month}-01"
        month_end = f"{current_month}-{calendar.monthrange(today.year, today.month)[1]:02d}"
        daily_records = self._cost_repo.query_by_gran_period_range("DAILY", month_start, month_end)

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

        # Previous month
        prev_month = get_previous_month()
        prev_records = self._cost_repo.query_by_gran_period("MONTHLY", prev_month)
        prev_usd = sum(r.amount_usd for r in prev_records)
        prev_brl = sum(r.amount_brl for r in prev_records)

        # Forecast
        days_elapsed = today.day
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        if days_elapsed > 0:
            forecast_usd = (mtd_usd / days_elapsed * days_in_month).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            forecast_brl = (mtd_brl / days_elapsed * days_in_month).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        else:
            forecast_usd = Decimal("0")
            forecast_brl = Decimal("0")
        confidence = Decimal(str(round(min(days_elapsed / days_in_month, 1.0), 2)))

        # --- Trend: last 30 days ---
        daily_periods = get_last_n_periods("DAILY", 30)
        trend_records = self._cost_repo.query_by_gran_period_range("DAILY", daily_periods[0], daily_periods[-1])
        trend_by_period: dict[str, dict] = {}
        for r in trend_records:
            if r.period not in trend_by_period:
                trend_by_period[r.period] = {"usd": Decimal("0"), "brl": Decimal("0")}
            trend_by_period[r.period]["usd"] += r.amount_usd
            trend_by_period[r.period]["brl"] += r.amount_brl

        daily_trend = []
        for p in daily_periods:
            t = trend_by_period.get(p, {"usd": Decimal("0"), "brl": Decimal("0")})
            daily_trend.append({"period": p, "total_usd": t["usd"], "total_brl": t["brl"]})

        # --- Monthly trend: last 12 months ---
        monthly_periods = get_last_n_periods("MONTHLY", 12)
        monthly_records = self._cost_repo.query_by_gran_period_range("MONTHLY", monthly_periods[0], monthly_periods[-1])
        monthly_by_period: dict[str, dict] = {}
        for r in monthly_records:
            if r.period not in monthly_by_period:
                monthly_by_period[r.period] = {"usd": Decimal("0"), "brl": Decimal("0")}
            monthly_by_period[r.period]["usd"] += r.amount_usd
            monthly_by_period[r.period]["brl"] += r.amount_brl

        monthly_trend = []
        for p in monthly_periods:
            t = monthly_by_period.get(p, {"usd": Decimal("0"), "brl": Decimal("0")})
            monthly_trend.append({"period": p, "total_usd": t["usd"], "total_brl": t["brl"]})

        # --- Services breakdown (yesterday) ---
        yesterday_records = [r for r in daily_records if r.period == yesterday]
        services = self._aggregate_by_service(yesterday_records)

        # --- Accounts breakdown (yesterday) ---
        accounts = self._aggregate_by_account(yesterday_records)

        # --- Heatmap: last 8 days of service data ---
        heatmap_periods = []
        for i in range(8, 0, -1):
            d = today - datetime.timedelta(days=i)
            heatmap_periods.append(d.isoformat())

        heatmap_records = self._cost_repo.query_by_gran_period_range(
            "DAILY", heatmap_periods[0], heatmap_periods[-1]
        ) if heatmap_periods else []

        heatmap_by_period: dict[str, list] = defaultdict(list)
        for r in heatmap_records:
            heatmap_by_period[r.period].append(r)

        heatmap = {}
        for p in heatmap_periods:
            heatmap[p] = self._aggregate_by_service(heatmap_by_period.get(p, []))

        return {
            "summary": {
                "today_usd": today_usd, "today_brl": today_brl,
                "mtd_usd": mtd_usd, "mtd_brl": mtd_brl,
                "prev_month_usd": prev_usd, "prev_month_brl": prev_brl,
                "forecast_usd": forecast_usd, "forecast_brl": forecast_brl,
                "forecast_method": "linear_projection",
                "forecast_confidence": confidence,
            },
            "daily_trend": daily_trend,
            "monthly_trend": monthly_trend,
            "services": services,
            "accounts": accounts,
            "heatmap": heatmap,
        }

    @staticmethod
    def _aggregate_by_service(records) -> list[dict]:
        agg: dict[str, dict] = {}
        for r in records:
            if r.service_name not in agg:
                agg[r.service_name] = {"usd": Decimal("0"), "brl": Decimal("0")}
            agg[r.service_name]["usd"] += r.amount_usd
            agg[r.service_name]["brl"] += r.amount_brl
        total_usd = sum(v["usd"] for v in agg.values())
        result = []
        for svc, amounts in agg.items():
            pct = (amounts["usd"] / total_usd * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total_usd > 0 else Decimal("0")
            result.append({"service_name": svc, "amount_usd": amounts["usd"], "amount_brl": amounts["brl"], "percentage_of_total": pct})
        result.sort(key=lambda x: x["amount_usd"], reverse=True)
        return result

    @staticmethod
    def _aggregate_by_account(records) -> list[dict]:
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
            pct = (amounts["usd"] / total_usd * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total_usd > 0 else Decimal("0")
            result.append({"account_id": acct, "amount_usd": amounts["usd"], "amount_brl": amounts["brl"], "percentage_of_total": pct})
        result.sort(key=lambda x: x["amount_usd"], reverse=True)
        return result
