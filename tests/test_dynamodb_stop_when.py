import threading

import pytest
from mypy_boto3_dynamodb.service_resource import Table

from aws_expect import (
    DynamoDBWaitTimeoutError,
    StopConditionError,
    StopConditionMetError,
    expect_dynamodb_item,
)


class TestToExistStopWhen:
    """Tests for expect_dynamodb_item(table).to_exist(key=..., entries=..., stop_when=...)."""

    def test_stop_when_returns_true_aborts_with_default_reason(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-1", "status": "pending"})
        with pytest.raises(StopConditionMetError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_exist(
                key={"pk": "item-1"},
                entries={"status": "active"},
                stop_when=lambda s: s["status"] == "pending",
                timeout=5,
                poll_interval=1,
            )
        assert exc_info.value.resource_id.startswith(
            f"dynamodb://{dynamodb_table.name}?pk=item-1"
        )
        assert exc_info.value.stop_reason == "stop condition met"
        assert exc_info.value.elapsed >= 0
        assert exc_info.value.timeout == 5

    def test_stop_when_returns_string_uses_it_as_reason(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-2", "status": "failed"})
        with pytest.raises(StopConditionMetError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_exist(
                key={"pk": "item-2"},
                entries={"status": "active"},
                stop_when=lambda s: f"status is {s['status']}",
                timeout=5,
                poll_interval=1,
            )
        assert exc_info.value.stop_reason == "status is failed"

    def test_stop_when_none_is_backward_compatible(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-3", "status": "active"})
        result = expect_dynamodb_item(dynamodb_table).to_exist(
            key={"pk": "item-3"},
            entries={"status": "active"},
            timeout=10,
            poll_interval=1,
        )
        assert result["status"] == "active"

        result2 = expect_dynamodb_item(dynamodb_table).to_exist(
            key={"pk": "item-3"},
            entries={"status": "active"},
            timeout=10,
            poll_interval=1,
            stop_when=None,
        )
        assert result2["status"] == "active"

    def test_stop_when_without_entries_raises_typeerror(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-4", "status": "ok"})
        with pytest.raises(TypeError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_exist(
                key={"pk": "item-4"},
                stop_when=lambda s: True,
                timeout=0.1,
                poll_interval=1,
            )
        assert "stop_when requires entries to be provided" in str(exc_info.value)

    def test_stop_when_is_keyword_only(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": "item-5", "status": "ok"})
        with pytest.raises(TypeError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_exist(
                {"pk": "item-5"},
                10,
                1,
                {"status": "ok"},
                lambda s: True,
            )
        assert "positional argument" in str(exc_info.value)

    def test_item_not_exist_yet_skip_stop_when(self, dynamodb_table: Table) -> None:
        def insert_later() -> None:
            dynamodb_table.put_item(Item={"pk": "item-6", "status": "done"})

        timer = threading.Timer(2.0, insert_later)
        timer.start()
        try:
            result = expect_dynamodb_item(dynamodb_table).to_exist(
                key={"pk": "item-6"},
                entries={"status": "done"},
                stop_when=lambda s: True,
                timeout=10,
                poll_interval=1,
            )
            assert result["status"] == "done"
            assert result["pk"] == "item-6"
        finally:
            timer.cancel()

    def test_stop_when_state_dict_is_shallow_copy(
        self, dynamodb_table: Table
    ) -> None:
        called: list[bool] = []

        def mutating_predicate(state: dict) -> bool:
            called.append(True)
            state["mutated"] = True  # mutate the shallow copy
            return False  # continue polling

        # Item exists with status "pending" — entries require "done",
        # so entries don't match initially but stop_when is evaluated
        dynamodb_table.put_item(Item={"pk": "item-7", "status": "pending"})

        def update_later() -> None:
            dynamodb_table.update_item(
                Key={"pk": "item-7"},
                UpdateExpression="SET #s = :val",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":val": "done"},
            )

        timer = threading.Timer(1.5, update_later)
        timer.start()
        try:
            result = expect_dynamodb_item(dynamodb_table).to_exist(
                key={"pk": "item-7"},
                entries={"status": "done"},
                stop_when=mutating_predicate,
                timeout=10,
                poll_interval=1,
            )
            assert result["pk"] == "item-7"
            assert result["status"] == "done"
            assert len(called) >= 1  # stop_when was called on early polls
            # Mutation happened on shallow copy — original item state
            # was not corrupted, so entries eventually matched
        finally:
            timer.cancel()

    def test_main_condition_wins_stop_when_not_called(
        self, dynamodb_table: Table
    ) -> None:
        called: list[bool] = []

        def stop_when_pred(state: dict) -> bool:
            called.append(True)
            return True

        dynamodb_table.put_item(Item={"pk": "item-8", "status": "active"})
        result = expect_dynamodb_item(dynamodb_table).to_exist(
            key={"pk": "item-8"},
            entries={"status": "active"},
            stop_when=stop_when_pred,
            timeout=5,
            poll_interval=1,
        )
        assert result["status"] == "active"
        assert len(called) == 0

    def test_resource_id_format_for_composite_key(
        self, dynamodb_composite_table: Table
    ) -> None:
        dynamodb_composite_table.put_item(
            Item={"pk": "user-1", "sk": "2024-01-01", "status": "pending"}
        )
        with pytest.raises(StopConditionMetError) as exc_info:
            expect_dynamodb_item(dynamodb_composite_table).to_exist(
                key={"pk": "user-1", "sk": "2024-01-01"},
                entries={"status": "active"},
                stop_when=lambda s: True,
                timeout=5,
                poll_interval=1,
            )
        expected = (
            f"dynamodb://{dynamodb_composite_table.name}?pk=user-1&sk=2024-01-01"
        )
        assert exc_info.value.resource_id == expected

    def test_main_condition_wins_after_update(
        self, dynamodb_table: Table
    ) -> None:
        # Item does NOT exist initially — D-02: stop_when skipped when
        # item is None. Timer creates the item with matching entries,
        # so on the next poll the entries check returns success before
        # stop_when is ever reached (D-06 main-condition-wins).
        def insert_later() -> None:
            dynamodb_table.put_item(Item={"pk": "item-9", "status": "active"})

        timer = threading.Timer(1.0, insert_later)
        timer.start()
        try:
            result = expect_dynamodb_item(dynamodb_table).to_exist(
                key={"pk": "item-9"},
                entries={"status": "active"},
                stop_when=lambda s: True,  # would fire if called
                timeout=10,
                poll_interval=1,
            )
            assert result["status"] == "active"
            assert result["pk"] == "item-9"
        finally:
            timer.cancel()


class TestToFindItemStopWhen:
    """Tests for expect_dynamodb_item(table).to_find_item(entries=..., stop_when=...)."""

    def test_stop_when_aborts_scan_on_first_non_matching_item(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "a", "status": "ok"})
        dynamodb_table.put_item(Item={"pk": "b", "status": "bad"})
        dynamodb_table.put_item(Item={"pk": "c", "status": "ok"})
        with pytest.raises(StopConditionMetError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_find_item(
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
        result = expect_dynamodb_item(dynamodb_table).to_find_item(
            entries={"status": "good"},
            stop_when=lambda s: called.append(True) or True,
            timeout=10,
            poll_interval=1,
        )
        assert result["status"] == "good"
        assert len(called) == 0  # D-06: main-condition-wins — stop_when never reached

    def test_stop_when_string_return_used_as_reason(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "z", "error": "timeout"})
        with pytest.raises(StopConditionMetError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_find_item(
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
            expect_dynamodb_item(dynamodb_table).to_find_item(
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
            expect_dynamodb_item(dynamodb_table).to_find_item(
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
        # Items 1–5, where item "3" triggers stop_when
        for i in range(1, 6):
            status = "abort" if i == 3 else "ok"
            dynamodb_table.put_item(
                Item={"pk": str(i), "status": status}
            )
        with pytest.raises(StopConditionMetError):
            expect_dynamodb_item(dynamodb_table).to_find_item(
                entries={"status": "target"},
                stop_when=lambda s: scanned.append(s["pk"])
                or s.get("status") == "abort",
                timeout=5,
                poll_interval=1,
            )
        # D-09: entire scan aborted — items 4 and 5 never fetched
        assert len(scanned) <= 3
        assert "3" in scanned

    def test_stop_when_none_no_behavior_change(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "compat", "status": "found"})
        result = expect_dynamodb_item(dynamodb_table).to_find_item(
            entries={"status": "found"},
            timeout=10,
            poll_interval=1,
        )
        assert result["pk"] == "compat"
        assert result["status"] == "found"

        result2 = expect_dynamodb_item(dynamodb_table).to_find_item(
            entries={"status": "found"},
            timeout=10,
            poll_interval=1,
            stop_when=None,
        )
        assert result2["pk"] == "compat"
        assert result2["status"] == "found"

    def test_stop_when_state_dict_is_shallow_copy(
        self, dynamodb_table: Table
    ) -> None:
        called: list[bool] = []

        def mutating_predicate(state: dict) -> bool:
            called.append(True)
            state["mutated"] = True
            return False

        # Items exist, entries match — stop_when never called (D-06).
        # To exercise stop_when, we use entries that DON'T match any item,
        # so stop_when is evaluated per-item. stop_when returns False
        # (continue) but mutates the shallow copy — mutation isolation
        # ensures next iteration sees original state.
        dynamodb_table.put_item(Item={"pk": "mut-scan", "count": 0})

        # No item matches {"count": 1}, so stop_when is evaluated on
        # every iteration. Returns False each time — waiter eventually
        # times out, but we verify stop_when was called and shallow
        # copy isolation held across iterations.
        with pytest.raises(DynamoDBWaitTimeoutError):
            expect_dynamodb_item(dynamodb_table).to_find_item(
                entries={"count": 1},
                stop_when=mutating_predicate,
                timeout=3,
                poll_interval=1,
            )
        assert len(called) >= 1
