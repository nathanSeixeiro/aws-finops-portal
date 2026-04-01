"""Lambda handler for GET /services endpoint.

Supports both single-period and range queries:
- Single: ?granularity=DAILY&period=2026-03-25
- Range:  ?granularity=DAILY&period_start=2026-03-18&period_end=2026-03-25
"""

import os

from repositories.budget_repository import BudgetRepository
from repositories.cost_record_repository import CostRecordRepository
from services.cost_query_service import CostQueryService
from utils.auth import validate_api_key
from utils.aws_client import get_dynamodb_resource
from utils.response import error, success


def handler(event, context):
    """Return service breakdown for a given granularity and period (or range)."""
    if not validate_api_key(event):
        return error("Unauthorized", 401)

    params = event.get("queryStringParameters") or {}
    granularity = params.get("granularity")
    period = params.get("period")
    period_start = params.get("period_start")
    period_end = params.get("period_end")

    if not granularity:
        return error("Missing required query parameter: granularity", 400)

    if not period and not (period_start and period_end):
        return error(
            "Missing required query parameters: provide 'period' or both 'period_start' and 'period_end'",
            400,
        )

    dynamodb = get_dynamodb_resource()
    cost_table = dynamodb.Table(os.environ.get("COST_RECORDS_TABLE", "costwatch-cost-records"))
    budget_table = dynamodb.Table(os.environ.get("BUDGETS_TABLE", "costwatch-budgets"))

    cost_repo = CostRecordRepository(cost_table)
    budget_repo = BudgetRepository(budget_table)
    query_svc = CostQueryService(cost_repo, budget_repo)

    if period:
        # Single period — backward compatible
        breakdowns = query_svc.get_service_breakdown(granularity, period)
        return success([b.model_dump() for b in breakdowns])

    # Range query — returns {period: [breakdowns]}
    result = query_svc.get_service_breakdown_range(granularity, period_start, period_end)
    serialized = {
        p: [b.model_dump() for b in blist] for p, blist in result.items()
    }
    return success(serialized)
