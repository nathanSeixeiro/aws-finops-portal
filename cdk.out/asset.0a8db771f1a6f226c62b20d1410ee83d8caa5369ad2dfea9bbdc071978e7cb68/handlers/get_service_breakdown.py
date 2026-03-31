"""Lambda handler for GET /services endpoint."""

import os

from repositories.budget_repository import BudgetRepository
from repositories.cost_record_repository import CostRecordRepository
from services.cost_query_service import CostQueryService
from utils.auth import validate_api_key
from utils.aws_client import get_dynamodb_resource
from utils.response import error, success


def handler(event, context):
    """Return service breakdown for a given granularity and period."""
    if not validate_api_key(event):
        return error("Unauthorized", 401)

    params = event.get("queryStringParameters") or {}
    granularity = params.get("granularity")
    period = params.get("period")

    if not granularity or not period:
        return error("Missing required query parameters: granularity, period", 400)

    dynamodb = get_dynamodb_resource()
    cost_table = dynamodb.Table(os.environ.get("COST_RECORDS_TABLE", "costwatch-cost-records"))
    budget_table = dynamodb.Table(os.environ.get("BUDGETS_TABLE", "costwatch-budgets"))

    cost_repo = CostRecordRepository(cost_table)
    budget_repo = BudgetRepository(budget_table)
    query_svc = CostQueryService(cost_repo, budget_repo)

    breakdowns = query_svc.get_service_breakdown(granularity, period)
    return success([b.model_dump() for b in breakdowns])
