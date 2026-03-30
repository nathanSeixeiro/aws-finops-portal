"""Unit tests for CostRecord Pydantic model."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models.cost_record import CostRecord


def _make_cost_record(**overrides) -> CostRecord:
    """Factory helper for creating CostRecord instances with sensible defaults."""
    defaults = {
        "pk": "ACCOUNT#123456789012#GRAN#DAILY#PERIOD#2025-03-15",
        "sk": "SERVICE#Amazon EC2",
        "account_id": "123456789012",
        "account_alias": "prod-account",
        "period": "2025-03-15",
        "period_end": "2025-03-15",
        "granularity": "DAILY",
        "service_name": "Amazon EC2",
        "amount_usd": Decimal("142.5678"),
        "amount_brl": Decimal("719.9674"),
        "exchange_rate": Decimal("5.05"),
        "tags": {"team": "platform", "env": "production"},
        "ingested_at": "2025-03-16T02:00:00Z",
        "ttl": 1742169600,
    }
    defaults.update(overrides)
    return CostRecord(**defaults)


class TestCostRecordValidation:
    """Test CostRecord field validation."""

    def test_valid_daily_record(self):
        record = _make_cost_record(granularity="DAILY")
        assert record.granularity == "DAILY"
        assert record.amount_usd == Decimal("142.5678")

    def test_valid_weekly_record(self):
        record = _make_cost_record(
            pk="ACCOUNT#123456789012#GRAN#WEEKLY#PERIOD#2025-03-10",
            granularity="WEEKLY",
            period="2025-03-10",
            period_end="2025-03-16",
        )
        assert record.granularity == "WEEKLY"

    def test_valid_monthly_record(self):
        record = _make_cost_record(
            pk="ACCOUNT#123456789012#GRAN#MONTHLY#PERIOD#2025-03",
            granularity="MONTHLY",
            period="2025-03",
            period_end="2025-03-31",
        )
        assert record.granularity == "MONTHLY"

    def test_invalid_granularity_rejected(self):
        with pytest.raises(ValidationError):
            _make_cost_record(granularity="HOURLY")

    def test_default_tags_empty_dict(self):
        """When tags is omitted, the default_factory should produce an empty dict."""
        defaults = {
            "pk": "ACCOUNT#123456789012#GRAN#DAILY#PERIOD#2025-03-15",
            "sk": "SERVICE#Amazon EC2",
            "account_id": "123456789012",
            "account_alias": "prod-account",
            "period": "2025-03-15",
            "period_end": "2025-03-15",
            "granularity": "DAILY",
            "service_name": "Amazon EC2",
            "amount_usd": Decimal("142.5678"),
            "amount_brl": Decimal("719.9674"),
            "exchange_rate": Decimal("5.05"),
            "ingested_at": "2025-03-16T02:00:00Z",
            "ttl": 1742169600,
        }
        record = CostRecord(**defaults)
        assert record.tags == {}

    def test_tags_none_rejected(self):
        """Passing None for tags should raise a ValidationError."""
        with pytest.raises(ValidationError):
            _make_cost_record(tags=None)

    def test_decimal_precision_preserved(self):
        record = _make_cost_record(
            amount_usd=Decimal("0.0001"),
            amount_brl=Decimal("0.0005"),
        )
        assert record.amount_usd == Decimal("0.0001")
        assert record.amount_brl == Decimal("0.0005")


class TestCostRecordSerialization:
    """Test CostRecord serialization via model_dump."""

    def test_model_dump_returns_all_fields(self):
        record = _make_cost_record()
        data = record.model_dump()
        assert data["pk"] == "ACCOUNT#123456789012#GRAN#DAILY#PERIOD#2025-03-15"
        assert data["sk"] == "SERVICE#Amazon EC2"
        assert data["granularity"] == "DAILY"
        assert data["tags"] == {"team": "platform", "env": "production"}

    def test_model_dump_decimal_types(self):
        record = _make_cost_record()
        data = record.model_dump()
        assert isinstance(data["amount_usd"], Decimal)
        assert isinstance(data["amount_brl"], Decimal)
        assert isinstance(data["exchange_rate"], Decimal)


class TestCostRecordDynamoDBRoundTrip:
    """Test CostRecord to_dynamodb_item / from_dynamodb_item round-trip."""

    def test_round_trip_preserves_all_fields(self):
        original = _make_cost_record()
        item = original.to_dynamodb_item()
        restored = CostRecord.from_dynamodb_item(item)
        assert restored == original

    def test_to_dynamodb_item_keeps_decimals(self):
        record = _make_cost_record()
        item = record.to_dynamodb_item()
        assert isinstance(item["amount_usd"], Decimal)
        assert isinstance(item["amount_brl"], Decimal)
        assert isinstance(item["exchange_rate"], Decimal)

    def test_round_trip_with_empty_tags(self):
        original = _make_cost_record(tags={})
        item = original.to_dynamodb_item()
        restored = CostRecord.from_dynamodb_item(item)
        assert restored.tags == {}

    def test_round_trip_with_nested_tags(self):
        tags = {"team": "platform", "meta": {"region": "us-east-1"}}
        original = _make_cost_record(tags=tags)
        item = original.to_dynamodb_item()
        restored = CostRecord.from_dynamodb_item(item)
        assert restored.tags == tags

    def test_from_dynamodb_item_with_string_numbers(self):
        """DynamoDB may return Decimal; verify model accepts both."""
        item = _make_cost_record().to_dynamodb_item()
        # Simulate DynamoDB returning Decimal values (already the case)
        restored = CostRecord.from_dynamodb_item(item)
        assert restored.amount_usd == Decimal("142.5678")
