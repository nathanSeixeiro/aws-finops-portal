"""Tests for response.py envelope builder."""

import json
from decimal import Decimal

from utils.response import error, success


class TestSuccess:
    def test_default_status_code(self):
        resp = success({"msg": "ok"})
        assert resp["statusCode"] == 200

    def test_custom_status_code(self):
        resp = success({"created": True}, status_code=201)
        assert resp["statusCode"] == 201

    def test_cors_header(self):
        resp = success({})
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_content_type_header(self):
        resp = success({})
        assert resp["headers"]["Content-Type"] == "application/json"

    def test_body_is_json_string(self):
        resp = success({"key": "value"})
        parsed = json.loads(resp["body"])
        assert parsed == {"key": "value"}

    def test_decimal_serialization(self):
        resp = success({"amount_usd": Decimal("123.4567"), "amount_brl": Decimal("623.4567")})
        parsed = json.loads(resp["body"])
        assert parsed["amount_usd"] == "123.4567"
        assert parsed["amount_brl"] == "623.4567"


class TestError:
    def test_status_code(self):
        resp = error("not found", 404)
        assert resp["statusCode"] == 404

    def test_cors_header(self):
        resp = error("bad", 400)
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_content_type_header(self):
        resp = error("bad", 400)
        assert resp["headers"]["Content-Type"] == "application/json"

    def test_body_contains_error_key(self):
        resp = error("something went wrong", 500)
        parsed = json.loads(resp["body"])
        assert parsed == {"error": "something went wrong"}
