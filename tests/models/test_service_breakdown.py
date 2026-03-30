"""Unit tests for ServiceBreakdown Pydantic model."""

from decimal import Decimal

from src.models.service_breakdown import ServiceBreakdown


def _make_breakdown(**overrides) -> ServiceBreakdown:
    """Factory helper for creating ServiceBreakdown instances."""
    defaults = {
        "service_name": "Amazon EC2",
        "amount_usd": Decimal("500.0000"),
        "amount_brl": Decimal("2525.0000"),
        "percentage_of_total": Decimal("45.23"),
    }
    defaults.update(overrides)
    return ServiceBreakdown(**defaults)


class TestServiceBreakdownValidation:
    """Test ServiceBreakdown field validation."""

    def test_valid_breakdown(self):
        bd = _make_breakdown()
        assert bd.service_name == "Amazon EC2"
        assert bd.amount_usd == Decimal("500.0000")
        assert bd.percentage_of_total == Decimal("45.23")

    def test_decimal_precision(self):
        bd = _make_breakdown(
            amount_usd=Decimal("0.0001"),
            amount_brl=Decimal("0.0005"),
        )
        assert bd.amount_usd == Decimal("0.0001")
        assert bd.amount_brl == Decimal("0.0005")


class TestServiceBreakdownPercentage:
    """Test percentage_of_total computation scenarios."""

    def test_percentage_sums_to_100(self):
        """Verify a realistic set of breakdowns sums to ~100%."""
        breakdowns = [
            _make_breakdown(service_name="EC2", percentage_of_total=Decimal("45.00")),
            _make_breakdown(service_name="S3", percentage_of_total=Decimal("30.00")),
            _make_breakdown(service_name="RDS", percentage_of_total=Decimal("25.00")),
        ]
        total_pct = sum(b.percentage_of_total for b in breakdowns)
        assert total_pct == Decimal("100.00")

    def test_single_service_100_percent(self):
        bd = _make_breakdown(percentage_of_total=Decimal("100.00"))
        assert bd.percentage_of_total == Decimal("100.00")

    def test_zero_percentage(self):
        bd = _make_breakdown(
            amount_usd=Decimal("0.0000"),
            amount_brl=Decimal("0.0000"),
            percentage_of_total=Decimal("0.00"),
        )
        assert bd.percentage_of_total == Decimal("0.00")

    def test_small_percentage(self):
        bd = _make_breakdown(
            amount_usd=Decimal("0.5000"),
            percentage_of_total=Decimal("0.05"),
        )
        assert bd.percentage_of_total == Decimal("0.05")

    def test_model_dump_preserves_percentage(self):
        bd = _make_breakdown(percentage_of_total=Decimal("33.3333"))
        data = bd.model_dump()
        assert data["percentage_of_total"] == Decimal("33.3333")
        assert isinstance(data["percentage_of_total"], Decimal)
