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


class TestExpectAnyTupleForm:
    """Tests for expect_any with (fn, *args) tuple arguments."""

    def test_single_tuple_succeeds(self, dynamodb_tables: list[Table]) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "any1", "val": "first-success"})

        result: dict[str, Any] = expect_any(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    {"pk": "any1"},
                    10,
                    1,
                ),
            ]
        )

        assert result["val"] == "first-success"

    def test_first_of_multiple_tuples_succeeds(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "winner", "val": "first"})
        # tables[1] and tables[2] are empty — will timeout

        result: dict[str, Any] = expect_any(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    {"pk": "winner"},
                    10,
                    1,
                ),
                (
                    expect_dynamodb_item(tables[1]).to_exist,
                    {"pk": "missing-1"},
                    2,
                    1,
                ),
                (
                    expect_dynamodb_item(tables[2]).to_exist,
                    {"pk": "missing-2"},
                    2,
                    1,
                ),
            ]
        )

        assert result["val"] == "first"

    def test_tuple_with_kwargs_only_works(self, dynamodb_tables: list[Table]) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "kw-any", "val": "kwargs-win"})

        result: dict[str, Any] = expect_any(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    {"key": {"pk": "kw-any"}, "timeout": 10, "poll_interval": 1},
                ),
            ]
        )

        assert result["val"] == "kwargs-win"

    def test_all_tuples_timeout_raises_aggregate_error(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables

        with pytest.raises(AggregateWaitTimeoutError) as exc_info:
            expect_any(
                [
                    (
                        expect_dynamodb_item(tables[0]).to_exist,
                        {"pk": "nope-1"},
                        2,
                        1,
                    ),
                    (
                        expect_dynamodb_item(tables[1]).to_exist,
                        {"pk": "nope-2"},
                        2,
                        1,
                    ),
                    (
                        expect_dynamodb_item(tables[2]).to_exist,
                        {"pk": "nope-3"},
                        2,
                        1,
                    ),
                ]
            )

        err = exc_info.value
        assert len(err.errors) == 3
        assert all(r is None for r in err.results)

    def test_tuple_plain_callable_mixed_works(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "mix-win", "val": "mixed"})
        # tables[1] is empty — will timeout

        result: dict[str, Any] = expect_any(
            [
                lambda: expect_dynamodb_item(tables[0]).to_exist(
                    key={"pk": "mix-win"}, timeout=10, poll_interval=1
                ),
                (
                    expect_dynamodb_item(tables[1]).to_exist,
                    {
                        "key": {"pk": "missing"},
                        "timeout": 2,
                        "poll_interval": 1,
                    },
                ),
            ]
        )

        assert result["val"] == "mixed"


class TestExpectAnyMixed:
    """Tests for expect_any with mixed (fn, *args) tuples and plain callables in the same sequence."""

    def test_tuple_first_succeeds(self, dynamodb_tables: list[Table]) -> None:
        """Tuple at position 0 — it succeeds, result returned."""
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "t0", "val": "tuple-wins"})
        # tables[1] empty — will timeout

        result: dict[str, Any] = expect_any(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    {"pk": "t0"},
                    10,
                    1,
                ),
                lambda: expect_dynamodb_item(tables[1]).to_exist(
                    key={"pk": "missing"}, timeout=2, poll_interval=1
                ),
            ]
        )

        assert result["val"] == "tuple-wins"

    def test_callable_first_succeeds(self, dynamodb_tables: list[Table]) -> None:
        """Callable at position 0 — it succeeds, result returned."""
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "c0", "val": "callable-wins"})
        # tables[1] empty — will timeout

        result: dict[str, Any] = expect_any(
            [
                lambda: expect_dynamodb_item(tables[0]).to_exist(
                    key={"pk": "c0"}, timeout=10, poll_interval=1
                ),
                (
                    expect_dynamodb_item(tables[1]).to_exist,
                    {"pk": "missing"},
                    2,
                    1,
                ),
            ]
        )

        assert result["val"] == "callable-wins"

    def test_interleaved_first_tuple_wins(self, dynamodb_tables: list[Table]) -> None:
        """Sequence [tuple, callable, tuple] — first tuple succeeds, others timeout."""
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "i0", "val": "first-tuple"})
        # tables[1] and tables[2] empty — will timeout

        result: dict[str, Any] = expect_any(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    {"pk": "i0"},
                    10,
                    1,
                ),
                lambda: expect_dynamodb_item(tables[1]).to_exist(
                    key={"pk": "nope-1"}, timeout=2, poll_interval=1
                ),
                (
                    expect_dynamodb_item(tables[2]).to_exist,
                    {"pk": "nope-2"},
                    2,
                    1,
                ),
            ]
        )

        assert result["val"] == "first-tuple"

    def test_succeeds_when_any_item_wins_regardless_of_type(
        self, dynamodb_tables: list[Table]
    ) -> None:
        """One item succeeds while others timeout — type doesn't matter."""
        tables = dynamodb_tables
        # Only tables[1] (a callable) has data; tables[0] (tuple) and tables[2] (tuple) timeout
        tables[1].put_item(Item={"pk": "winner", "val": "callable-winner"})

        result: dict[str, Any] = expect_any(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    {"pk": "nope-0"},
                    2,
                    1,
                ),
                lambda: expect_dynamodb_item(tables[1]).to_exist(
                    key={"pk": "winner"}, timeout=10, poll_interval=1
                ),
                (
                    expect_dynamodb_item(tables[2]).to_exist,
                    {"pk": "nope-2"},
                    2,
                    1,
                ),
            ]
        )

        assert result["val"] == "callable-winner"

    def test_all_mixed_all_failures_raises_aggregate_error(
        self, dynamodb_tables: list[Table]
    ) -> None:
        """Every item times out — error aggregation handles mixed types uniformly."""
        tables = dynamodb_tables
        # All tables empty — all items will timeout

        with pytest.raises(AggregateWaitTimeoutError) as exc_info:
            expect_any(
                [
                    lambda: expect_dynamodb_item(tables[0]).to_exist(
                        key={"pk": "nope-0"}, timeout=2, poll_interval=1
                    ),
                    (
                        expect_dynamodb_item(tables[1]).to_exist,
                        {"pk": "nope-1"},
                        2,
                        1,
                    ),
                    lambda: expect_dynamodb_item(tables[2]).to_exist(
                        key={"pk": "nope-2"}, timeout=2, poll_interval=1
                    ),
                ]
            )

        err = exc_info.value
        assert len(err.errors) == 3
        assert all(r is None for r in err.results)
