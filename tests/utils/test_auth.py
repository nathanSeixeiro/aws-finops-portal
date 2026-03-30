"""Tests for auth.py API key validation."""

import os

from src.utils.auth import validate_api_key


class TestValidateApiKey:
    def test_valid_key(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "my-secret-key")
        event = {"headers": {"x-api-key": "my-secret-key"}}
        assert validate_api_key(event) is True

    def test_invalid_key(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "my-secret-key")
        event = {"headers": {"x-api-key": "wrong-key"}}
        assert validate_api_key(event) is False

    def test_missing_header(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "my-secret-key")
        event = {"headers": {}}
        assert validate_api_key(event) is False

    def test_missing_headers_key(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "my-secret-key")
        event = {}
        assert validate_api_key(event) is False

    def test_none_headers(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "my-secret-key")
        event = {"headers": None}
        assert validate_api_key(event) is False

    def test_missing_env_var(self, monkeypatch):
        monkeypatch.delenv("API_KEY", raising=False)
        event = {"headers": {"x-api-key": "some-key"}}
        assert validate_api_key(event) is False

    def test_case_insensitive_header(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "my-secret-key")
        event = {"headers": {"X-Api-Key": "my-secret-key"}}
        assert validate_api_key(event) is True

    def test_uppercase_header(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "my-secret-key")
        event = {"headers": {"X-API-KEY": "my-secret-key"}}
        assert validate_api_key(event) is True
