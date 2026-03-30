"""Lambda handler for cost data ingestion triggered by EventBridge."""

import logging
import os

from repositories.cost_record_repository import CostRecordRepository
from services.cost_ingestion_service import CostIngestionService
from services.currency_service import CurrencyService
from utils.aws_client import get_ce_client, get_dynamodb_resource, get_ssm_client

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def handler(event, context):
    """Parse EventBridge event and delegate to CostIngestionService."""
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
    result = ingestion_svc.ingest(granularity)

    logger.info("Ingestion result for %s: %s", granularity, result)
    return result
