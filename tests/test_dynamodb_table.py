import threading
from uuid import uuid4

import pytest
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

from aws_expect import DynamoDBWaitTimeoutError, WaitTimeoutError, expect_dynamodb_table


class TestDynamoDBTableToExist:
    """Tests for expect_dynamodb_table(resource, name).to_exist()."""

    def test_returns_description_when_table_exists(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        result = expect_dynamodb_table(dynamodb_resource, dynamodb_table.name).to_exist(
            timeout=10, poll_interval=1
        )

        assert result["TableName"] == dynamodb_table.name
        assert result["TableStatus"] == "ACTIVE"
        assert "KeySchema" in result

    def test_raises_timeout_when_table_missing(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        table_name = f"nonexistent-{uuid4().hex[:12]}"

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_table(dynamodb_resource, table_name).to_exist(
                timeout=2, poll_interval=1
            )

        assert exc_info.value.table_name == table_name
        assert exc_info.value.key is None
        assert exc_info.value.timeout == 2

    def test_catchable_as_base_wait_timeout_error(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        """DynamoDBWaitTimeoutError from to_exist is a WaitTimeoutError."""
        table_name = f"nonexistent-{uuid4().hex[:12]}"

        with pytest.raises(WaitTimeoutError):
            expect_dynamodb_table(dynamodb_resource, table_name).to_exist(
                timeout=2, poll_interval=1
            )

    def test_succeeds_when_table_created_mid_poll(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        table_name = f"test-{uuid4().hex[:12]}"

        def create_later() -> None:
            dynamodb_resource.create_table(
                TableName=table_name,
                KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )

        timer = threading.Timer(2.0, create_later)
        timer.start()

        try:
            result = expect_dynamodb_table(dynamodb_resource, table_name).to_exist(
                timeout=30, poll_interval=1
            )
            assert result["TableName"] == table_name
            assert result["TableStatus"] == "ACTIVE"
        finally:
            timer.cancel()
            # Cleanup: delete the table we created
            try:
                dynamodb_resource.meta.client.delete_table(TableName=table_name)
            except Exception:
                pass


class TestDynamoDBTableToNotExist:
    """Tests for expect_dynamodb_table(resource, name).to_not_exist()."""

    def test_returns_none_when_table_absent(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        table_name = f"nonexistent-{uuid4().hex[:12]}"

        result = expect_dynamodb_table(dynamodb_resource, table_name).to_not_exist(
            timeout=10, poll_interval=1
        )

        assert result is None

    def test_raises_timeout_when_table_still_exists(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_table(dynamodb_resource, dynamodb_table.name).to_not_exist(
                timeout=2, poll_interval=1
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key is None
        assert exc_info.value.timeout == 2

    def test_catchable_as_base_wait_timeout_error(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        """DynamoDBWaitTimeoutError from to_not_exist is a WaitTimeoutError."""
        with pytest.raises(WaitTimeoutError):
            expect_dynamodb_table(dynamodb_resource, dynamodb_table.name).to_not_exist(
                timeout=2, poll_interval=1
            )

    def test_succeeds_when_table_deleted_mid_poll(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        table_name = f"test-{uuid4().hex[:12]}"

        # Create table and wait for it to be active
        dynamodb_resource.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb_resource.meta.client.get_waiter("table_exists").wait(
            TableName=table_name
        )

        def delete_later() -> None:
            dynamodb_resource.meta.client.delete_table(TableName=table_name)

        timer = threading.Timer(2.0, delete_later)
        timer.start()

        try:
            result = expect_dynamodb_table(dynamodb_resource, table_name).to_not_exist(
                timeout=30, poll_interval=1
            )
            assert result is None
        finally:
            timer.cancel()
            # Cleanup in case the test failed before deletion happened
            try:
                dynamodb_resource.meta.client.delete_table(TableName=table_name)
            except Exception:
                pass
