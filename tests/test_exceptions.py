"""Tests for StopConditionMetError and StopConditionError."""

from __future__ import annotations

import pytest

from aws_expect.exceptions import (
    AggregateWaitTimeoutError,
    DynamoDBFindItemTimeoutError,
    DynamoDBWaitTimeoutError,
    LambdaInvocableTimeoutError,
    LambdaWaitTimeoutError,
    S3ContentWaitTimeoutError,
    S3WaitTimeoutError,
    SQSEventWaitTimeoutError,
    SQSWaitTimeoutError,
    StopConditionError,
    StopConditionMetError,
    WaitTimeoutError,
)


class TestStopConditionMetError:
    """EXN-01: StopConditionMetError signals a stop condition was met."""

    def test_is_exception_not_wait_timeout(self) -> None:
        """Not a WaitTimeoutError — retains normal Exception lineage."""
        e = StopConditionMetError("my-resource", "value matched", 1.5, 10.0)
        assert isinstance(e, Exception)
        assert not isinstance(e, WaitTimeoutError)

    def test_stores_all_fields(self) -> None:
        e = StopConditionMetError("my-resource", "value matched", 1.5, 10.0)
        assert e.resource_id == "my-resource"
        assert e.stop_reason == "value matched"
        assert e.elapsed == 1.5
        assert e.timeout == 10.0

    def test_str_format_is_pytest_assertion_style(self) -> None:
        e = StopConditionMetError("my-resource", "some value", 2.0, 5.0)
        msg = str(e)
        assert "assert" in msg
        assert "my-resource" in msg
        assert "some value" in msg
        assert "2.0" in msg
        assert "5.0" in msg

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(StopConditionMetError) as exc_info:
            raise StopConditionMetError("res-1", "matched", 0.5, 3.0)
        assert exc_info.value.resource_id == "res-1"
        assert exc_info.value.stop_reason == "matched"


class TestStopConditionError:
    """EXN-02: StopConditionError wraps a predicate exception."""

    def test_is_exception_not_wait_timeout(self) -> None:
        orig = ValueError("predicate exploded")
        e = StopConditionError("my-resource", orig)
        assert isinstance(e, Exception)
        assert not isinstance(e, WaitTimeoutError)

    def test_stores_resource_id(self) -> None:
        orig = ValueError("boom")
        e = StopConditionError("my-resource", orig)
        assert e.resource_id == "my-resource"

    def test_preserves_original_exception_via_cause(self) -> None:
        orig = ValueError("predicate exploded")
        e = StopConditionError("my-resource", orig)
        assert e.__cause__ is orig

    def test_str_includes_resource_id_and_original_message(self) -> None:
        orig = ValueError("predicate exploded")
        e = StopConditionError("my-resource", orig)
        msg = str(e)
        assert "my-resource" in msg
        assert "predicate exploded" in msg
        assert "ValueError" in msg

    def test_can_be_raised_and_caught(self) -> None:
        orig = RuntimeError("something broke")
        with pytest.raises(StopConditionError) as exc_info:
            raise StopConditionError("res-2", orig)
        assert exc_info.value.resource_id == "res-2"
        assert exc_info.value.__cause__ is orig

    def test_cause_chain_is_preserved_when_raised_from(self) -> None:
        try:
            try:
                raise TypeError("inner error")
            except TypeError as exc:
                raise StopConditionError("res-3", exc) from exc
        except StopConditionError as outer:
            assert outer.resource_id == "res-3"
            assert isinstance(outer.__cause__, TypeError)
            assert "inner error" in str(outer.__cause__)


class TestS3WaitTimeoutErrorStr:
    """ERR-02: S3WaitTimeoutError __str__ omits Expected:/Actual: when both None."""

    def test_no_expected_actual_block_when_both_none(self) -> None:
        e = S3WaitTimeoutError("my-bucket", "my-key", 10.0)
        msg = str(e)
        assert "Expected:" not in msg
        assert "Actual:" not in msg
        assert "Timed out after 10.0s waiting for s3://my-bucket/my-key" == msg

    def test_includes_bucket_and_key_in_resource_desc(self) -> None:
        e = S3WaitTimeoutError("bkt", "obj", 5.0)
        assert "s3://bkt/obj" in str(e)


class TestS3ContentWaitTimeoutErrorStr:
    """ERR-02: S3ContentWaitTimeoutError __str__ shows Expected:/Actual:."""

    def test_shows_expected_and_actual(self) -> None:
        e = S3ContentWaitTimeoutError(
            "b", "k", {"status": "ok"}, {"status": "err"}, 10.0
        )
        msg = str(e)
        assert "Expected:" in msg
        assert "Actual:" in msg
        assert "'status': 'ok'" in msg
        assert "'status': 'err'" in msg

    def test_actual_none_shows_only_expected(self) -> None:
        e = S3ContentWaitTimeoutError("b", "k", {"x": 1}, None, 10.0)
        msg = str(e)
        assert "Expected:" in msg
        assert "Actual:" not in msg


class TestDynamoDBWaitTimeoutErrorStr:
    """ERR-01, ERR-02: DynamoDBWaitTimeoutError field rename + __str__ format."""

    def test_expected_field_rename(self) -> None:
        e = DynamoDBWaitTimeoutError(
            "tbl", {"pk": "1"}, 10.0, expected={"a": 1}, actual={"b": 2}
        )
        assert e.expected == {"a": 1}

    def test_shows_expected_and_actual_in_str(self) -> None:
        e = DynamoDBWaitTimeoutError(
            "tbl", {"pk": "1"}, 10.0, expected={"a": 1}, actual={"b": 2}
        )
        msg = str(e)
        assert "Expected:" in msg
        assert "Actual:" in msg
        assert "tbl" in msg

    def test_message_override_preserves_legacy_format(self) -> None:
        """D-06: message= uses legacy format."""
        e = DynamoDBWaitTimeoutError(
            "tbl", {"pk": "1"}, 10.0, message="Custom header", actual={"b": 2}
        )
        msg = str(e)
        assert "Custom header" in msg
        assert "Actual (last seen):" in msg


class TestDynamoDBFindItemTimeoutErrorStr:
    """ERR-02: DynamoDBFindItemTimeoutError __str__."""

    def test_shows_expected_and_actual(self) -> None:
        e = DynamoDBFindItemTimeoutError("tbl", {"x": 1}, [{"y": 2}], 10.0)
        msg = str(e)
        assert "Expected:" in msg
        assert "Actual:" in msg


class TestLambdaWaitTimeoutErrorStr:
    """ERR-02: LambdaWaitTimeoutError omits Expected:/Actual: when both None."""

    def test_no_expected_actual_block(self) -> None:
        e = LambdaWaitTimeoutError("my-func", 10.0)
        msg = str(e)
        assert "Expected:" not in msg
        assert "Actual:" not in msg
        assert "my-func" in msg


class TestLambdaInvocableTimeoutErrorStr:
    """ERR-02: LambdaInvocableTimeoutError __str__."""

    def test_shows_expected_and_actual(self) -> None:
        e = LambdaInvocableTimeoutError("func", {"status": 200}, {"status": 500}, 10.0)
        msg = str(e)
        assert "Expected:" in msg
        assert "Actual:" in msg


class TestSQSWaitTimeoutErrorStr:
    """ERR-01, ERR-02: SQSWaitTimeoutError field rename + __str__."""

    def test_expected_field_rename(self) -> None:
        e = SQSWaitTimeoutError("url", "hello world", 10.0, actual=["msg1"])
        assert e.expected == "hello world"

    def test_shows_expected_and_actual(self) -> None:
        e = SQSWaitTimeoutError("url", "hello", 10.0, actual=["a", "b"])
        msg = str(e)
        assert "Expected:" in msg
        assert "Actual:" in msg


class TestSQSEventWaitTimeoutErrorStr:
    """ERR-01, ERR-02: SQSEventWaitTimeoutError field rename + __str__."""

    def test_expected_field_rename(self) -> None:
        e = SQSEventWaitTimeoutError("url", {"type": "order"}, 10.0, actual=[{"x": 1}])
        assert e.expected == {"type": "order"}

    def test_shows_expected_and_actual(self) -> None:
        e = SQSEventWaitTimeoutError("url", {"type": "order"}, 10.0, actual=[{"x": 1}])
        msg = str(e)
        assert "Expected:" in msg
        assert "Actual:" in msg


class TestAggregateWaitTimeoutErrorStr:
    """ERR-02: AggregateWaitTimeoutError auto-enriched via sub-errors."""

    def test_sub_errors_auto_enriched(self) -> None:
        ddb = DynamoDBWaitTimeoutError(
            "tbl", {"pk": "1"}, 10.0, expected={"a": 1}, actual={"b": 2}
        )
        sqs = SQSWaitTimeoutError("url", "hello", 10.0, actual=["msg1"])
        agg = AggregateWaitTimeoutError([ddb, sqs], [None, None])
        msg = str(agg)
        assert "Expected:" in msg  # from sub-errors
        assert "Actual:" in msg  # from sub-errors
        assert "2 of 2 expectations timed out" in msg
