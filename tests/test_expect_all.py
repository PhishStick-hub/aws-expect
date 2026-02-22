import threading
import time
from typing import Any

import pytest

from aws_expect import (
    AggregateWaitTimeoutError,
    WaitTimeoutError,
    expect_all,
    expect_dynamodb_item,
)


class TestExpectAllSuccess:
    """Tests for expect_all when all expectations succeed."""

    def test_returns_all_results_in_order(self, dynamodb_tables):
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

    def test_runs_in_parallel_not_sequentially(self, dynamodb_tables):
        """Wall-clock time should be ~max(delays), not sum(delays)."""
        tables = dynamodb_tables

        def insert_later(table, key, delay):
            def _insert():
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

    def test_works_with_single_expectation(self, dynamodb_table):
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

    def test_empty_list_returns_empty_list(self):
        results = expect_all([])

        assert results == []


class TestExpectAllFailure:
    """Tests for expect_all when one or more expectations fail."""

    def test_raises_aggregate_error_when_one_fails(self, dynamodb_tables):
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

    def test_raises_aggregate_error_when_all_fail(self, dynamodb_tables):
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

    def test_aggregate_error_is_catchable_as_wait_timeout_error(self, dynamodb_table):
        """AggregateWaitTimeoutError is a WaitTimeoutError."""
        with pytest.raises(WaitTimeoutError):
            expect_all(
                [
                    lambda: expect_dynamodb_item(dynamodb_table).to_exist(
                        key={"pk": "gone"}, timeout=2, poll_interval=1
                    ),
                ]
            )

    def test_aggregate_error_contains_individual_errors(self, dynamodb_tables):
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

    def test_non_wait_timeout_error_propagates(self):
        """Non-WaitTimeoutError exceptions are re-raised directly."""

        def boom():
            msg = "unexpected failure"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="unexpected failure"):
            expect_all([boom])

    def test_aggregate_error_message_is_descriptive(self, dynamodb_tables):
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
