import threading
from decimal import Decimal

import pytest
from mypy_boto3_dynamodb.service_resource import Table

from aws_expect import (
    DynamoDBNonNumericFieldError,
    DynamoDBWaitTimeoutError,
    WaitTimeoutError,
    expect_dynamodb_item,
)


class TestDynamoDBToExist:
    """Tests for expect_dynamodb_item(table).to_exist(key=...)."""

    def test_returns_item_when_exists(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "user-1", "name": "Alice"})

        result = expect_dynamodb_item(dynamodb_table).to_exist(
            key={"pk": "user-1"}, timeout=10, poll_interval=1
        )

        assert result["pk"] == "user-1"
        assert result["name"] == "Alice"

    def test_raises_timeout_when_item_missing(self, dynamodb_table):
        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_exist(
                key={"pk": "ghost"}, timeout=2, poll_interval=1
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key == {"pk": "ghost"}
        assert exc_info.value.timeout == 2

    def test_catchable_as_base_wait_timeout_error(self, dynamodb_table):
        """DynamoDBWaitTimeoutError is a WaitTimeoutError."""
        with pytest.raises(WaitTimeoutError):
            expect_dynamodb_item(dynamodb_table).to_exist(
                key={"pk": "ghost"}, timeout=2, poll_interval=1
            )

    def test_succeeds_when_item_appears_mid_poll(self, dynamodb_table):
        def insert_later():
            dynamodb_table.put_item(Item={"pk": "delayed", "status": "ready"})

        timer = threading.Timer(2.0, insert_later)
        timer.start()

        try:
            result = expect_dynamodb_item(dynamodb_table).to_exist(
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

        result = expect_dynamodb_item(dynamodb_table).to_exist(
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
            expect_dynamodb_item(dynamodb_table).to_exist(
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
            result = expect_dynamodb_item(dynamodb_table).to_exist(
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

        result = expect_dynamodb_item(dynamodb_composite_table).to_exist(
            key={"pk": "user-1", "sk": "order-1"}, timeout=10, poll_interval=1
        )

        assert result["total"] == 50

    def test_works_with_composite_key_and_entries(self, dynamodb_composite_table):
        dynamodb_composite_table.put_item(
            Item={"pk": "user-2", "sk": "order-5", "status": "done", "total": 200}
        )

        result = expect_dynamodb_item(dynamodb_composite_table).to_exist(
            key={"pk": "user-2", "sk": "order-5"},
            entries={"status": "done", "total": 200},
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "user-2"
        assert result["sk"] == "order-5"


class TestDynamoDBToBeEmpty:
    """Tests for expect_dynamodb_item(table).to_be_empty()."""

    def test_returns_none_when_table_empty(self, dynamodb_table):
        result = expect_dynamodb_item(dynamodb_table).to_be_empty(
            timeout=10, poll_interval=1
        )

        assert result is None

    def test_raises_timeout_when_table_has_items(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "user-1", "name": "Alice"})

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_be_empty(timeout=2, poll_interval=1)

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key is None
        assert exc_info.value.timeout == 2

    def test_catchable_as_base_wait_timeout_error(self, dynamodb_table):
        """DynamoDBWaitTimeoutError from to_be_empty is a WaitTimeoutError."""
        dynamodb_table.put_item(Item={"pk": "sticky"})

        with pytest.raises(WaitTimeoutError):
            expect_dynamodb_item(dynamodb_table).to_be_empty(timeout=2, poll_interval=1)

    def test_succeeds_when_items_deleted_mid_poll(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "temp-1"})
        dynamodb_table.put_item(Item={"pk": "temp-2"})

        def delete_later():
            dynamodb_table.delete_item(Key={"pk": "temp-1"})
            dynamodb_table.delete_item(Key={"pk": "temp-2"})

        timer = threading.Timer(2.0, delete_later)
        timer.start()

        try:
            result = expect_dynamodb_item(dynamodb_table).to_be_empty(
                timeout=10, poll_interval=1
            )
            assert result is None
        finally:
            timer.cancel()


class TestDynamoDBToBeNotEmpty:
    """Tests for expect_dynamodb_item(table).to_be_not_empty()."""

    def test_returns_none_when_table_has_items(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "user-1", "name": "Alice"})

        result = expect_dynamodb_item(dynamodb_table).to_be_not_empty(
            timeout=10, poll_interval=1
        )

        assert result is None

    def test_raises_timeout_when_table_empty(self, dynamodb_table):
        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_be_not_empty(
                timeout=2, poll_interval=1
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key is None
        assert exc_info.value.timeout == 2

    def test_catchable_as_base_wait_timeout_error(self, dynamodb_table):
        """DynamoDBWaitTimeoutError from to_be_not_empty is a WaitTimeoutError."""
        with pytest.raises(WaitTimeoutError):
            expect_dynamodb_item(dynamodb_table).to_be_not_empty(
                timeout=2, poll_interval=1
            )

    def test_succeeds_when_item_inserted_mid_poll(self, dynamodb_table):
        def insert_later():
            dynamodb_table.put_item(Item={"pk": "delayed", "status": "ready"})

        timer = threading.Timer(2.0, insert_later)
        timer.start()

        try:
            result = expect_dynamodb_item(dynamodb_table).to_be_not_empty(
                timeout=10, poll_interval=1
            )
            assert result is None
        finally:
            timer.cancel()


class TestDynamoDBToHaveNumericValueCloseTo:
    """Tests for expect_dynamodb_item(table).to_have_numeric_value_close_to(...)."""

    def test_returns_item_when_value_matches_exactly(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-1", "score": 42})

        result = expect_dynamodb_item(dynamodb_table).to_have_numeric_value_close_to(
            key={"pk": "item-1"},
            field="score",
            expected=42,
            delta=0,
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "item-1"
        assert result["score"] == 42

    def test_returns_item_when_value_within_delta(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": "item-2", "temperature": Decimal("98.9")})

        result = expect_dynamodb_item(dynamodb_table).to_have_numeric_value_close_to(
            key={"pk": "item-2"},
            field="temperature",
            expected=100,
            delta=2,
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "item-2"

    def test_raises_timeout_when_value_out_of_delta(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-3", "score": 50})

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_have_numeric_value_close_to(
                key={"pk": "item-3"},
                field="score",
                expected=100,
                delta=1,
                timeout=2,
                poll_interval=1,
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key == {"pk": "item-3"}
        assert exc_info.value.timeout == 2

    def test_raises_immediately_when_field_not_numeric(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-4", "score": "not-a-number"})

        with pytest.raises(DynamoDBNonNumericFieldError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_have_numeric_value_close_to(
                key={"pk": "item-4"},
                field="score",
                expected=100,
                delta=5,
                timeout=10,
                poll_interval=1,
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key == {"pk": "item-4"}
        assert exc_info.value.field == "score"
        assert exc_info.value.value == "not-a-number"

    def test_raises_timeout_when_item_missing(self, dynamodb_table: Table) -> None:
        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_have_numeric_value_close_to(
                key={"pk": "ghost"},
                field="score",
                expected=10,
                delta=1,
                timeout=2,
                poll_interval=1,
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key == {"pk": "ghost"}
        assert exc_info.value.timeout == 2

    def test_raises_timeout_when_field_absent(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": "item-5", "other": "value"})

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_have_numeric_value_close_to(
                key={"pk": "item-5"},
                field="score",
                expected=10,
                delta=1,
                timeout=2,
                poll_interval=1,
            )

        assert exc_info.value.table_name == dynamodb_table.name

    def test_catchable_as_base_wait_timeout_error(self, dynamodb_table: Table) -> None:
        """DynamoDBWaitTimeoutError is a WaitTimeoutError."""
        with pytest.raises(WaitTimeoutError):
            expect_dynamodb_item(dynamodb_table).to_have_numeric_value_close_to(
                key={"pk": "ghost"},
                field="score",
                expected=10,
                delta=1,
                timeout=2,
                poll_interval=1,
            )

    def test_succeeds_when_value_converges_mid_poll(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-6", "score": 1})

        def update_later() -> None:
            dynamodb_table.update_item(
                Key={"pk": "item-6"},
                UpdateExpression="SET score = :val",
                ExpressionAttributeValues={":val": 100},
            )

        timer = threading.Timer(2.0, update_later)
        timer.start()

        try:
            result = expect_dynamodb_item(
                dynamodb_table
            ).to_have_numeric_value_close_to(
                key={"pk": "item-6"},
                field="score",
                expected=100,
                delta=5,
                timeout=10,
                poll_interval=1,
            )
            assert result["pk"] == "item-6"
            assert abs(result["score"] - 100) <= 5
        finally:
            timer.cancel()

    def test_works_with_composite_key(self, dynamodb_composite_table: Table) -> None:
        dynamodb_composite_table.put_item(
            Item={"pk": "user-1", "sk": "order-1", "amount": Decimal("99.5")}
        )

        result = expect_dynamodb_item(
            dynamodb_composite_table
        ).to_have_numeric_value_close_to(
            key={"pk": "user-1", "sk": "order-1"},
            field="amount",
            expected=100,
            delta=1,
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "user-1"
        assert result["sk"] == "order-1"


class TestDynamoDBToNotExist:
    """Tests for expect_dynamodb_item(table).to_not_exist(key=...)."""

    def test_returns_none_when_item_absent(self, dynamodb_table):
        result = expect_dynamodb_item(dynamodb_table).to_not_exist(
            key={"pk": "ghost"}, timeout=10, poll_interval=1
        )

        assert result is None

    def test_raises_timeout_when_item_still_exists(self, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "sticky", "val": "here"})

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_not_exist(
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
            result = expect_dynamodb_item(dynamodb_table).to_not_exist(
                key={"pk": "temp"}, timeout=10, poll_interval=1
            )
            assert result is None
        finally:
            timer.cancel()
