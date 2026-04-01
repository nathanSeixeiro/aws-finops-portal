"""Lambda handler for GET /summary endpoint.

Returns KPIs (today, MTD, prev month) and forecast in a single response,
eliminating the need for a separate /forecast call.
"""

import os

from repositories.budget_repository import BudgetRepository
from repositories.cost_record_repository import CostRecordRepository
from services.cost_query_service import CostQueryService
from utils.auth import validate_api_key
from utils.aws_client import get_dynamodb_resource
from utils.response import error, success


def handler(event, context):
    """Return cost summary with today, MTD, previous month, and forecast."""
    if not validate_api_key(event):
        return error("Unauthorized", 401)

    dynamodb = get_dynamodb_resource()
    cost_table = dynamodb.Table(os.environ.get("COST_RECORDS_TABLE", "costwatch-cost-records"))
    budget_table = dynamodb.Table(os.environ.get("BUDGETS_TABLE", "costwatch-budgets"))

    cost_repo = CostRecordRepository(cost_table)
    budget_repo = BudgetRepository(budget_table)
    query_svc = CostQueryService(cost_repo, budget_repo)

    summary = query_svc.get_summary()
    return success(summary)
