import inspect
import io
import zipfile
from collections.abc import Iterator
from contextlib import suppress
from types import FunctionType
from uuid import uuid4

import boto3
import pytest
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
from mypy_boto3_lambda.client import LambdaClient
from mypy_boto3_s3.service_resource import S3ServiceResource
from mypy_boto3_sqs.service_resource import Queue, SQSServiceResource
from testcontainers.localstack import LocalStackContainer


def _make_lambda_zip(handler_fn: FunctionType) -> bytes:
    """Create an in-memory zip with handler.py containing *handler_fn* renamed to ``handler``."""
    source = inspect.getsource(handler_fn)
    source = source.replace(f"def {handler_fn.__name__}(", "def handler(", 1)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("handler.py", source)
    return buf.getvalue()


@pytest.fixture(scope="session")
def localstack() -> Iterator[LocalStackContainer]:
    """Start a LocalStack container for the entire test session."""
    container = LocalStackContainer(image="localstack/localstack:4")
    container.with_volume_mapping("/var/run/docker.sock", "/var/run/docker.sock", "rw")
    with container:
        yield container


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
def test_bucket(s3_resource: S3ServiceResource) -> Iterator[str]:
    """Create a unique S3 bucket for each test, cleaned up afterwards."""
    bucket_name = f"test-{uuid4().hex[:12]}"
    bucket = s3_resource.create_bucket(Bucket=bucket_name)
    yield bucket_name

    for obj in bucket.objects.all():
        obj.delete()
    bucket.delete()


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
def dynamodb_tables(
    dynamodb_resource: DynamoDBServiceResource,
) -> Iterator[list[Table]]:
    """Create three unique DynamoDB tables for parallel expectation tests."""
    tables: list[Table] = []
    for _ in range(3):
        table_name = f"test-{uuid4().hex[:12]}"
        table = dynamodb_resource.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName=table_name)
        tables.append(table)
    yield tables
    for table in tables:
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


# ── Lambda fixtures ───────────────────────────────────────────────

_LAMBDA_ROLE = "arn:aws:iam::000000000000:role/lambda-role"


def _default_handler(event, _context):
    return {"statusCode": 200, "body": "hello"}


def _error_handler(event, _context):
    raise RuntimeError("intentional error")


def _json_body_handler(event, _context):
    import json  # noqa: PLC0415

    return {"statusCode": 200, "body": json.dumps({"message": "hello", "status": "ok"})}


def _nested_body_handler(event, _context):
    import json  # noqa: PLC0415

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"data": {"id": 42, "tags": ["a", "b"]}, "meta": {"version": 1}}
        ),
    }


@pytest.fixture(scope="session")
def lambda_client(localstack: LocalStackContainer) -> LambdaClient:
    """Create a boto3 Lambda client connected to the LocalStack container."""
    return boto3.client(
        "lambda",
        endpoint_url=localstack.get_url(),
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


@pytest.fixture()
def lambda_function(lambda_client: LambdaClient) -> Iterator[str]:
    """Create a unique Lambda function for each test, cleaned up afterwards."""
    function_name = f"test-{uuid4().hex[:12]}"
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=_LAMBDA_ROLE,
        Handler="handler.handler",
        Code={"ZipFile": _make_lambda_zip(_default_handler)},
    )
    lambda_client.get_waiter("function_active_v2").wait(FunctionName=function_name)
    yield function_name
    with suppress(lambda_client.exceptions.ResourceNotFoundException):
        lambda_client.delete_function(FunctionName=function_name)


@pytest.fixture()
def lambda_function_json_body(lambda_client: LambdaClient) -> Iterator[str]:
    """Create a Lambda function returning a JSON-encoded body field for respond_with tests."""
    function_name = f"test-json-{uuid4().hex[:12]}"
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=_LAMBDA_ROLE,
        Handler="handler.handler",
        Code={"ZipFile": _make_lambda_zip(_json_body_handler)},
    )
    lambda_client.get_waiter("function_active_v2").wait(FunctionName=function_name)
    yield function_name
    with suppress(lambda_client.exceptions.ResourceNotFoundException):
        lambda_client.delete_function(FunctionName=function_name)


@pytest.fixture()
def lambda_function_nested_body(lambda_client: LambdaClient) -> Iterator[str]:
    """Create a Lambda function returning a deeply nested JSON body, for deep-match tests."""
    function_name = f"test-nested-{uuid4().hex[:12]}"
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=_LAMBDA_ROLE,
        Handler="handler.handler",
        Code={"ZipFile": _make_lambda_zip(_nested_body_handler)},
    )
    lambda_client.get_waiter("function_active_v2").wait(FunctionName=function_name)
    yield function_name
    with suppress(lambda_client.exceptions.ResourceNotFoundException):
        lambda_client.delete_function(FunctionName=function_name)


@pytest.fixture()
def error_lambda_function(lambda_client: LambdaClient) -> Iterator[str]:
    """Create a Lambda function whose handler always raises, for error-path tests."""
    function_name = f"test-err-{uuid4().hex[:12]}"
    lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.13",
        Role=_LAMBDA_ROLE,
        Handler="handler.handler",
        Code={"ZipFile": _make_lambda_zip(_error_handler)},
    )
    lambda_client.get_waiter("function_active_v2").wait(FunctionName=function_name)
    yield function_name
    with suppress(lambda_client.exceptions.ResourceNotFoundException):
        lambda_client.delete_function(FunctionName=function_name)


# ── SQS fixtures ──────────────────────────────────────────────────


@pytest.fixture(scope="session")
def sqs_resource(localstack: LocalStackContainer) -> SQSServiceResource:
    """Create a boto3 SQS resource connected to the LocalStack container."""
    return boto3.resource(
        "sqs",
        endpoint_url=localstack.get_url(),
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


@pytest.fixture()
def sqs_queue(sqs_resource: SQSServiceResource) -> Iterator[Queue]:
    """Create a unique standard SQS queue for each test, cleaned up afterwards."""
    queue_name = f"test-{uuid4().hex[:12]}"
    queue = sqs_resource.create_queue(QueueName=queue_name)
    yield queue
    queue.delete()
