"""Budget Pydantic v2 model for the costwatch-budgets DynamoDB table."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class Budget(BaseModel):
    """Represents a budget entry in the costwatch-budgets DynamoDB table.

    PK pattern: ACCOUNT#{account_id} or TEAM#{team_name}
    SK pattern: BUDGET#MONTHLY
    """

    pk: str
    sk: str
    budget_usd: Decimal = Field(decimal_places=4)
    budget_brl: Decimal = Field(decimal_places=4)
    alert_threshold_pct: Decimal
    owner_email: str
    created_at: str
    updated_at: str

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Serialize the model to a dict suitable for DynamoDB PutItem."""
        item: dict[str, Any] = {}
        for field_name, value in self.model_dump().items():
            item[field_name] = value
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "Budget":
        """Deserialize a DynamoDB item dict back into a Budget instance."""
        return cls.model_validate(item)
