"""Lambda handler for GET /forecast endpoint."""

import os

from src.repositories.cost_record_repository import CostRecordRepository
from src.services.forecast_service import ForecastService
from src.utils.auth import validate_api_key
from src.utils.aws_client import get_dynamodb_resource
from src.utils.response import error, success


def handler(event, context):
    """Return projected monthly cost forecast."""
    if not validate_api_key(event):
        return error("Unauthorized", 401)

    dynamodb = get_dynamodb_resource()
    cost_table = dynamodb.Table(os.environ.get("COST_RECORDS_TABLE", "costwatch-cost-records"))

    cost_repo = CostRecordRepository(cost_table)
    forecast_svc = ForecastService(cost_repo)

    forecast = forecast_svc.get_forecast()
    return success(forecast)
