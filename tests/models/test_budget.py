"""Unit tests for Budget Pydantic model."""

from decimal import Decimal

from src.models.budget import Budget


def _make_budget(**overrides) -> Budget:
    """Factory helper for creating Budget instances with sensible defaults."""
    defaults = {
        "pk": "ACCOUNT#123456789012",
        "sk": "BUDGET#MONTHLY",
        "budget_usd": Decimal("5000.0000"),
        "budget_brl": Decimal("25250.0000"),
        "alert_threshold_pct": Decimal("80"),
        "owner_email": "owner@example.com",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-03-01T00:00:00Z",
    }
    defaults.update(overrides)
    return Budget(**defaults)


class TestBudgetValidation:
    """Test Budget field validation."""

    def test_valid_account_budget(self):
        budget = _make_budget()
        assert budget.pk == "ACCOUNT#123456789012"
        assert budget.sk == "BUDGET#MONTHLY"
        assert budget.budget_usd == Decimal("5000.0000")

    def test_valid_team_budget(self):
        budget = _make_budget(pk="TEAM#platform-eng")
        assert budget.pk == "TEAM#platform-eng"

    def test_decimal_precision_preserved(self):
        budget = _make_budget(
            budget_usd=Decimal("1234.5678"),
            budget_brl=Decimal("6234.5678"),
        )
        assert budget.budget_usd == Decimal("1234.5678")
        assert budget.budget_brl == Decimal("6234.5678")

    def test_alert_threshold_pct(self):
        budget = _make_budget(alert_threshold_pct=Decimal("90"))
        assert budget.alert_threshold_pct == Decimal("90")


class TestBudgetSerialization:
    """Test Budget serialization and DynamoDB round-trip."""

    def test_model_dump_returns_all_fields(self):
        budget = _make_budget()
        data = budget.model_dump()
        assert data["pk"] == "ACCOUNT#123456789012"
        assert data["owner_email"] == "owner@example.com"
        assert isinstance(data["budget_usd"], Decimal)

    def test_to_dynamodb_item_preserves_decimals(self):
        budget = _make_budget()
        item = budget.to_dynamodb_item()
        assert isinstance(item["budget_usd"], Decimal)
        assert isinstance(item["budget_brl"], Decimal)
        assert isinstance(item["alert_threshold_pct"], Decimal)

    def test_round_trip_preserves_all_fields(self):
        original = _make_budget()
        item = original.to_dynamodb_item()
        restored = Budget.from_dynamodb_item(item)
        assert restored == original

    def test_round_trip_team_budget(self):
        original = _make_budget(pk="TEAM#data-eng")
        item = original.to_dynamodb_item()
        restored = Budget.from_dynamodb_item(item)
        assert restored.pk == "TEAM#data-eng"
        assert restored == original
