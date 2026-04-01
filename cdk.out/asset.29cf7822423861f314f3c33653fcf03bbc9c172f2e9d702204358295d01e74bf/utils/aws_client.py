"""Boto3 client factory with dependency injection support."""

import boto3


def get_dynamodb_resource(resource=None, region: str = "us-east-1"):
    """Return a DynamoDB resource. If provided, return the injected resource as-is."""
    if resource is not None:
        return resource
    return boto3.resource("dynamodb", region_name=region)


def get_ssm_client(client=None, region: str = "us-east-1"):
    """Return an SSM client. If provided, return the injected client as-is."""
    if client is not None:
        return client
    return boto3.client("ssm", region_name=region)


def get_ce_client(client=None, region: str = "us-east-1"):
    """Return a Cost Explorer client. If provided, return the injected client as-is."""
    if client is not None:
        return client
    return boto3.client("ce", region_name=region)
