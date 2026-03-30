"""Repository for costwatch-budgets DynamoDB table."""

from models.budget import Budget


class BudgetRepository:
    """Encapsulates all DynamoDB access for the costwatch-budgets table.

    Uses dependency injection — accepts a DynamoDB table resource in the constructor.
    """

    def __init__(self, table_resource) -> None:
        self._table = table_resource

    def get_account_budget(self, account_id: str) -> Budget | None:
        """Get the monthly budget for a specific account."""
        resp = self._table.get_item(
            Key={"pk": f"ACCOUNT#{account_id}", "sk": "BUDGET#MONTHLY"}
        )
        item = resp.get("Item")
        return Budget.from_dynamodb_item(item) if item else None

    def get_team_budget(self, team_name: str) -> Budget | None:
        """Get the monthly budget for a specific team."""
        resp = self._table.get_item(
            Key={"pk": f"TEAM#{team_name}", "sk": "BUDGET#MONTHLY"}
        )
        item = resp.get("Item")
        return Budget.from_dynamodb_item(item) if item else None

    def list_all_budgets(self) -> list[Budget]:
        """Scan the budgets table and return all budget entries.

        Scan is acceptable here because the budgets table is small.
        """
        resp = self._table.scan()
        return [Budget.from_dynamodb_item(item) for item in resp.get("Items", [])]
