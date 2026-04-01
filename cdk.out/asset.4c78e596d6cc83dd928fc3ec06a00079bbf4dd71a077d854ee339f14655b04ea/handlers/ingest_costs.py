"""Lambda handler for cost data ingestion triggered by EventBridge.

After ingesting cost data, rebuilds the dashboard snapshot so the
/dashboard endpoint always serves fresh pre-computed data.
"""

import logging
import os

from repositories.cost_record_repository import CostRecordRepository
from services.cost_ingestion_service import CostIngestionService
from services.currency_service import CurrencyService
from services.dashboard_snapshot_service import DashboardSnapshotService
from utils.aws_client import get_ce_client, get_dynamodb_resource, get_ssm_client

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def handler(event, context):
    """Parse EventBridge event, ingest costs, then rebuild dashboard snapshot."""
    detail = event.get("detail", {})
    granularity = detail.get("granularity")

    if granularity not in ("DAILY", "WEEKLY", "MONTHLY"):
        logger.error("Invalid or missing granularity in event detail: %s", granularity)
        return {"status": "error", "message": f"Invalid granularity: {granularity}"}

    table_name = os.environ.get("COST_RECORDS_TABLE", "costwatch-cost-records")
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)

    cost_repo = CostRecordRepository(table)
    currency_svc = CurrencyService(get_ssm_client())
    ce_client = get_ce_client()

    ingestion_svc = CostIngestionService(cost_repo, currency_svc, ce_client)

    # Support backfill: {"detail": {"granularity": "DAILY", "backfill_days": 30}}
    backfill_days = detail.get("backfill_days")
    if backfill_days and granularity == "DAILY":
        import datetime
        total = 0
        for i in range(int(backfill_days), 0, -1):
            day = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
            result = ingestion_svc.ingest_day(day)
            total += result.get("records", 0)
        ingestion_result = {"status": "ok", "records": total}
    else:
        ingestion_result = ingestion_svc.ingest(granularity)

    # Rebuild dashboard snapshot after ingestion
    try:
        snapshot_svc = DashboardSnapshotService(cost_repo, table)
        snapshot_svc.build_and_store()
        logger.info("Dashboard snapshot rebuilt after %s ingestion", granularity)
    except Exception:
        logger.error("Failed to rebuild dashboard snapshot", exc_info=True)

    logger.info("Ingestion result for %s: %s", granularity, ingestion_result)
    return ingestion_result
