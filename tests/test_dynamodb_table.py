import threading
from contextlib import suppress
from uuid import uuid4

import pytest
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

from aws_expect import (
    DynamoDBWaitTimeoutError,
    StopConditionError,
    StopConditionMetError,
    WaitTimeoutError,
    expect_dynamodb_table,
)


class TestDynamoDBTableToExist:
    """Tests for expect_dynamodb_table(table).to_exist()."""

    def test_returns_description_when_table_exists(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        result = expect_dynamodb_table(dynamodb_table).to_exist(
            timeout=10, poll_interval=1
        )

        assert result["TableName"] == dynamodb_table.name
        assert result["TableStatus"] == "ACTIVE"
        assert "KeySchema" in result

    def test_raises_timeout_when_table_missing(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        table_name = f"nonexistent-{uuid4().hex[:12]}"
        table = dynamodb_resource.Table(table_name)

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_table(table).to_exist(timeout=2, poll_interval=1)

        assert exc_info.value.table_name == table_name
        assert exc_info.value.key is None
        assert exc_info.value.timeout == 2

    def test_catchable_as_base_wait_timeout_error(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        """DynamoDBWaitTimeoutError from to_exist is a WaitTimeoutError."""
        table_name = f"nonexistent-{uuid4().hex[:12]}"
        table = dynamodb_resource.Table(table_name)

        with pytest.raises(WaitTimeoutError):
            expect_dynamodb_table(table).to_exist(timeout=2, poll_interval=1)

    def test_succeeds_when_table_created_mid_poll(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        table_name = f"test-{uuid4().hex[:12]}"
        table = dynamodb_resource.Table(table_name)

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
            result = expect_dynamodb_table(table).to_exist(timeout=30, poll_interval=1)
            assert result["TableName"] == table_name
            assert result["TableStatus"] == "ACTIVE"
        finally:
            timer.cancel()
            with suppress(Exception):
                dynamodb_resource.meta.client.delete_table(TableName=table_name)


class TestDynamoDBTableToNotExist:
    """Tests for expect_dynamodb_table(table).to_not_exist()."""

    def test_returns_none_when_table_absent(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        table_name = f"nonexistent-{uuid4().hex[:12]}"
        table = dynamodb_resource.Table(table_name)

        result = expect_dynamodb_table(table).to_not_exist(timeout=10, poll_interval=1)

        assert result is None

    def test_raises_timeout_when_table_still_exists(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_table(dynamodb_table).to_not_exist(
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
            expect_dynamodb_table(dynamodb_table).to_not_exist(
                timeout=2, poll_interval=1
            )

    def test_succeeds_when_table_deleted_mid_poll(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        table_name = f"test-{uuid4().hex[:12]}"
        table = dynamodb_resource.Table(table_name)

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
            result = expect_dynamodb_table(table).to_not_exist(
                timeout=30, poll_interval=1
            )
            assert result is None
        finally:
            timer.cancel()
            with suppress(Exception):
                dynamodb_resource.meta.client.delete_table(TableName=table_name)


class TestDynamoDBTableToBeEmpty:
    """Tests for expect_dynamodb_table(table).to_be_empty()."""

    def test_returns_none_when_table_is_empty(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        result = expect_dynamodb_table(dynamodb_table).to_be_empty(
            timeout=10, poll_interval=1
        )

        assert result is None

    def test_raises_timeout_when_table_has_items(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-1"})

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_table(dynamodb_table).to_be_empty(
                timeout=2, poll_interval=1
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key is None
        assert exc_info.value.timeout == 2

    def test_catchable_as_base_wait_timeout_error(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-1"})

        with pytest.raises(WaitTimeoutError):
            expect_dynamodb_table(dynamodb_table).to_be_empty(
                timeout=2, poll_interval=1
            )

    def test_raises_timeout_when_table_does_not_exist(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        table_name = f"nonexistent-{uuid4().hex[:12]}"
        table = dynamodb_resource.Table(table_name)

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_table(table).to_be_empty(timeout=2, poll_interval=1)

        assert exc_info.value.table_name == table_name

    def test_succeeds_when_items_deleted_mid_poll(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-1"})

        def delete_later() -> None:
            dynamodb_table.delete_item(Key={"pk": "item-1"})

        timer = threading.Timer(2.0, delete_later)
        timer.start()

        try:
            result = expect_dynamodb_table(dynamodb_table).to_be_empty(
                timeout=30, poll_interval=1
            )
            assert result is None
        finally:
            timer.cancel()


class TestDynamoDBTableToBeNotEmpty:
    """Tests for expect_dynamodb_table(table).to_be_not_empty()."""

    def test_returns_none_when_table_has_items(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-1"})

        result = expect_dynamodb_table(dynamodb_table).to_be_not_empty(
            timeout=10, poll_interval=1
        )

        assert result is None

    def test_raises_timeout_when_table_is_empty(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_table(dynamodb_table).to_be_not_empty(
                timeout=2, poll_interval=1
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key is None
        assert exc_info.value.timeout == 2

    def test_catchable_as_base_wait_timeout_error(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        with pytest.raises(WaitTimeoutError):
            expect_dynamodb_table(dynamodb_table).to_be_not_empty(
                timeout=2, poll_interval=1
            )

    def test_raises_timeout_when_table_does_not_exist(
        self, dynamodb_resource: DynamoDBServiceResource
    ) -> None:
        table_name = f"nonexistent-{uuid4().hex[:12]}"
        table = dynamodb_resource.Table(table_name)

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_table(table).to_be_not_empty(timeout=2, poll_interval=1)

        assert exc_info.value.table_name == table_name

    def test_succeeds_when_items_added_mid_poll(
        self, dynamodb_resource: DynamoDBServiceResource, dynamodb_table: Table
    ) -> None:
        def add_later() -> None:
            dynamodb_table.put_item(Item={"pk": "item-1"})

        timer = threading.Timer(2.0, add_later)
        timer.start()

        try:
            result = expect_dynamodb_table(dynamodb_table).to_be_not_empty(
                timeout=30, poll_interval=1
            )
            assert result is None
        finally:
            timer.cancel()


class TestToFindItemStopWhen:
    """Tests for expect_dynamodb_table(table).to_find_item(entries=..., stop_when=...)."""

    def test_stop_when_aborts_scan_on_first_non_matching_item(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "a", "status": "ok"})
        dynamodb_table.put_item(Item={"pk": "b", "status": "bad"})
        dynamodb_table.put_item(Item={"pk": "c", "status": "ok"})
        with pytest.raises(StopConditionMetError) as exc_info:
            expect_dynamodb_table(dynamodb_table).to_find_item(
                entries={"status": "target"},
                stop_when=lambda s: s["status"] == "bad",
                timeout=5,
                poll_interval=1,
            )
        assert exc_info.value.stop_reason == "stop condition met"
        assert exc_info.value.resource_id == f"dynamodb://{dynamodb_table.name}"

    def test_stop_when_does_not_fire_on_matching_item(
        self, dynamodb_table: Table
    ) -> None:
        called: list[bool] = []
        dynamodb_table.put_item(Item={"pk": "y", "status": "good"})
        result = expect_dynamodb_table(dynamodb_table).to_find_item(
            entries={"status": "good"},
            stop_when=lambda s: called.append(True) or True,
            timeout=10,
            poll_interval=1,
        )
        assert result["status"] == "good"
        assert len(called) == 0

    def test_stop_when_string_return_used_as_reason(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "z", "error": "timeout"})
        with pytest.raises(StopConditionMetError) as exc_info:
            expect_dynamodb_table(dynamodb_table).to_find_item(
                entries={"status": "ok"},
                stop_when=lambda s: f"found error: {s['error']}",
                timeout=5,
                poll_interval=1,
            )
        assert exc_info.value.stop_reason == "found error: timeout"

    def test_predicate_raises_valueerror_wraps_in_stop_condition_error(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "crash", "status": "broken"})
        with pytest.raises(StopConditionError) as exc_info:
            expect_dynamodb_table(dynamodb_table).to_find_item(
                entries={"status": "ok"},
                stop_when=lambda s: (_ for _ in ()).throw(ValueError("bad state")),
                timeout=5,
                poll_interval=1,
            )
        assert isinstance(exc_info.value.__cause__, ValueError)
        assert "bad state" in str(exc_info.value)

    def test_predicate_raises_stop_condition_met_error_directly(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "direct", "status": "nope"})

        def custom_stop(state: dict) -> str:
            raise StopConditionMetError("custom-id", "custom reason", 0.0, 30.0)

        with pytest.raises(StopConditionMetError) as exc_info:
            expect_dynamodb_table(dynamodb_table).to_find_item(
                entries={"status": "ok"},
                stop_when=custom_stop,
                timeout=5,
                poll_interval=1,
            )
        assert exc_info.value.resource_id == "custom-id"
        assert exc_info.value.stop_reason == "custom reason"

    def test_stop_when_aborts_entire_scan_no_more_items(
        self, dynamodb_table: Table
    ) -> None:
        scanned: list[str] = []
        for i in range(1, 6):
            status = "abort" if i == 3 else "ok"
            dynamodb_table.put_item(Item={"pk": str(i), "status": status})
        with pytest.raises(StopConditionMetError):
            expect_dynamodb_table(dynamodb_table).to_find_item(
                entries={"status": "target"},
                stop_when=lambda s: (
                    scanned.append(s["pk"]) or s.get("status") == "abort"
                ),
                timeout=5,
                poll_interval=1,
            )
        assert len(scanned) <= 3
        assert "3" in scanned

    def test_stop_when_none_no_behavior_change(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": "compat", "status": "found"})
        result = expect_dynamodb_table(dynamodb_table).to_find_item(
            entries={"status": "found"},
            timeout=10,
            poll_interval=1,
        )
        assert result["pk"] == "compat"
        assert result["status"] == "found"

        result2 = expect_dynamodb_table(dynamodb_table).to_find_item(
            entries={"status": "found"},
            timeout=10,
            poll_interval=1,
            stop_when=None,
        )
        assert result2["pk"] == "compat"
        assert result2["status"] == "found"

    def test_stop_when_state_dict_is_shallow_copy(self, dynamodb_table: Table) -> None:
        called: list[bool] = []

        def mutating_predicate(state: dict) -> bool:
            called.append(True)
            state["mutated"] = True
            return False

        dynamodb_table.put_item(Item={"pk": "mut-scan", "count": 0})

        with pytest.raises(DynamoDBWaitTimeoutError):
            expect_dynamodb_table(dynamodb_table).to_find_item(
                entries={"count": 1},
                stop_when=mutating_predicate,
                timeout=3,
                poll_interval=1,
            )
        assert len(called) >= 1
