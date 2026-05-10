import threading
import time
from typing import Any

import pytest
from mypy_boto3_dynamodb.service_resource import Table

from aws_expect import (
    AggregateWaitTimeoutError,
    DynamoDBNonNumericFieldError,
    WaitTimeoutError,
    expect_all,
    expect_dynamodb_item,
)


class TestExpectAllSuccess:
    """Tests for expect_all when all expectations succeed."""

    def test_returns_all_results_in_order(self, dynamodb_tables: list[Table]) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "a", "val": "first"})
        tables[1].put_item(Item={"pk": "b", "val": "second"})
        tables[2].put_item(Item={"pk": "c", "val": "third"})

        results = expect_all(
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

        assert len(results) == 3
        assert results[0]["val"] == "first"
        assert results[1]["val"] == "second"
        assert results[2]["val"] == "third"

    def test_runs_in_parallel_not_sequentially(
        self, dynamodb_tables: list[Table]
    ) -> None:
        """Wall-clock time should be ~max(delays), not sum(delays)."""
        tables = dynamodb_tables

        def insert_later(table: Table, key: str, delay: float) -> threading.Timer:
            def _insert() -> None:
                table.put_item(Item={"pk": key, "ready": True})

            timer = threading.Timer(delay, _insert)
            timer.start()
            return timer

        # Each item appears after ~2s. If run sequentially the total
        # would be at least 6s. In parallel it should be ~2s.
        timers = [
            insert_later(tables[0], "p1", 2.0),
            insert_later(tables[1], "p2", 2.0),
            insert_later(tables[2], "p3", 2.0),
        ]

        try:
            start = time.monotonic()
            results = expect_all(
                [
                    lambda: expect_dynamodb_item(tables[0]).to_exist(
                        key={"pk": "p1"}, timeout=10, poll_interval=1
                    ),
                    lambda: expect_dynamodb_item(tables[1]).to_exist(
                        key={"pk": "p2"}, timeout=10, poll_interval=1
                    ),
                    lambda: expect_dynamodb_item(tables[2]).to_exist(
                        key={"pk": "p3"}, timeout=10, poll_interval=1
                    ),
                ]
            )
            elapsed = time.monotonic() - start

            assert len(results) == 3
            # Should complete well under the sequential total of 6s.
            assert elapsed < 6.0
        finally:
            for t in timers:
                t.cancel()

    def test_works_with_single_expectation(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": "solo", "val": "only"})

        results = expect_all(
            [
                lambda: expect_dynamodb_item(dynamodb_table).to_exist(
                    key={"pk": "solo"}, timeout=10, poll_interval=1
                ),
            ]
        )

        assert len(results) == 1
        assert results[0]["val"] == "only"

    def test_empty_list_returns_empty_list(self) -> None:
        results = expect_all([])

        assert results == []


class TestExpectAllFailure:
    """Tests for expect_all when one or more expectations fail."""

    def test_raises_aggregate_error_when_one_fails(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "ok-1", "val": "good"})
        tables[1].put_item(Item={"pk": "ok-2", "val": "fine"})
        # tables[2] has no item — will timeout

        with pytest.raises(AggregateWaitTimeoutError) as exc_info:
            expect_all(
                [
                    lambda: expect_dynamodb_item(tables[0]).to_exist(
                        key={"pk": "ok-1"}, timeout=10, poll_interval=1
                    ),
                    lambda: expect_dynamodb_item(tables[1]).to_exist(
                        key={"pk": "ok-2"}, timeout=10, poll_interval=1
                    ),
                    lambda: expect_dynamodb_item(tables[2]).to_exist(
                        key={"pk": "missing"}, timeout=2, poll_interval=1
                    ),
                ]
            )

        err = exc_info.value
        assert len(err.errors) == 1
        assert len(err.results) == 3
        # Successful results are at indices 0 and 1
        result_0: dict[str, Any] = err.results[0]  # type: ignore[assignment]
        result_1: dict[str, Any] = err.results[1]  # type: ignore[assignment]
        assert result_0["val"] == "good"
        assert result_1["val"] == "fine"
        # Failed result is None
        assert err.results[2] is None

    def test_raises_aggregate_error_when_all_fail(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables

        with pytest.raises(AggregateWaitTimeoutError) as exc_info:
            expect_all(
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
        """AggregateWaitTimeoutError is a WaitTimeoutError."""
        with pytest.raises(WaitTimeoutError):
            expect_all(
                [
                    lambda: expect_dynamodb_item(dynamodb_table).to_exist(
                        key={"pk": "gone"}, timeout=2, poll_interval=1
                    ),
                ]
            )

    def test_aggregate_error_contains_individual_errors(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables

        with pytest.raises(AggregateWaitTimeoutError) as exc_info:
            expect_all(
                [
                    lambda: expect_dynamodb_item(tables[0]).to_exist(
                        key={"pk": "x"}, timeout=2, poll_interval=1
                    ),
                    lambda: expect_dynamodb_item(tables[1]).to_exist(
                        key={"pk": "y"}, timeout=3, poll_interval=1
                    ),
                ]
            )

        err = exc_info.value
        assert len(err.errors) == 2
        assert all(isinstance(e, WaitTimeoutError) for e in err.errors)
        assert err.timeout == 3  # max of individual timeouts

    def test_non_wait_timeout_error_propagates(self) -> None:
        """Non-WaitTimeoutError exceptions are re-raised directly."""

        def boom() -> None:
            msg = "unexpected failure"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="unexpected failure"):
            expect_all([boom])

    def test_non_numeric_field_error_propagates_immediately(
        self, dynamodb_tables: list[Table]
    ) -> None:
        """DynamoDBNonNumericFieldError must propagate immediately, not be aggregated.

        Before the fix, DynamoDBNonNumericFieldError inherited WaitTimeoutError and
        was silently swallowed into AggregateWaitTimeoutError. It must now surface
        directly so callers know they have a type error, not a timing issue.
        """
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "bad", "score": "not-a-number"})

        with pytest.raises(DynamoDBNonNumericFieldError):
            expect_all(
                [
                    lambda: expect_dynamodb_item(
                        tables[0]
                    ).to_have_numeric_value_close_to(
                        key={"pk": "bad"},
                        field="score",
                        expected=10,
                        delta=1,
                        timeout=10,
                        poll_interval=1,
                    ),
                    lambda: expect_dynamodb_item(tables[1]).to_exist(
                        key={"pk": "present"}, timeout=10, poll_interval=1
                    ),
                ]
            )

    def test_aggregate_error_message_is_descriptive(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables

        with pytest.raises(AggregateWaitTimeoutError, match=r"1 of 2.*timed out"):
            tables[0].put_item(Item={"pk": "present"})
            expect_all(
                [
                    lambda: expect_dynamodb_item(tables[0]).to_exist(
                        key={"pk": "present"}, timeout=10, poll_interval=1
                    ),
                    lambda: expect_dynamodb_item(tables[1]).to_exist(
                        key={"pk": "absent"}, timeout=2, poll_interval=1
                    ),
                ]
            )


class TestExpectAllTupleForm:
    """Tests for expect_all with (fn, args, kwargs) tuple arguments."""

    def test_single_tuple_with_args_succeeds(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "t1", "val": "first"})

        results = expect_all(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    ({"pk": "t1"}, 10, 1),
                    {},
                ),
            ]
        )

        assert len(results) == 1
        assert results[0]["val"] == "first"

    def test_multiple_tuples_return_in_order(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "a", "val": "first"})
        tables[1].put_item(Item={"pk": "b", "val": "second"})
        tables[2].put_item(Item={"pk": "c", "val": "third"})

        results = expect_all(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    ({"pk": "a"}, 10, 1),
                    {},
                ),
                (
                    expect_dynamodb_item(tables[1]).to_exist,
                    ({"pk": "b"}, 10, 1),
                    {},
                ),
                (
                    expect_dynamodb_item(tables[2]).to_exist,
                    ({"pk": "c"}, 10, 1),
                    {},
                ),
            ]
        )

        assert len(results) == 3
        assert results[0]["val"] == "first"
        assert results[1]["val"] == "second"
        assert results[2]["val"] == "third"

    def test_tuple_with_empty_args_works(self, dynamodb_tables: list[Table]) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "noargs", "val": "yes"})

        results = expect_all(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    (),
                    {"key": {"pk": "noargs"}, "timeout": 10, "poll_interval": 1},
                ),
            ]
        )

        assert results[0]["val"] == "yes"

    def test_tuple_mixed_with_plain_callable_works(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "mix1", "val": "tuple-result"})
        tables[1].put_item(Item={"pk": "mix2", "val": "lambda-result"})

        results = expect_all(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    ({"pk": "mix1"}, 10, 1),
                    {},
                ),
                lambda: expect_dynamodb_item(tables[1]).to_exist(
                    key={"pk": "mix2"}, timeout=10, poll_interval=1
                ),
            ]
        )

        assert len(results) == 2
        assert results[0]["val"] == "tuple-result"
        assert results[1]["val"] == "lambda-result"

    def test_tuple_timeout_returns_none_at_correct_index(
        self, dynamodb_tables: list[Table]
    ) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "ok", "val": "good"})
        # tables[1] is empty — will timeout

        with pytest.raises(AggregateWaitTimeoutError) as exc_info:
            expect_all(
                [
                    (
                        expect_dynamodb_item(tables[0]).to_exist,
                        ({"pk": "ok"}, 10, 1),
                        {},
                    ),
                    (
                        expect_dynamodb_item(tables[1]).to_exist,
                        ({"pk": "missing"}, 2, 1),
                        {},
                    ),
                ]
            )

        err = exc_info.value
        assert len(err.errors) == 1
        assert err.results[0] is not None
        result_0: dict[str, Any] = err.results[0]  # type: ignore[assignment]
        assert result_0["val"] == "good"
        assert err.results[1] is None

    def test_tuple_with_kwargs_only_works(self, dynamodb_tables: list[Table]) -> None:
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "kw", "val": "kwargs-test"})

        results = expect_all(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    (),
                    {
                        "key": {"pk": "kw"},
                        "timeout": 10,
                        "poll_interval": 1,
                    },
                ),
            ]
        )

        assert results[0]["val"] == "kwargs-test"


class TestExpectAllMixed:
    """Tests for expect_all with mixed (fn, args, kwargs) tuples and plain callables in the same sequence."""

    def test_tuple_first_ordering_succeeds(self, dynamodb_tables: list[Table]) -> None:
        """Tuple at position 0, callable at position 1 — both succeed."""
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "t0", "val": "tuple-result"})
        tables[1].put_item(Item={"pk": "c1", "val": "callable-result"})

        results = expect_all(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    ({"pk": "t0"}, 10, 1),
                    {},
                ),
                lambda: expect_dynamodb_item(tables[1]).to_exist(
                    key={"pk": "c1"}, timeout=10, poll_interval=1
                ),
            ]
        )

        assert len(results) == 2
        assert results[0]["val"] == "tuple-result"
        assert results[1]["val"] == "callable-result"

    def test_callable_first_ordering_succeeds(
        self, dynamodb_tables: list[Table]
    ) -> None:
        """Callable at position 0, tuple at position 1 — both succeed."""
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "c0", "val": "first"})
        tables[1].put_item(Item={"pk": "t1", "val": "second"})

        results = expect_all(
            [
                lambda: expect_dynamodb_item(tables[0]).to_exist(
                    key={"pk": "c0"}, timeout=10, poll_interval=1
                ),
                (
                    expect_dynamodb_item(tables[1]).to_exist,
                    ({"pk": "t1"}, 10, 1),
                    {},
                ),
            ]
        )

        assert len(results) == 2
        assert results[0]["val"] == "first"
        assert results[1]["val"] == "second"

    def test_interleaved_ordering_succeeds(self, dynamodb_tables: list[Table]) -> None:
        """Sequence [tuple, callable, tuple] — repeated type switching."""
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "i0", "val": "tuple-0"})
        tables[1].put_item(Item={"pk": "i1", "val": "callable-1"})
        tables[2].put_item(Item={"pk": "i2", "val": "tuple-2"})

        results = expect_all(
            [
                (
                    expect_dynamodb_item(tables[0]).to_exist,
                    ({"pk": "i0"}, 10, 1),
                    {},
                ),
                lambda: expect_dynamodb_item(tables[1]).to_exist(
                    key={"pk": "i1"}, timeout=10, poll_interval=1
                ),
                (
                    expect_dynamodb_item(tables[2]).to_exist,
                    ({"pk": "i2"}, 10, 1),
                    {},
                ),
            ]
        )

        assert len(results) == 3
        assert results[0]["val"] == "tuple-0"
        assert results[1]["val"] == "callable-1"
        assert results[2]["val"] == "tuple-2"

    def test_mixed_with_one_failure_has_none_at_correct_index(
        self, dynamodb_tables: list[Table]
    ) -> None:
        """One item times out — results list has None at correct index regardless of item type."""
        tables = dynamodb_tables
        tables[0].put_item(Item={"pk": "ok-t", "val": "tuple-ok"})
        tables[2].put_item(Item={"pk": "ok-c", "val": "callable-ok"})
        # tables[1] is empty — the callable at index 1 will timeout

        with pytest.raises(AggregateWaitTimeoutError) as exc_info:
            expect_all(
                [
                    (
                        expect_dynamodb_item(tables[0]).to_exist,
                        ({"pk": "ok-t"}, 10, 1),
                        {},
                    ),
                    lambda: expect_dynamodb_item(tables[1]).to_exist(
                        key={"pk": "missing"}, timeout=2, poll_interval=1
                    ),
                    lambda: expect_dynamodb_item(tables[2]).to_exist(
                        key={"pk": "ok-c"}, timeout=10, poll_interval=1
                    ),
                ]
            )

        err = exc_info.value
        assert len(err.errors) == 1
        assert err.results[0] is not None
        assert err.results[1] is None  # the timeout — at correct index
        assert err.results[2] is not None
        result_0: dict[str, Any] = err.results[0]  # type: ignore[assignment]
        result_2: dict[str, Any] = err.results[2]  # type: ignore[assignment]
        assert result_0["val"] == "tuple-ok"
        assert result_2["val"] == "callable-ok"

    def test_all_mixed_all_failures_raises_aggregate_error(
        self, dynamodb_tables: list[Table]
    ) -> None:
        """Every item times out — error aggregation handles mixed types uniformly."""
        tables = dynamodb_tables
        # All tables empty — all items will timeout

        with pytest.raises(AggregateWaitTimeoutError) as exc_info:
            expect_all(
                [
                    lambda: expect_dynamodb_item(tables[0]).to_exist(
                        key={"pk": "nope-0"}, timeout=2, poll_interval=1
                    ),
                    (
                        expect_dynamodb_item(tables[1]).to_exist,
                        ({"pk": "nope-1"}, 2, 1),
                        {},
                    ),
                    lambda: expect_dynamodb_item(tables[2]).to_exist(
                        key={"pk": "nope-2"}, timeout=2, poll_interval=1
                    ),
                ]
            )

        err = exc_info.value
        assert len(err.errors) == 3
        assert all(r is None for r in err.results)
