"""Lambda handler for GET /dashboard — returns pre-computed snapshot.

Single DynamoDB GetItem call. No computation at request time.
"""

import os

from repositories.cost_record_repository import CostRecordRepository
from services.dashboard_snapshot_service import DashboardSnapshotService
from utils.auth import validate_api_key
from utils.aws_client import get_dynamodb_resource
from utils.response import error, success


def handler(event, context):
    """Return the pre-computed dashboard snapshot."""
    if not validate_api_key(event):
        return error("Unauthorized", 401)

    dynamodb = get_dynamodb_resource()
    cost_table = dynamodb.Table(os.environ.get("COST_RECORDS_TABLE", "costwatch-cost-records"))

    cost_repo = CostRecordRepository(cost_table)
    snapshot_svc = DashboardSnapshotService(cost_repo, cost_table)

    data = snapshot_svc.get_snapshot()
    if data is None:
        return error("No dashboard data available yet. Run ingestion first.", 404)

    return success(data)
