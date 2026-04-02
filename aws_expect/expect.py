from __future__ import annotations

from typing import TYPE_CHECKING

from aws_expect.dynamodb import DynamoDBItemExpectation, DynamoDBTableExpectation
from aws_expect.lambda_function import LambdaFunctionExpectation
from aws_expect.s3 import S3ObjectExpectation
from aws_expect.sqs import SQSQueueExpectation

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
    from mypy_boto3_lambda.client import LambdaClient
    from mypy_boto3_s3.service_resource import Object as S3Object
    from mypy_boto3_sqs.service_resource import Queue as SQSQueue


def expect_s3(s3_object: S3Object) -> S3ObjectExpectation:
    """Create an expectation for an S3 resource Object.

    Args:
        s3_object: A boto3 S3 Object resource
            (``boto3.resource("s3").Object(bucket, key)``).

    Returns:
        An :class:`S3ObjectExpectation` that can be used to wait for
        the object to exist or not exist.

    Example::

        import boto3
        from aws_expect import expect_s3

        s3 = boto3.resource("s3")
        obj = s3.Object("my-bucket", "report.csv")
        metadata = expect_s3(obj).to_exist(timeout=30)
    """
    return S3ObjectExpectation(s3_object)


def expect_dynamodb_item(table: Table) -> DynamoDBItemExpectation:
    """Create an expectation for a DynamoDB Table resource item.

    Args:
        table: A boto3 DynamoDB Table resource
            (``boto3.resource("dynamodb").Table(name)``).

    Returns:
        A :class:`DynamoDBItemExpectation` that can be used to wait for
        an item to exist (with optional entry matching) or not exist.

    Example::

        import boto3
        from aws_expect import expect_dynamodb_item

        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table("my-table")
        item = expect_dynamodb_item(table).to_exist(key={"pk": "user-1"}, timeout=30)
    """
    return DynamoDBItemExpectation(table)


def expect_dynamodb_table(
    dynamodb_resource: DynamoDBServiceResource, table_name: str
) -> DynamoDBTableExpectation:
    """Create an expectation for a DynamoDB table.

    Use this to wait for a table to exist (and become ACTIVE) or to be
    deleted.

    Args:
        dynamodb_resource: A boto3 DynamoDB resource
            (``boto3.resource("dynamodb")``).
        table_name: The name of the DynamoDB table to check.

    Returns:
        A :class:`DynamoDBTableExpectation` that can be used to wait for
        the table to exist or not exist.

    Example::

        import boto3
        from aws_expect import expect_dynamodb_table

        dynamodb = boto3.resource("dynamodb")
        description = expect_dynamodb_table(dynamodb, "my-table").to_exist(timeout=60)
    """
    return DynamoDBTableExpectation(dynamodb_resource, table_name)


def expect_lambda(lambda_client: LambdaClient) -> LambdaFunctionExpectation:
    """Create an expectation for a Lambda function.

    Args:
        lambda_client: A boto3 Lambda client
            (``boto3.client("lambda")``).

    Returns:
        A :class:`LambdaFunctionExpectation` whose methods each accept a
        *function_name* and wait for the requested state.

    Example::

        import boto3
        from aws_expect import expect_lambda

        client = boto3.client("lambda")
        expect_lambda(client).to_be_active("my-function", timeout=60)
    """
    return LambdaFunctionExpectation(lambda_client)


def expect_sqs(queue: SQSQueue) -> SQSQueueExpectation:
    """Create an expectation for a boto3 SQS Queue resource.

    Args:
        queue: A boto3 SQS Queue resource
            (``boto3.resource("sqs").Queue(url)``).

    Returns:
        An :class:`SQSQueueExpectation` that can be used to wait for
        a message to be present or to consume a message.

    Example::

        import boto3
        from aws_expect import expect_sqs

        sqs = boto3.resource("sqs")
        queue = sqs.Queue("https://sqs.us-east-1.amazonaws.com/123/my-queue")
        message = expect_sqs(queue).to_have_message(body="hello", timeout=30)
    """
    return SQSQueueExpectation(queue)
