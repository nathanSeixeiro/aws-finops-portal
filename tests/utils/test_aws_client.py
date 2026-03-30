"""Tests for aws_client.py factory functions."""

from unittest.mock import MagicMock

from utils.aws_client import get_ce_client, get_dynamodb_resource, get_ssm_client


class TestGetDynamodbResource:
    def test_returns_injected_resource(self):
        mock_resource = MagicMock()
        result = get_dynamodb_resource(resource=mock_resource)
        assert result is mock_resource

    def test_creates_real_resource_when_none(self):
        resource = get_dynamodb_resource()
        assert resource.meta.service_name == "dynamodb"

    def test_respects_region(self):
        resource = get_dynamodb_resource(region="eu-west-1")
        assert resource.meta.client.meta.region_name == "eu-west-1"


class TestGetSsmClient:
    def test_returns_injected_client(self):
        mock_client = MagicMock()
        result = get_ssm_client(client=mock_client)
        assert result is mock_client

    def test_creates_real_client_when_none(self):
        client = get_ssm_client()
        assert client.meta.service_model.service_name == "ssm"

    def test_respects_region(self):
        client = get_ssm_client(region="eu-west-1")
        assert client.meta.region_name == "eu-west-1"


class TestGetCeClient:
    def test_returns_injected_client(self):
        mock_client = MagicMock()
        result = get_ce_client(client=mock_client)
        assert result is mock_client

    def test_creates_real_client_when_none(self):
        client = get_ce_client()
        assert client.meta.service_model.service_name == "ce"

    def test_creates_client_with_default_region(self):
        # Cost Explorer is a global service; boto3 resolves to aws-global
        client = get_ce_client()
        assert client.meta.service_model.service_name == "ce"
