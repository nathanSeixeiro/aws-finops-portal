"""Lambda handler for GET /trend endpoint."""

import os

from repositories.budget_repository import BudgetRepository
from repositories.cost_record_repository import CostRecordRepository
from services.cost_query_service import CostQueryService
from utils.auth import validate_api_key
from utils.aws_client import get_dynamodb_resource
from utils.response import error, success


def handler(event, context):
    """Return cost trend for the last n periods at a given granularity."""
    if not validate_api_key(event):
        return error("Unauthorized", 401)

    params = event.get("queryStringParameters") or {}
    granularity = params.get("granularity")

    if not granularity:
        return error("Missing required query parameter: granularity", 400)

    try:
        n = int(params.get("n", 30))
    except (TypeError, ValueError):
        return error("Parameter 'n' must be an integer", 400)

    dynamodb = get_dynamodb_resource()
    cost_table = dynamodb.Table(os.environ.get("COST_RECORDS_TABLE", "costwatch-cost-records"))
    budget_table = dynamodb.Table(os.environ.get("BUDGETS_TABLE", "costwatch-budgets"))

    cost_repo = CostRecordRepository(cost_table)
    budget_repo = BudgetRepository(budget_table)
    query_svc = CostQueryService(cost_repo, budget_repo)

    trend = query_svc.get_trend(granularity, n)
    return success(trend)
