import json
import threading
import time
from typing import Any

import pytest
from mypy_boto3_sqs.service_resource import Queue

from aws_expect import (
    SQSEventWaitTimeoutError,
    SQSUnexpectedEventError,
    SQSWaitTimeoutError,
    WaitTimeoutError,
    expect_sqs,
)


def _send_event(queue: Queue, event: dict[str, Any]) -> None:
    """Helper: send a JSON-serialised event to the queue."""
    queue.send_message(MessageBody=json.dumps(event))


class TestSQSToHaveEvent:
    """Tests for expect_sqs(queue).to_have_event(event=...)."""

    def test_returns_message_on_exact_match(self, sqs_queue: Queue) -> None:
        _send_event(sqs_queue, {"source": "my-app", "detail-type": "OrderPlaced"})

        result = expect_sqs(sqs_queue).to_have_event(
            event={"source": "my-app", "detail-type": "OrderPlaced"},
            timeout=5,
            poll_interval=1,
        )

        assert json.loads(result["Body"]) == {
            "source": "my-app",
            "detail-type": "OrderPlaced",
        }
        assert "MessageId" in result
        assert "ReceiptHandle" in result

    def test_returns_message_on_subset_match(self, sqs_queue: Queue) -> None:
        """Extra fields in the body are ignored."""
        _send_event(
            sqs_queue,
            {"source": "my-app", "detail-type": "OrderPlaced", "version": "0"},
        )

        result = expect_sqs(sqs_queue).to_have_event(
            event={"source": "my-app"},
            timeout=5,
            poll_interval=1,
        )

        assert json.loads(result["Body"])["source"] == "my-app"

    def test_deep_nested_match(self, sqs_queue: Queue) -> None:
        _send_event(
            sqs_queue,
            {"source": "my-app", "detail": {"orderId": "123", "status": "placed"}},
        )

        result = expect_sqs(sqs_queue).to_have_event(
            event={"detail": {"orderId": "123"}},
            timeout=5,
            poll_interval=1,
        )

        assert json.loads(result["Body"])["detail"]["orderId"] == "123"

    def test_non_json_body_skipped_polling_continues(self, sqs_queue: Queue) -> None:
        """Non-JSON body is ignored; polling continues until a matching JSON message arrives."""
        sqs_queue.send_message(MessageBody="not-json")

        def send_event_later() -> None:
            _send_event(sqs_queue, {"source": "my-app"})

        timer = threading.Timer(2.0, send_event_later)
        timer.start()
        try:
            result = expect_sqs(sqs_queue).to_have_event(
                event={"source": "my-app"},
                timeout=8,
                poll_interval=1,
            )
            assert json.loads(result["Body"])["source"] == "my-app"
        finally:
            timer.cancel()

    def test_raises_timeout_when_queue_empty(self, sqs_queue: Queue) -> None:
        with pytest.raises(SQSEventWaitTimeoutError) as exc_info:
            expect_sqs(sqs_queue).to_have_event(
                event={"source": "my-app"},
                timeout=2,
                poll_interval=1,
            )

        assert exc_info.value.event == {"source": "my-app"}
        assert exc_info.value.timeout == 2
        assert exc_info.value.queue_url == sqs_queue.url

    def test_raises_timeout_when_wrong_event_present(self, sqs_queue: Queue) -> None:
        _send_event(sqs_queue, {"source": "other-app"})

        with pytest.raises(SQSEventWaitTimeoutError):
            expect_sqs(sqs_queue).to_have_event(
                event={"source": "my-app"},
                timeout=2,
                poll_interval=1,
            )

    def test_exception_chain_cause_is_sqs_wait_timeout_error(
        self, sqs_queue: Queue
    ) -> None:
        """__cause__ must be SQSWaitTimeoutError to preserve exception chain."""
        with pytest.raises(SQSEventWaitTimeoutError) as exc_info:
            expect_sqs(sqs_queue).to_have_event(
                event={"source": "my-app"},
                timeout=2,
                poll_interval=1,
            )

        assert isinstance(exc_info.value.__cause__, SQSWaitTimeoutError)

    def test_non_matching_messages_remain_visible(self, sqs_queue: Queue) -> None:
        """Non-destructive: message stays visible after a failed poll."""
        _send_event(sqs_queue, {"source": "other-app"})

        with pytest.raises(SQSEventWaitTimeoutError):
            expect_sqs(sqs_queue).to_have_event(
                event={"source": "my-app"},
                timeout=2,
                poll_interval=1,
            )

        messages = sqs_queue.receive_messages(MaxNumberOfMessages=1)
        assert len(messages) == 1
        assert json.loads(messages[0].body)["source"] == "other-app"
        messages[0].delete()

    def test_succeeds_when_event_appears_mid_poll(self, sqs_queue: Queue) -> None:
        def send_later() -> None:
            _send_event(sqs_queue, {"source": "my-app", "detail": {"id": "42"}})

        timer = threading.Timer(2.0, send_later)
        timer.start()
        try:
            result = expect_sqs(sqs_queue).to_have_event(
                event={"detail": {"id": "42"}},
                timeout=8,
                poll_interval=1,
            )
            assert json.loads(result["Body"])["detail"]["id"] == "42"
        finally:
            timer.cancel()

    def test_catchable_as_wait_timeout_error(self, sqs_queue: Queue) -> None:
        with pytest.raises(WaitTimeoutError):
            expect_sqs(sqs_queue).to_have_event(
                event={"source": "my-app"},
                timeout=2,
                poll_interval=1,
            )

    def test_not_catchable_as_sqs_wait_timeout_error(self, sqs_queue: Queue) -> None:
        """SQSEventWaitTimeoutError does NOT inherit SQSWaitTimeoutError."""
        with pytest.raises(SQSEventWaitTimeoutError):
            expect_sqs(sqs_queue).to_have_event(
                event={"source": "my-app"},
                timeout=2,
                poll_interval=1,
            )
        # Verify the hierarchy separately
        exc = SQSEventWaitTimeoutError("url", {"k": "v"}, 1.0)
        assert not isinstance(exc, SQSWaitTimeoutError)


class TestSQSToConsumeEvent:
    """Tests for expect_sqs(queue).to_consume_event(event=...)."""

    def test_returns_and_deletes_matching_message(self, sqs_queue: Queue) -> None:
        _send_event(sqs_queue, {"source": "my-app"})

        result = expect_sqs(sqs_queue).to_consume_event(
            event={"source": "my-app"},
            timeout=5,
            poll_interval=1,
        )

        assert json.loads(result["Body"])["source"] == "my-app"
        messages = sqs_queue.receive_messages(MaxNumberOfMessages=1)
        assert messages == []

    def test_non_matched_in_match_batch_restored(self, sqs_queue: Queue) -> None:
        """Non-matching messages in same batch as match are restored."""
        _send_event(sqs_queue, {"source": "keep-me"})
        _send_event(sqs_queue, {"source": "delete-me"})

        result = expect_sqs(sqs_queue).to_consume_event(
            event={"source": "delete-me"},
            timeout=5,
            poll_interval=1,
        )
        assert json.loads(result["Body"])["source"] == "delete-me"

        time.sleep(1.0)  # allow change_message_visibility to propagate in LocalStack
        messages = sqs_queue.receive_messages(MaxNumberOfMessages=10)
        bodies = [json.loads(m.body)["source"] for m in messages]
        assert "delete-me" not in bodies
        assert "keep-me" in bodies
        for m in messages:
            m.delete()

    def test_non_matched_in_no_match_batch_restored(self, sqs_queue: Queue) -> None:
        """Non-matching messages in a no-match batch are restored so polling can continue."""
        _send_event(sqs_queue, {"source": "keep-me"})

        def send_target() -> None:
            _send_event(sqs_queue, {"source": "target"})

        timer = threading.Timer(2.0, send_target)
        timer.start()
        try:
            result = expect_sqs(sqs_queue).to_consume_event(
                event={"source": "target"},
                timeout=8,
                poll_interval=1,
            )
            assert json.loads(result["Body"])["source"] == "target"
        finally:
            timer.cancel()

        time.sleep(1.0)
        messages = sqs_queue.receive_messages(MaxNumberOfMessages=10)
        bodies = [json.loads(m.body)["source"] for m in messages]
        assert "keep-me" in bodies
        for m in messages:
            m.delete()

    def test_raises_timeout_when_queue_empty(self, sqs_queue: Queue) -> None:
        with pytest.raises(SQSEventWaitTimeoutError) as exc_info:
            expect_sqs(sqs_queue).to_consume_event(
                event={"source": "my-app"},
                timeout=2,
                poll_interval=1,
            )

        assert exc_info.value.event == {"source": "my-app"}
        assert exc_info.value.timeout == 2

    def test_succeeds_when_event_appears_mid_poll(self, sqs_queue: Queue) -> None:
        def send_later() -> None:
            _send_event(sqs_queue, {"source": "my-app"})

        timer = threading.Timer(2.0, send_later)
        timer.start()
        try:
            result = expect_sqs(sqs_queue).to_consume_event(
                event={"source": "my-app"},
                timeout=8,
                poll_interval=1,
            )
            assert json.loads(result["Body"])["source"] == "my-app"
        finally:
            timer.cancel()


class TestSQSToNotHaveEvent:
    """Tests for expect_sqs(queue).to_not_have_event(event=...)."""

    def test_returns_none_when_queue_empty(self, sqs_queue: Queue) -> None:
        result = expect_sqs(sqs_queue).to_not_have_event(
            event={"source": "my-app"}, delay=1
        )
        assert result is None

    def test_returns_none_when_non_matching_event_present(
        self, sqs_queue: Queue
    ) -> None:
        _send_event(sqs_queue, {"source": "other-app"})

        result = expect_sqs(sqs_queue).to_not_have_event(
            event={"source": "my-app"}, delay=1
        )
        assert result is None

        sqs_queue.receive_messages(MaxNumberOfMessages=1)[0].delete()

    def test_raises_when_matching_event_found(self, sqs_queue: Queue) -> None:
        _send_event(sqs_queue, {"source": "bad-app", "detail-type": "Alert"})

        with pytest.raises(SQSUnexpectedEventError) as exc_info:
            expect_sqs(sqs_queue).to_not_have_event(
                event={"source": "bad-app"},
                delay=1,
            )

        assert exc_info.value.event == {"source": "bad-app"}
        assert exc_info.value.delay == 1
        assert exc_info.value.queue_url == sqs_queue.url

    def test_not_a_wait_timeout_error(self, sqs_queue: Queue) -> None:
        _send_event(sqs_queue, {"source": "bad-app"})

        with pytest.raises(SQSUnexpectedEventError) as exc_info:
            expect_sqs(sqs_queue).to_not_have_event(
                event={"source": "bad-app"}, delay=1
            )

        assert not isinstance(exc_info.value, WaitTimeoutError)

    def test_delay_zero_clamped_to_one_second(self, sqs_queue: Queue) -> None:
        """delay=0 must still wait at least 1 second (_compute_delay clamps it)."""
        start = time.monotonic()
        expect_sqs(sqs_queue).to_not_have_event(event={"source": "x"}, delay=0)
        elapsed = time.monotonic() - start
        assert elapsed >= 1.0
