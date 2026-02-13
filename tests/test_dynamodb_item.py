import threading

import pytest

from aws_expect import DynamoDBWaitTimeoutError, WaitTimeoutError, expect_dynamodb


class TestDynamoDBToExist:
    """Tests for expect_dynamodb(table).to_exist(key=...)."""

    def test_returns_item_when_exists(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "user-1", "name": "Alice"})

        result = expect_dynamodb(dynamodb_table).to_exist(
            key={"pk": "user-1"}, timeout=10, poll_interval=1
        )

        assert result["pk"] == "user-1"
        assert result["name"] == "Alice"

    def test_raises_timeout_when_item_missing(self, dynamodb_table):
        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb(dynamodb_table).to_exist(
                key={"pk": "ghost"}, timeout=2, poll_interval=1
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key == {"pk": "ghost"}
        assert exc_info.value.timeout == 2

    def test_catchable_as_base_wait_timeout_error(self, dynamodb_table):
        """DynamoDBWaitTimeoutError is a WaitTimeoutError."""
        with pytest.raises(WaitTimeoutError):
            expect_dynamodb(dynamodb_table).to_exist(
                key={"pk": "ghost"}, timeout=2, poll_interval=1
            )

    def test_succeeds_when_item_appears_mid_poll(self, dynamodb_table):
        def insert_later():
            dynamodb_table.put_item(Item={"pk": "delayed", "status": "ready"})

        timer = threading.Timer(2.0, insert_later)
        timer.start()

        try:
            result = expect_dynamodb(dynamodb_table).to_exist(
                key={"pk": "delayed"}, timeout=10, poll_interval=1
            )
            assert result["pk"] == "delayed"
            assert result["status"] == "ready"
        finally:
            timer.cancel()

    def test_matches_expected_entries(self, dynamodb_table):
        dynamodb_table.put_item(
            Item={"pk": "order-1", "status": "active", "total": 100}
        )

        result = expect_dynamodb(dynamodb_table).to_exist(
            key={"pk": "order-1"},
            entries={"status": "active"},
            timeout=10,
            poll_interval=1,
        )

        assert result["status"] == "active"
        assert result["total"] == 100  # extra fields are present

    def test_raises_timeout_when_entries_dont_match(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "order-2", "status": "pending"})

        with pytest.raises(DynamoDBWaitTimeoutError):
            expect_dynamodb(dynamodb_table).to_exist(
                key={"pk": "order-2"},
                entries={"status": "shipped"},
                timeout=2,
                poll_interval=1,
            )

    def test_succeeds_when_entries_match_after_update(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "order-3", "status": "pending"})

        def update_later():
            dynamodb_table.update_item(
                Key={"pk": "order-3"},
                UpdateExpression="SET #s = :val",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":val": "shipped"},
            )

        timer = threading.Timer(2.0, update_later)
        timer.start()

        try:
            result = expect_dynamodb(dynamodb_table).to_exist(
                key={"pk": "order-3"},
                entries={"status": "shipped"},
                timeout=10,
                poll_interval=1,
            )
            assert result["status"] == "shipped"
        finally:
            timer.cancel()

    def test_works_with_composite_key(self, dynamodb_composite_table):
        dynamodb_composite_table.put_item(
            Item={"pk": "user-1", "sk": "order-1", "total": 50}
        )

        result = expect_dynamodb(dynamodb_composite_table).to_exist(
            key={"pk": "user-1", "sk": "order-1"}, timeout=10, poll_interval=1
        )

        assert result["total"] == 50

    def test_works_with_composite_key_and_entries(self, dynamodb_composite_table):
        dynamodb_composite_table.put_item(
            Item={"pk": "user-2", "sk": "order-5", "status": "done", "total": 200}
        )

        result = expect_dynamodb(dynamodb_composite_table).to_exist(
            key={"pk": "user-2", "sk": "order-5"},
            entries={"status": "done", "total": 200},
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "user-2"
        assert result["sk"] == "order-5"


class TestDynamoDBToBeEmpty:
    """Tests for expect_dynamodb(table).to_be_empty()."""

    def test_returns_none_when_table_empty(self, dynamodb_table):
        result = expect_dynamodb(dynamodb_table).to_be_empty(
            timeout=10, poll_interval=1
        )

        assert result is None

    def test_raises_timeout_when_table_has_items(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "user-1", "name": "Alice"})

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb(dynamodb_table).to_be_empty(timeout=2, poll_interval=1)

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key is None
        assert exc_info.value.timeout == 2

    def test_catchable_as_base_wait_timeout_error(self, dynamodb_table):
        """DynamoDBWaitTimeoutError from to_be_empty is a WaitTimeoutError."""
        dynamodb_table.put_item(Item={"pk": "sticky"})

        with pytest.raises(WaitTimeoutError):
            expect_dynamodb(dynamodb_table).to_be_empty(timeout=2, poll_interval=1)

    def test_succeeds_when_items_deleted_mid_poll(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "temp-1"})
        dynamodb_table.put_item(Item={"pk": "temp-2"})

        def delete_later():
            dynamodb_table.delete_item(Key={"pk": "temp-1"})
            dynamodb_table.delete_item(Key={"pk": "temp-2"})

        timer = threading.Timer(2.0, delete_later)
        timer.start()

        try:
            result = expect_dynamodb(dynamodb_table).to_be_empty(
                timeout=10, poll_interval=1
            )
            assert result is None
        finally:
            timer.cancel()


class TestDynamoDBToNotBeEmpty:
    """Tests for expect_dynamodb(table).to_not_be_empty()."""

    def test_returns_none_when_table_has_items(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "user-1", "name": "Alice"})

        result = expect_dynamodb(dynamodb_table).to_not_be_empty(
            timeout=10, poll_interval=1
        )

        assert result is None

    def test_raises_timeout_when_table_empty(self, dynamodb_table):
        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb(dynamodb_table).to_not_be_empty(timeout=2, poll_interval=1)

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key is None
        assert exc_info.value.timeout == 2

    def test_catchable_as_base_wait_timeout_error(self, dynamodb_table):
        """DynamoDBWaitTimeoutError from to_not_be_empty is a WaitTimeoutError."""
        with pytest.raises(WaitTimeoutError):
            expect_dynamodb(dynamodb_table).to_not_be_empty(timeout=2, poll_interval=1)

    def test_succeeds_when_item_inserted_mid_poll(self, dynamodb_table):
        def insert_later():
            dynamodb_table.put_item(Item={"pk": "delayed", "status": "ready"})

        timer = threading.Timer(2.0, insert_later)
        timer.start()

        try:
            result = expect_dynamodb(dynamodb_table).to_not_be_empty(
                timeout=10, poll_interval=1
            )
            assert result is None
        finally:
            timer.cancel()


class TestDynamoDBToNotExist:
    """Tests for expect_dynamodb(table).to_not_exist(key=...)."""

    def test_returns_none_when_item_absent(self, dynamodb_table):
        result = expect_dynamodb(dynamodb_table).to_not_exist(
            key={"pk": "ghost"}, timeout=10, poll_interval=1
        )

        assert result is None

    def test_raises_timeout_when_item_still_exists(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "sticky", "val": "here"})

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb(dynamodb_table).to_not_exist(
                key={"pk": "sticky"}, timeout=2, poll_interval=1
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key == {"pk": "sticky"}
        assert exc_info.value.timeout == 2

    def test_succeeds_when_item_deleted_mid_poll(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "temp", "val": "bye"})

        def delete_later():
            dynamodb_table.delete_item(Key={"pk": "temp"})

        timer = threading.Timer(2.0, delete_later)
        timer.start()

        try:
            result = expect_dynamodb(dynamodb_table).to_not_exist(
                key={"pk": "temp"}, timeout=10, poll_interval=1
            )
            assert result is None
        finally:
            timer.cancel()
