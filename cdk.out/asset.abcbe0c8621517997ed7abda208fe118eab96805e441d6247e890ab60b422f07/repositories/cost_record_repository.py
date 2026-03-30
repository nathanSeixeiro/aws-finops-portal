"""Repository for costwatch-cost-records DynamoDB table."""

from boto3.dynamodb.conditions import Key

from models.cost_record import CostRecord


class CostRecordRepository:
    """Encapsulates all DynamoDB access for the costwatch-cost-records table.

    Uses dependency injection — accepts a DynamoDB table resource in the constructor.
    """

    def __init__(self, table_resource) -> None:
        self._table = table_resource

    def put(self, record: CostRecord) -> None:
        """Store a CostRecord using the canonical key patterns.

        PK: ACCOUNT#{account_id}#GRAN#{granularity}#PERIOD#{period}
        SK: SERVICE#{service_name}
        """
        item = record.to_dynamodb_item()
        item["pk"] = f"ACCOUNT#{record.account_id}#GRAN#{record.granularity}#PERIOD#{record.period}"
        item["sk"] = f"SERVICE#{record.service_name}"
        self._table.put_item(Item=item)

    def query_by_gran_period(self, granularity: str, period: str) -> list[CostRecord]:
        """Query GSI gsi-gran-period for all records matching a granularity + period."""
        resp = self._table.query(
            IndexName="gsi-gran-period",
            KeyConditionExpression=Key("granularity").eq(granularity) & Key("period").eq(period),
        )
        return [CostRecord.from_dynamodb_item(item) for item in resp.get("Items", [])]

    def query_by_service_period(
        self, service: str, period_start: str, period_end: str
    ) -> list[CostRecord]:
        """Query GSI gsi-service-period with a sort-key range on period."""
        resp = self._table.query(
            IndexName="gsi-service-period",
            KeyConditionExpression=(
                Key("service_name").eq(service)
                & Key("period").between(period_start, period_end)
            ),
        )
        return [CostRecord.from_dynamodb_item(item) for item in resp.get("Items", [])]

    def query_by_account_gran(
        self, account_id: str, granularity: str, period_start: str, period_end: str
    ) -> list[CostRecord]:
        """Query GSI gsi-account-gran with composite SK range (granularity#period)."""
        sk_start = f"{granularity}#{period_start}"
        sk_end = f"{granularity}#{period_end}"
        resp = self._table.query(
            IndexName="gsi-account-gran",
            KeyConditionExpression=(
                Key("account_id").eq(account_id)
                & Key("granularity_period").between(sk_start, sk_end)
            ),
        )
        return [CostRecord.from_dynamodb_item(item) for item in resp.get("Items", [])]
