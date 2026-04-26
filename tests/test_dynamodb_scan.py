from __future__ import annotations

import threading
import time
from uuid import uuid4

import pytest
from mypy_boto3_dynamodb.service_resource import Table

from aws_expect import (
    DynamoDBFindItemTimeoutError,
    DynamoDBUnexpectedItemError,
    DynamoDBWaitTimeoutError,
    WaitTimeoutError,
    expect_dynamodb_item,
)


class TestDynamoDBToFindItem:
    """Tests for expect_dynamodb_item(table).to_find_item(entries, ...)."""

    def test_returns_item_on_match(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": uuid4().hex, "status": "ok"})
        result = expect_dynamodb_item(dynamodb_table).to_find_item(
            {"status": "ok"}, timeout=10, poll_interval=1
        )
        assert result["status"] == "ok"

    def test_partial_dict_matches(self, dynamodb_table: Table) -> None:
        pk = uuid4().hex
        dynamodb_table.put_item(Item={"pk": pk, "x": 1, "y": 2})
        result = expect_dynamodb_item(dynamodb_table).to_find_item(
            {"x": 1}, timeout=10, poll_interval=1
        )
        assert result["pk"] == pk
        assert result["y"] == 2

    def test_deep_nested_match(self, dynamodb_table: Table) -> None:
        pk = uuid4().hex
        dynamodb_table.put_item(
            Item={"pk": pk, "meta": {"env": "prod", "region": "us"}}
        )
        result = expect_dynamodb_item(dynamodb_table).to_find_item(
            {"meta": {"env": "prod"}}, timeout=10, poll_interval=1
        )
        assert result["pk"] == pk
        assert result["meta"]["region"] == "us"

    def test_succeeds_mid_poll(self, dynamodb_table: Table) -> None:
        pk = uuid4().hex

        def insert_later() -> None:
            dynamodb_table.put_item(Item={"pk": pk, "val": "found"})

        timer = threading.Timer(2.0, insert_later)
        timer.start()
        try:
            result = expect_dynamodb_item(dynamodb_table).to_find_item(
                {"val": "found"}, timeout=10, poll_interval=1
            )
            assert result["pk"] == pk
            assert result["val"] == "found"
        finally:
            timer.cancel()

    def test_raises_timeout(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": uuid4().hex, "status": "wrong"})
        with pytest.raises(DynamoDBFindItemTimeoutError):
            expect_dynamodb_item(dynamodb_table).to_find_item(
                {"status": "right"}, timeout=2, poll_interval=1
            )

    def test_timeout_error_fields(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": uuid4().hex, "status": "wrong"})
        with pytest.raises(DynamoDBFindItemTimeoutError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_find_item(
                {"status": "right"}, timeout=2, poll_interval=1
            )
        exc = exc_info.value
        assert exc.expected == {"status": "right"}
        assert isinstance(exc.actual, list)
        assert exc.timeout == 2
        assert exc.table_name == dynamodb_table.name

    def test_catchable_as_dynamodb_timeout(self, dynamodb_table: Table) -> None:
        with pytest.raises(DynamoDBWaitTimeoutError):
            expect_dynamodb_item(dynamodb_table).to_find_item(
                {"pk": "never"}, timeout=2, poll_interval=1
            )

    def test_catchable_as_wait_timeout(self, dynamodb_table: Table) -> None:
        with pytest.raises(WaitTimeoutError):
            expect_dynamodb_item(dynamodb_table).to_find_item(
                {"pk": "never"}, timeout=2, poll_interval=1
            )


class TestDynamoDBToNotFindItem:
    """Tests for expect_dynamodb_item(table).to_not_find_item(entries, ...)."""

    def test_returns_none_when_no_match(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": uuid4().hex, "status": "ok"})
        result = expect_dynamodb_item(dynamodb_table).to_not_find_item(
            {"status": "gone"}
        )
        assert result is None

    def test_returns_none_when_table_empty(self, dynamodb_table: Table) -> None:
        result = expect_dynamodb_item(dynamodb_table).to_not_find_item({"pk": "any"})
        assert result is None

    def test_raises_when_match_found(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": uuid4().hex, "status": "here"})
        with pytest.raises(DynamoDBUnexpectedItemError):
            expect_dynamodb_item(dynamodb_table).to_not_find_item({"status": "here"})

    def test_error_context_fields(self, dynamodb_table: Table) -> None:
        pk = uuid4().hex
        dynamodb_table.put_item(Item={"pk": pk, "status": "here"})
        with pytest.raises(DynamoDBUnexpectedItemError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_not_find_item({"status": "here"})
        exc = exc_info.value
        assert exc.table_name == dynamodb_table.name
        assert exc.entries == {"status": "here"}
        assert exc.found_item["pk"] == pk
        assert exc.found_item["status"] == "here"
        assert exc.delay >= 0

    def test_not_a_wait_timeout_error(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": uuid4().hex, "status": "here"})
        with pytest.raises(DynamoDBUnexpectedItemError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_not_find_item({"status": "here"})
        assert not isinstance(exc_info.value, WaitTimeoutError)

    def test_delay_zero_clamped_to_one_second(self, dynamodb_table: Table) -> None:
        start = time.monotonic()
        result = expect_dynamodb_item(dynamodb_table).to_not_find_item(
            {"pk": "none"}, delay=0
        )
        elapsed = time.monotonic() - start
        assert result is None
        assert elapsed >= 1.0
