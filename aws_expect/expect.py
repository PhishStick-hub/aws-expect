from typing import Any

from aws_expect.dynamodb import DynamoDBItemExpectation, DynamoDBTableExpectation
from aws_expect.s3 import S3ObjectExpectation


def expect_s3(s3_object: Any) -> S3ObjectExpectation:
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


def expect_dynamodb(table: Any) -> DynamoDBItemExpectation:
    """Create an expectation for a DynamoDB Table resource.

    Args:
        table: A boto3 DynamoDB Table resource
            (``boto3.resource("dynamodb").Table(name)``).

    Returns:
        A :class:`DynamoDBItemExpectation` that can be used to wait for
        an item to exist (with optional entry matching) or not exist.

    Example::

        import boto3
        from aws_expect import expect_dynamodb

        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table("my-table")
        item = expect_dynamodb(table).to_exist(key={"pk": "user-1"}, timeout=30)
    """
    return DynamoDBItemExpectation(table)


def expect_dynamodb_table(
    dynamodb_resource: Any, table_name: str
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
