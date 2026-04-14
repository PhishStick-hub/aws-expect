import threading
import time

import pytest
from mypy_boto3_sqs.service_resource import Queue

from aws_expect import (
    SQSUnexpectedMessageError,
    SQSWaitTimeoutError,
    WaitTimeoutError,
    expect_sqs,
)

# LocalStack needs a short settle period after change_message_visibility calls.
_LOCALSTACK_SETTLE_S = 1.0


class TestSQSToHaveMessage:
    """Tests for expect_sqs(queue).to_have_message(body=...)."""

    def test_returns_message_when_body_matches(self, sqs_queue: Queue) -> None:
        sqs_queue.send_message(MessageBody="hello")

        result = expect_sqs(sqs_queue).to_have_message(
            body="hello", timeout=5, poll_interval=1
        )

        assert result["Body"] == "hello"
        assert "MessageId" in result
        assert "ReceiptHandle" in result

    def test_raises_timeout_when_queue_empty(self, sqs_queue: Queue) -> None:
        with pytest.raises(SQSWaitTimeoutError) as exc_info:
            expect_sqs(sqs_queue).to_have_message(
                body="hello", timeout=2, poll_interval=1
            )

        assert exc_info.value.body == "hello"
        assert exc_info.value.timeout == 2
        assert exc_info.value.queue_url == sqs_queue.url

    def test_raises_timeout_when_wrong_body_present(self, sqs_queue: Queue) -> None:
        sqs_queue.send_message(MessageBody="wrong")

        with pytest.raises(SQSWaitTimeoutError):
            expect_sqs(sqs_queue).to_have_message(
                body="right", timeout=2, poll_interval=1
            )

    def test_message_remains_visible_after_non_matching_poll(
        self, sqs_queue: Queue
    ) -> None:
        sqs_queue.send_message(MessageBody="wrong")

        with pytest.raises(SQSWaitTimeoutError):
            expect_sqs(sqs_queue).to_have_message(
                body="right", timeout=2, poll_interval=1
            )

        # "wrong" must still be receivable — non-destructive guarantee
        messages = sqs_queue.receive_messages(MaxNumberOfMessages=1)
        assert len(messages) == 1
        assert messages[0].body == "wrong"
        # clean up
        messages[0].delete()

    def test_returns_correct_message_from_batch(self, sqs_queue: Queue) -> None:
        for body in ["alpha", "beta", "target", "delta"]:
            sqs_queue.send_message(MessageBody=body)

        result = expect_sqs(sqs_queue).to_have_message(
            body="target", timeout=5, poll_interval=1
        )

        assert result["Body"] == "target"

    def test_succeeds_when_message_appears_mid_poll(self, sqs_queue: Queue) -> None:
        def send_later() -> None:
            sqs_queue.send_message(MessageBody="delayed")

        timer = threading.Timer(2.0, send_later)
        timer.start()
        try:
            result = expect_sqs(sqs_queue).to_have_message(
                body="delayed", timeout=8, poll_interval=1
            )
            assert result["Body"] == "delayed"
        finally:
            timer.cancel()

    def test_catchable_as_base_wait_timeout_error(self, sqs_queue: Queue) -> None:
        with pytest.raises(WaitTimeoutError):
            expect_sqs(sqs_queue).to_have_message(
                body="hello", timeout=2, poll_interval=1
            )


class TestSQSToConsumeMessage:
    """Tests for expect_sqs(queue).to_consume_message(body=...)."""

    def test_returns_and_deletes_matching_message(self, sqs_queue: Queue) -> None:
        sqs_queue.send_message(MessageBody="consume-me")

        result = expect_sqs(sqs_queue).to_consume_message(
            body="consume-me", timeout=5, poll_interval=1
        )

        assert result["Body"] == "consume-me"
        # Queue must now be empty
        messages = sqs_queue.receive_messages(MaxNumberOfMessages=1)
        assert messages == []

    def test_raises_timeout_when_queue_empty(self, sqs_queue: Queue) -> None:
        with pytest.raises(SQSWaitTimeoutError) as exc_info:
            expect_sqs(sqs_queue).to_consume_message(
                body="hello", timeout=2, poll_interval=1
            )

        assert exc_info.value.body == "hello"
        assert exc_info.value.timeout == 2

    def test_non_matching_message_restored_and_matching_consumed(
        self, sqs_queue: Queue
    ) -> None:
        sqs_queue.send_message(MessageBody="keep-me")

        def send_target() -> None:
            sqs_queue.send_message(MessageBody="consume-me")

        timer = threading.Timer(2.0, send_target)
        timer.start()
        try:
            result = expect_sqs(sqs_queue).to_consume_message(
                body="consume-me", timeout=8, poll_interval=1
            )
            assert result["Body"] == "consume-me"
        finally:
            timer.cancel()

        # "keep-me" must still be visible
        messages = sqs_queue.receive_messages(MaxNumberOfMessages=1)
        assert len(messages) == 1
        assert messages[0].body == "keep-me"
        messages[0].delete()

    def test_only_matching_message_deleted_from_batch(self, sqs_queue: Queue) -> None:
        for body in ["keep-1", "delete-me", "keep-2"]:
            sqs_queue.send_message(MessageBody=body)

        result = expect_sqs(sqs_queue).to_consume_message(
            body="delete-me", timeout=5, poll_interval=1
        )
        assert result["Body"] == "delete-me"

        # Remaining messages must still be visible
        time.sleep(
            _LOCALSTACK_SETTLE_S
        )  # allow change_message_visibility to propagate in LocalStack
        messages = sqs_queue.receive_messages(MaxNumberOfMessages=10)
        remaining_bodies = {m.body for m in messages}
        assert "delete-me" not in remaining_bodies
        assert remaining_bodies == {"keep-1", "keep-2"}
        for m in messages:
            m.delete()

    def test_succeeds_when_message_appears_mid_poll(self, sqs_queue: Queue) -> None:
        def send_later() -> None:
            sqs_queue.send_message(MessageBody="delayed")

        timer = threading.Timer(2.0, send_later)
        timer.start()
        try:
            result = expect_sqs(sqs_queue).to_consume_message(
                body="delayed", timeout=8, poll_interval=1
            )
            assert result["Body"] == "delayed"
        finally:
            timer.cancel()

    def test_catchable_as_base_wait_timeout_error(self, sqs_queue: Queue) -> None:
        with pytest.raises(WaitTimeoutError):
            expect_sqs(sqs_queue).to_consume_message(
                body="hello", timeout=2, poll_interval=1
            )


class TestSQSToNotHaveMessage:
    """Tests for expect_sqs(queue).to_not_have_message(body=...)."""

    def test_returns_none_when_queue_is_empty(self, sqs_queue: Queue) -> None:
        result = expect_sqs(sqs_queue).to_not_have_message(body="absent", delay=1)
        assert result is None

    def test_returns_none_when_different_body_present(self, sqs_queue: Queue) -> None:
        sqs_queue.send_message(MessageBody="other")
        result = expect_sqs(sqs_queue).to_not_have_message(body="absent", delay=1)
        assert result is None
        # clean up
        sqs_queue.receive_messages(MaxNumberOfMessages=1)[0].delete()

    def test_raises_when_message_present(self, sqs_queue: Queue) -> None:
        sqs_queue.send_message(MessageBody="bad-message")

        with pytest.raises(SQSUnexpectedMessageError) as exc_info:
            expect_sqs(sqs_queue).to_not_have_message(body="bad-message", delay=1)

        assert exc_info.value.body == "bad-message"
        assert exc_info.value.delay == 1
        assert exc_info.value.queue_url == sqs_queue.url

    def test_message_remains_visible_after_failed_check(self, sqs_queue: Queue) -> None:
        sqs_queue.send_message(MessageBody="present")

        with pytest.raises(SQSUnexpectedMessageError):
            expect_sqs(sqs_queue).to_not_have_message(body="present", delay=1)

        # message must still be receivable (VisibilityTimeout=0)
        messages = sqs_queue.receive_messages(MaxNumberOfMessages=1)
        assert len(messages) == 1
        assert messages[0].body == "present"
        messages[0].delete()

    def test_not_a_wait_timeout_error(self, sqs_queue: Queue) -> None:
        sqs_queue.send_message(MessageBody="present")

        with pytest.raises(SQSUnexpectedMessageError) as exc_info:
            expect_sqs(sqs_queue).to_not_have_message(body="present", delay=1)

        assert not isinstance(exc_info.value, WaitTimeoutError)
