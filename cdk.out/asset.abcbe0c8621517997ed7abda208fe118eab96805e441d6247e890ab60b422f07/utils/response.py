"""Standard API Gateway proxy response envelope builder."""

import json


def success(body: dict, status_code: int = 200) -> dict:
    """Build a successful API Gateway proxy response.

    Args:
        body: Response payload to serialize as JSON.
        status_code: HTTP status code (default 200).

    Returns:
        API Gateway proxy response dict with CORS headers.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }


def error(message: str, status_code: int) -> dict:
    """Build an error API Gateway proxy response.

    Args:
        message: Human-readable error description.
        status_code: HTTP status code (e.g. 400, 401, 500).

    Returns:
        API Gateway proxy response dict with CORS headers.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"error": message}),
    }
