import json
import threading

import pytest
from mypy_boto3_s3.service_resource import S3ServiceResource

from aws_expect import StopConditionError, StopConditionMetError, expect_s3


class TestToExistStopWhen:
    """Tests for expect_s3(s3_object).to_exist(entries=..., stop_when=...)."""

    def test_stop_when_returns_true_aborts_with_default_reason(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-true"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "pending"}).encode()
        )
        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(StopConditionMetError) as exc_info:
            expect_s3(obj).to_exist(
                entries={"status": "active"},
                stop_when=lambda s: s["status"] == "pending",
                timeout=5,
                poll_interval=1,
            )
        assert exc_info.value.resource_id == f"s3://{test_bucket}/{key}"
        assert exc_info.value.stop_reason == "stop condition met"
        assert exc_info.value.elapsed >= 0
        assert exc_info.value.timeout == 5

    def test_stop_when_returns_string_uses_it_as_reason(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-str"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "failed"}).encode()
        )
        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(StopConditionMetError) as exc_info:
            expect_s3(obj).to_exist(
                entries={"status": "active"},
                stop_when=lambda s: f"status is {s['status']}",
                timeout=5,
                poll_interval=1,
            )
        assert exc_info.value.stop_reason == "status is failed"

    def test_stop_when_none_is_backward_compatible(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-none"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "active"}).encode()
        )
        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_exist(
            entries={"status": "active"}, timeout=10, poll_interval=1
        )
        assert result["status"] == "active"

        result2 = expect_s3(obj).to_exist(
            entries={"status": "active"},
            stop_when=None,
            timeout=10,
            poll_interval=1,
        )
        assert result2["status"] == "active"

    def test_stop_when_without_entries_raises_typeerror(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-typeerror"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "active"}).encode()
        )
        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(TypeError, match="stop_when requires entries"):
            expect_s3(obj).to_exist(stop_when=lambda s: True, timeout=1)

    def test_stop_when_is_keyword_only(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-kwonly"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "active"}).encode()
        )
        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(TypeError):
            expect_s3(obj).to_exist({"status": "active"}, lambda s: True)  # type: ignore[arg-type]

    def test_object_not_exist_yet_skip_stop_when(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-skip-none"
        stop_checked: list[bool] = []

        def stop_always(state: dict) -> bool:
            stop_checked.append(True)
            return True

        def create_object() -> None:
            s3_resource.Object(test_bucket, key).put(
                Body=json.dumps({"status": "done"}).encode()
            )

        timer = threading.Timer(2.0, create_object)
        timer.start()
        try:
            obj = s3_resource.Object(test_bucket, key)
            result = expect_s3(obj).to_exist(
                entries={"status": "done"},
                stop_when=stop_always,
                timeout=10,
                poll_interval=1,
            )
            assert result["status"] == "done"
        finally:
            timer.cancel()

    def test_stop_when_state_dict_is_shallow_copy(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-shallow"
        s3_resource.Object(test_bucket, key).put(Body=json.dumps({"count": 0}).encode())
        iterations: list[int] = [0]

        def mutation_checking_stop(state: dict) -> bool:
            iterations[0] += 1
            if iterations[0] == 1:
                state["mutated"] = True
                return False
            assert "mutated" not in state
            return True

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(StopConditionMetError):
            expect_s3(obj).to_exist(
                entries={"count": 999},
                stop_when=mutation_checking_stop,
                timeout=10,
                poll_interval=1,
            )

    def test_main_condition_wins_stop_when_not_called(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-mcw"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "active"}).encode()
        )
        called: list[int] = []

        def stop_pred(state: dict) -> bool:
            called.append(1)
            return True

        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_exist(
            entries={"status": "active"},
            stop_when=stop_pred,
            timeout=5,
            poll_interval=1,
        )
        assert result["status"] == "active"
        assert len(called) == 0

    def test_main_condition_wins_after_update(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-mcw-update"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "pending"}).encode()
        )
        stop_called: list[int] = []

        def update_object() -> None:
            s3_resource.Object(test_bucket, key).put(
                Body=json.dumps({"status": "active"}).encode()
            )

        timer = threading.Timer(1.5, update_object)
        timer.start()
        try:
            obj = s3_resource.Object(test_bucket, key)
            result = expect_s3(obj).to_exist(
                entries={"status": "active"},
                stop_when=lambda s: stop_called.append(1) or False,
                timeout=10,
                poll_interval=0.5,
            )
            assert result["status"] == "active"
            assert len(stop_called) >= 1
        finally:
            timer.cancel()

    def test_predicate_raises_valueerror_wraps_in_stop_condition_error(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-crash"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "pending"}).encode()
        )
        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(StopConditionError) as exc_info:
            expect_s3(obj).to_exist(
                entries={"status": "active"},
                stop_when=lambda s: (_ for _ in ()).throw(ValueError("bad state")),
                timeout=5,
                poll_interval=1,
            )
        assert exc_info.value.resource_id == f"s3://{test_bucket}/{key}"
        assert isinstance(exc_info.value.__cause__, ValueError)
        assert "bad state" in str(exc_info.value)

    def test_predicate_raises_stop_condition_met_error_directly(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-re-raise"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "pending"}).encode()
        )

        def custom_stop(state: dict) -> bool:
            raise StopConditionMetError("custom-id", "custom reason", 0.0, 30.0)

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(StopConditionMetError) as exc_info:
            expect_s3(obj).to_exist(
                entries={"status": "active"},
                stop_when=custom_stop,
                timeout=5,
                poll_interval=1,
            )
        assert exc_info.value.resource_id == "custom-id"
        assert exc_info.value.stop_reason == "custom reason"

    def test_stop_when_receives_parsed_body_as_state_dict(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "test-key-state"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"nested": {"key": "value"}, "list": [1, 2, 3]}).encode()
        )
        captured: list[dict] = []

        def capture_state(state: dict) -> bool:
            captured.append(state.copy())
            return isinstance(state.get("nested"), dict) and state["list"] == [1, 2, 3]

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(StopConditionMetError) as exc_info:
            expect_s3(obj).to_exist(
                entries={"nested": {"key": "different"}},
                stop_when=capture_state,
                timeout=5,
                poll_interval=1,
            )
        assert exc_info.value.stop_reason == "stop condition met"
        assert len(captured) >= 1
        assert captured[0] == {"nested": {"key": "value"}, "list": [1, 2, 3]}
