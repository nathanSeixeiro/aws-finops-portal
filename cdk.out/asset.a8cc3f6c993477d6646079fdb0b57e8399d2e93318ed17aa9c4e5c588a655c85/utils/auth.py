"""API key validation utility for CostWatch API Gateway handlers."""

import os


def validate_api_key(event: dict) -> bool:
    """Return True if x-api-key header matches expected key, False otherwise.

    Reads the expected API key from the API_KEY environment variable and compares
    it against the x-api-key header extracted from the event (case-insensitive
    header lookup).
    """
    expected_key = os.environ.get("API_KEY")
    if not expected_key:
        return False

    headers = event.get("headers") or {}
    # Normalize header names to lowercase for case-insensitive matching
    normalized = {k.lower(): v for k, v in headers.items()}
    provided_key = normalized.get("x-api-key")

    return provided_key == expected_key
