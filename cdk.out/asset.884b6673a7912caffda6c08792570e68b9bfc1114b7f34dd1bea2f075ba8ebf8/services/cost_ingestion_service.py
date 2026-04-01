"""Cost ingestion service — fetches data from Cost Explorer and stores in DynamoDB."""

import calendar
import datetime
import logging
from decimal import Decimal

from models.cost_record import CostRecord
from repositories.cost_record_repository import CostRecordRepository
from services.currency_service import CurrencyService
from utils.date_utils import get_previous_month, get_previous_week, get_yesterday

logger = logging.getLogger(__name__)

# TTL durations in seconds
_TTL_DAILY = 365 * 24 * 60 * 60          # 365 days
_TTL_WEEKLY = 2 * 365 * 24 * 60 * 60     # 2 years
_TTL_MONTHLY = 5 * 365 * 24 * 60 * 60    # 5 years


class CostIngestionService:
    """Orchestrates cost data ingestion for all granularities.

    Fetches cost data from AWS Cost Explorer, converts to BRL,
    sets TTL, and stores each record via the repository.
    """

    def __init__(
        self,
        cost_repo: CostRecordRepository,
        currency_svc: CurrencyService,
        ce_client=None,
    ) -> None:
        self._cost_repo = cost_repo
        self._currency_svc = currency_svc
        self._ce = ce_client

    def ingest(self, granularity: str) -> dict:
        """Fetch cost data from Cost Explorer, convert to BRL, store in DynamoDB."""
        period_start, period_end = self._compute_period(granularity)

        try:
            rate = self._currency_svc.get_exchange_rate()
            costs = self._fetch_costs(granularity, period_start, period_end)
        except Exception:
            logger.error(
                "Failed to ingest %s costs for period %s–%s",
                granularity,
                period_start,
                period_end,
                exc_info=True,
            )
            return {"status": "error", "records": 0}

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ttl = self._compute_ttl(granularity)

        for record in costs:
            record.amount_brl = self._currency_svc.convert(record.amount_usd, rate)
            record.exchange_rate = rate
            record.ingested_at = now
            record.ttl = ttl
            # period stored is the start date for DAILY/WEEKLY, YYYY-MM for MONTHLY
            record.period = period_start if granularity != "MONTHLY" else period_start
            record.period_end = period_end
            record.granularity = granularity
            record.pk = (
                f"ACCOUNT#{record.account_id}#GRAN#{granularity}#PERIOD#{record.period}"
            )
            record.sk = f"SERVICE#{record.service_name}"
            self._cost_repo.put(record)

        return {"status": "ok", "records": len(costs)}

    def ingest_day(self, day: str) -> dict:
        """Ingest a specific day's cost data (for backfill)."""
        granularity = "DAILY"
        try:
            rate = self._currency_svc.get_exchange_rate()
            costs = self._fetch_costs(granularity, day, day)
        except Exception:
            logger.error("Failed to ingest DAILY costs for %s", day, exc_info=True)
            return {"status": "error", "records": 0}

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ttl = self._compute_ttl(granularity)

        for record in costs:
            record.amount_brl = self._currency_svc.convert(record.amount_usd, rate)
            record.exchange_rate = rate
            record.ingested_at = now
            record.ttl = ttl
            record.period = day
            record.period_end = day
            record.granularity = granularity
            record.pk = f"ACCOUNT#{record.account_id}#GRAN#{granularity}#PERIOD#{day}"
            record.sk = f"SERVICE#{record.service_name}"
            self._cost_repo.put(record)

        return {"status": "ok", "records": len(costs)}

    def ingest_month(self, year_month: str) -> dict:
        """Ingest a specific month's cost data (for backfill). year_month is YYYY-MM."""
        granularity = "MONTHLY"
        year, month = int(year_month[:4]), int(year_month[5:7])
        last_day = calendar.monthrange(year, month)[1]
        period_end = f"{year_month}-{last_day:02d}"

        try:
            rate = self._currency_svc.get_exchange_rate()
            costs = self._fetch_costs(granularity, year_month, period_end)
        except Exception:
            logger.error("Failed to ingest MONTHLY costs for %s", year_month, exc_info=True)
            return {"status": "error", "records": 0}

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ttl = self._compute_ttl(granularity)

        for record in costs:
            record.amount_brl = self._currency_svc.convert(record.amount_usd, rate)
            record.exchange_rate = rate
            record.ingested_at = now
            record.ttl = ttl
            record.period = year_month
            record.period_end = period_end
            record.granularity = granularity
            record.pk = f"ACCOUNT#{record.account_id}#GRAN#{granularity}#PERIOD#{year_month}"
            record.sk = f"SERVICE#{record.service_name}"
            self._cost_repo.put(record)

        return {"status": "ok", "records": len(costs)}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_period(granularity: str) -> tuple[str, str]:
        """Return (period_start, period_end) based on granularity."""
        if granularity == "DAILY":
            yesterday = get_yesterday()
            return yesterday, yesterday

        if granularity == "WEEKLY":
            return get_previous_week()  # (monday, sunday)

        if granularity == "MONTHLY":
            prev = get_previous_month()  # YYYY-MM
            year, month = int(prev[:4]), int(prev[5:7])
            last_day = calendar.monthrange(year, month)[1]
            return prev, f"{prev}-{last_day:02d}"

        raise ValueError(f"Unknown granularity: {granularity}")

    @staticmethod
    def _compute_ttl(granularity: str) -> int:
        """Return a Unix epoch TTL based on granularity."""
        now_epoch = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        ttl_map = {
            "DAILY": _TTL_DAILY,
            "WEEKLY": _TTL_WEEKLY,
            "MONTHLY": _TTL_MONTHLY,
        }
        return now_epoch + ttl_map[granularity]

    def _fetch_costs(
        self, granularity: str, period_start: str, period_end: str
    ) -> list[CostRecord]:
        """Call Cost Explorer get_cost_and_usage and return partial CostRecord objects.

        The caller is responsible for filling in amount_brl, exchange_rate,
        ingested_at, ttl, pk, and sk before persisting.
        """
        # CE expects exclusive end date — add one day
        if granularity == "MONTHLY":
            # period_end is like "2024-03-31", need next day
            end_dt = datetime.date.fromisoformat(period_end) + datetime.timedelta(days=1)
            ce_start = f"{period_start}-01"
            ce_end = end_dt.isoformat()
        else:
            end_dt = datetime.date.fromisoformat(period_end) + datetime.timedelta(days=1)
            ce_start = period_start
            ce_end = end_dt.isoformat()

        resp = self._ce.get_cost_and_usage(
            TimePeriod={"Start": ce_start, "End": ce_end},
            Granularity=granularity if granularity != "WEEKLY" else "DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
            ],
        )

        records: list[CostRecord] = []
        for result_by_time in resp.get("ResultsByTime", []):
            for group in result_by_time.get("Groups", []):
                service_name = group["Keys"][0]
                account_id = group["Keys"][1] if len(group["Keys"]) > 1 else "default"
                amount_str = group["Metrics"]["UnblendedCost"]["Amount"]
                amount_usd = Decimal(amount_str).quantize(Decimal("0.0001"))

                records.append(
                    CostRecord(
                        pk="",  # filled by caller
                        sk="",  # filled by caller
                        account_id=account_id,
                        account_alias=account_id,
                        period=period_start,
                        period_end=period_end,
                        granularity=granularity,
                        service_name=service_name,
                        amount_usd=amount_usd,
                        amount_brl=Decimal("0"),  # filled by caller
                        exchange_rate=Decimal("0"),  # filled by caller
                        tags={},
                        ingested_at="",  # filled by caller
                        ttl=0,  # filled by caller
                    )
                )

        # Aggregate if WEEKLY (CE returns daily rows, we want weekly totals)
        if granularity == "WEEKLY" and len(resp.get("ResultsByTime", [])) > 1:
            aggregated: dict[str, CostRecord] = {}
            for r in records:
                if r.service_name in aggregated:
                    aggregated[r.service_name].amount_usd += r.amount_usd
                else:
                    aggregated[r.service_name] = r
            records = list(aggregated.values())

        return records
