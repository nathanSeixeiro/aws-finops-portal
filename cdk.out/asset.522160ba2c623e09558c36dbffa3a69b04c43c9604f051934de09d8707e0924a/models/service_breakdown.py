"""ServiceBreakdown Pydantic v2 model for cost breakdown by AWS service."""

from decimal import Decimal

from pydantic import BaseModel, Field


class ServiceBreakdown(BaseModel):
    """Represents a single service's cost breakdown within a period.

    Used by CostQueryService to return per-service cost data
    with percentage of total spend.
    """

    service_name: str
    amount_usd: Decimal = Field(decimal_places=4)
    amount_brl: Decimal = Field(decimal_places=4)
    percentage_of_total: Decimal
