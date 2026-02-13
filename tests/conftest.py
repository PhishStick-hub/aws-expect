from collections.abc import Iterator
from uuid import uuid4

import boto3
import pytest
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
from mypy_boto3_s3.client import S3Client
from mypy_boto3_s3.service_resource import S3ServiceResource
from testcontainers.localstack import LocalStackContainer


@pytest.fixture(scope="session")
def localstack() -> Iterator[LocalStackContainer]:
    """Start a LocalStack container for the entire test session."""
    with LocalStackContainer(image="localstack/localstack:4") as container:
        yield container


@pytest.fixture(scope="session")
def s3_client(localstack: LocalStackContainer) -> S3Client:
    """Create a boto3 S3 client connected to the LocalStack container."""
    return boto3.client(
        "s3",
        endpoint_url=localstack.get_url(),
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


@pytest.fixture(scope="session")
def s3_resource(localstack: LocalStackContainer) -> S3ServiceResource:
    """Create a boto3 S3 resource connected to the LocalStack container."""
    return boto3.resource(
        "s3",
        endpoint_url=localstack.get_url(),
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


@pytest.fixture()
def test_bucket(s3_client: S3Client) -> Iterator[str]:
    """Create a unique S3 bucket for each test, cleaned up afterwards."""
    bucket_name = f"test-{uuid4().hex[:12]}"
    s3_client.create_bucket(Bucket=bucket_name)
    yield bucket_name

    # Cleanup: delete all objects then the bucket
    response = s3_client.list_objects_v2(Bucket=bucket_name)
    for obj in response.get("Contents", []):
        s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])
    s3_client.delete_bucket(Bucket=bucket_name)


# ── DynamoDB fixtures ──────────────────────────────────────────────


@pytest.fixture(scope="session")
def dynamodb_resource(localstack: LocalStackContainer) -> DynamoDBServiceResource:
    """Create a boto3 DynamoDB resource connected to the LocalStack container."""
    return boto3.resource(
        "dynamodb",
        endpoint_url=localstack.get_url(),
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


@pytest.fixture()
def dynamodb_table(dynamodb_resource: DynamoDBServiceResource) -> Iterator[Table]:
    """Create a unique DynamoDB table (hash key only) for each test."""
    table_name = f"test-{uuid4().hex[:12]}"
    table = dynamodb_resource.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.meta.client.get_waiter("table_exists").wait(TableName=table_name)
    yield table
    table.delete()


@pytest.fixture()
def dynamodb_composite_table(
    dynamodb_resource: DynamoDBServiceResource,
) -> Iterator[Table]:
    """Create a unique DynamoDB table (hash + sort key) for each test."""
    table_name = f"test-{uuid4().hex[:12]}"
    table = dynamodb_resource.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.meta.client.get_waiter("table_exists").wait(TableName=table_name)
    yield table
    table.delete()
