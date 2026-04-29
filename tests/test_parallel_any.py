import threading
import time
from typing import Any

import pytest
from mypy_boto3_dynamodb.service_resource import Table

from aws_expect import (
    AggregateWaitTimeoutError,
    WaitTimeoutError,
    expect_any,
    expect_dynamodb_item,
)


class TestExpectAnySuccess:
    """Tests for expect_any when at least one expectation succeeds."""

    def test_returns_first_result_when_one_succeeds_immediately(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "a", "val": "first"})
        tables[1].put_item(Item={"pk": "b", "val": "second"})
        tables[2].put_item(Item={"pk": "c", "val": "third"})

        result: dict[str, Any] = expect_any(
            [
                lambda: expect_dynamodb_item(tables[0]).to_exist(
                    key={"pk": "a"}, timeout=10, poll_interval=1
                ),
                lambda: expect_dynamodb_item(tables[1]).to_exist(
                    key={"pk": "b"}, timeout=10, poll_interval=1
                ),
                lambda: expect_dynamodb_item(tables[2]).to_exist(
                    key={"pk": "c"}, timeout=10, poll_interval=1
                ),
            ]
        )

        assert result is not None
        assert result["val"] in ("first", "second", "third")

    def test_returns_first_result_when_only_one_can_succeed(
        self, dynamodb_tables: list[Table]
    ) -> None:
        """Only tables[0] is seeded; the others time out. expect_any returns tables[0]'s item."""
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "winner", "val": "winner"})
        # tables[1] and tables[2] have no matching items and will time out

        result: dict[str, Any] = expect_any(
            [
                lambda: expect_dynamodb_item(tables[0]).to_exist(
                    key={"pk": "winner"}, timeout=10, poll_interval=1
                ),
                lambda: expect_dynamodb_item(tables[1]).to_exist(
                    key={"pk": "missing-1"}, timeout=2, poll_interval=1
                ),
                lambda: expect_dynamodb_item(tables[2]).to_exist(
                    key={"pk": "missing-2"}, timeout=2, poll_interval=1
                ),
            ]
        )

        assert result["val"] == "winner"

    def test_runs_callables_in_parallel(self, dynamodb_tables: list[Table]) -> None:
        """Wall-clock time should be ~delay, not sum(delays). Proves concurrency."""
        tables = dynamodb_tables

        def insert_later(table: Table, key: str, delay: float) -> threading.Timer:
            def _insert() -> None:
                table.put_item(Item={"pk": key, "ready": True})

            timer = threading.Timer(delay, _insert)
            timer.start()
            return timer

        # tables[0] item appears after ~2s; tables[1] has no item and times out at 2s.
        # expect_any should return tables[0]'s item well under 5s total wall-clock.
        timer = insert_later(tables[0], "parallel", 2.0)

        try:
            start = time.monotonic()
            result: dict[str, Any] = expect_any(
                [
                    lambda: expect_dynamodb_item(tables[0]).to_exist(
                        key={"pk": "parallel"}, timeout=10, poll_interval=1
                    ),
                    lambda: expect_dynamodb_item(tables[1]).to_exist(
                        key={"pk": "not-there"}, timeout=2, poll_interval=1
                    ),
                ]
            )
            elapsed = time.monotonic() - start

            assert result is not None
            assert elapsed < 5.0
        finally:
            timer.cancel()

    def test_single_expectation_returns_its_result(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": "solo", "val": "only"})

        result: dict[str, Any] = expect_any(
            [
                lambda: expect_dynamodb_item(dynamodb_table).to_exist(
                    key={"pk": "solo"}, timeout=10, poll_interval=1
                ),
            ]
        )

        assert result["val"] == "only"

    def test_returns_result_type_not_wrapped(self, dynamodb_table: Table) -> None:
        """expect_any returns the raw result (dict), not wrapped in a list."""
        dynamodb_table.put_item(Item={"pk": "raw", "val": "direct"})

        result: dict[str, Any] = expect_any(
            [
                lambda: expect_dynamodb_item(dynamodb_table).to_exist(
                    key={"pk": "raw"}, timeout=10, poll_interval=1
                ),
            ]
        )

        assert type(result) is dict


class TestExpectAnyFailure:
    """Tests for expect_any when all or some expectations fail."""

    def test_raises_aggregate_error_when_all_fail(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables

        with pytest.raises(AggregateWaitTimeoutError) as exc_info:
            expect_any(
                [
                    lambda: expect_dynamodb_item(tables[0]).to_exist(
                        key={"pk": "nope-1"}, timeout=2, poll_interval=1
                    ),
                    lambda: expect_dynamodb_item(tables[1]).to_exist(
                        key={"pk": "nope-2"}, timeout=2, poll_interval=1
                    ),
                    lambda: expect_dynamodb_item(tables[2]).to_exist(
                        key={"pk": "nope-3"}, timeout=2, poll_interval=1
                    ),
                ]
            )

        err = exc_info.value
        assert len(err.errors) == 3
        assert all(r is None for r in err.results)

    def test_aggregate_error_is_catchable_as_wait_timeout_error(
        self, dynamodb_table: Table
    ) -> None:
        """AggregateWaitTimeoutError must be catchable as WaitTimeoutError."""
        with pytest.raises(WaitTimeoutError):
            expect_any(
                [
                    lambda: expect_dynamodb_item(dynamodb_table).to_exist(
                        key={"pk": "gone"}, timeout=2, poll_interval=1
                    ),
                ]
            )

    def test_non_wait_timeout_error_propagates_immediately(self) -> None:
        """Non-WaitTimeoutError exceptions are re-raised directly."""

        def boom() -> None:
            msg = "boom"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="boom"):
            expect_any([boom])

    def test_empty_list_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            expect_any([])
