"""CostRecord Pydantic v2 model for the costwatch-cost-records DynamoDB table."""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class CostRecord(BaseModel):
    """Represents a single cost record in the costwatch-cost-records DynamoDB table.

    PK pattern: ACCOUNT#{account_id}#GRAN#{granularity}#PERIOD#{period}
    SK pattern: SERVICE#{service_name}
    """

    pk: str
    sk: str
    account_id: str
    account_alias: str
    period: str
    period_end: str
    granularity: Literal["DAILY", "WEEKLY", "MONTHLY"]
    service_name: str
    amount_usd: Decimal = Field(decimal_places=4)
    amount_brl: Decimal = Field(decimal_places=4)
    exchange_rate: Decimal
    tags: dict = Field(default_factory=dict)
    ingested_at: str
    ttl: int

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Serialize the model to a dict suitable for DynamoDB PutItem.

        Converts all Decimal fields to their string representation first,
        then back to Decimal so DynamoDB/boto3 handles them correctly
        (boto3 requires Decimal, not float).
        """
        item: dict[str, Any] = {}
        for field_name, value in self.model_dump().items():
            if isinstance(value, Decimal):
                # Keep as Decimal — boto3's DynamoDB resource handles Decimal natively
                item[field_name] = value
            elif isinstance(value, dict):
                # Convert any nested Decimals in tags dict
                item[field_name] = _convert_decimals_in_dict(value)
            else:
                item[field_name] = value
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "CostRecord":
        """Deserialize a DynamoDB item dict back into a CostRecord instance.

        DynamoDB returns numbers as Decimal, which Pydantic v2 handles natively.
        """
        return cls.model_validate(item)


def _convert_decimals_in_dict(d: dict) -> dict:
    """Recursively ensure Decimals are preserved in nested dicts."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _convert_decimals_in_dict(v)
        else:
            result[k] = v
    return result
