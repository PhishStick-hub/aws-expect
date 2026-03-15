import threading
import time

import pytest

from aws_expect import SQSWaitTimeoutError, WaitTimeoutError, expect_sqs


class TestSQSToHaveMessage:
    """Tests for expect_sqs(queue).to_have_message(body=...)."""

    def test_returns_message_when_body_matches(self, sqs_queue, sqs_client):
        sqs_client.send_message(QueueUrl=sqs_queue.url, MessageBody="hello")

        result = expect_sqs(sqs_queue).to_have_message(
            body="hello", timeout=5, poll_interval=1
        )

        assert result["Body"] == "hello"
        assert "MessageId" in result
        assert "ReceiptHandle" in result

    def test_raises_timeout_when_queue_empty(self, sqs_queue):
        with pytest.raises(SQSWaitTimeoutError) as exc_info:
            expect_sqs(sqs_queue).to_have_message(
                body="hello", timeout=2, poll_interval=1
            )

        assert exc_info.value.body == "hello"
        assert exc_info.value.timeout == 2
        assert exc_info.value.queue_url == sqs_queue.url

    def test_raises_timeout_when_wrong_body_present(self, sqs_queue, sqs_client):
        sqs_client.send_message(QueueUrl=sqs_queue.url, MessageBody="wrong")

        with pytest.raises(SQSWaitTimeoutError):
            expect_sqs(sqs_queue).to_have_message(
                body="right", timeout=2, poll_interval=1
            )

    def test_message_remains_visible_after_non_matching_poll(
        self, sqs_queue, sqs_client
    ):
        sqs_client.send_message(QueueUrl=sqs_queue.url, MessageBody="wrong")

        with pytest.raises(SQSWaitTimeoutError):
            expect_sqs(sqs_queue).to_have_message(
                body="right", timeout=2, poll_interval=1
            )

        # "wrong" must still be receivable — non-destructive guarantee
        response = sqs_client.receive_message(
            QueueUrl=sqs_queue.url, MaxNumberOfMessages=1
        )
        messages = response.get("Messages", [])
        assert len(messages) == 1
        assert messages[0]["Body"] == "wrong"
        # clean up
        sqs_client.delete_message(
            QueueUrl=sqs_queue.url, ReceiptHandle=messages[0]["ReceiptHandle"]
        )

    def test_returns_correct_message_from_batch(self, sqs_queue, sqs_client):
        for body in ["alpha", "beta", "target", "delta"]:
            sqs_client.send_message(QueueUrl=sqs_queue.url, MessageBody=body)

        result = expect_sqs(sqs_queue).to_have_message(
            body="target", timeout=5, poll_interval=1
        )

        assert result["Body"] == "target"

    def test_succeeds_when_message_appears_mid_poll(self, sqs_queue, sqs_client):
        def send_later() -> None:
            sqs_client.send_message(QueueUrl=sqs_queue.url, MessageBody="delayed")

        timer = threading.Timer(2.0, send_later)
        timer.start()
        try:
            result = expect_sqs(sqs_queue).to_have_message(
                body="delayed", timeout=8, poll_interval=1
            )
            assert result["Body"] == "delayed"
        finally:
            timer.cancel()

    def test_catchable_as_base_wait_timeout_error(self, sqs_queue):
        with pytest.raises(WaitTimeoutError):
            expect_sqs(sqs_queue).to_have_message(
                body="hello", timeout=2, poll_interval=1
            )


class TestSQSToConsumeMessage:
    """Tests for expect_sqs(queue).to_consume_message(body=...)."""

    def test_returns_and_deletes_matching_message(self, sqs_queue, sqs_client):
        sqs_client.send_message(QueueUrl=sqs_queue.url, MessageBody="consume-me")

        result = expect_sqs(sqs_queue).to_consume_message(
            body="consume-me", timeout=5, poll_interval=1
        )

        assert result["Body"] == "consume-me"
        # Queue must now be empty
        response = sqs_client.receive_message(
            QueueUrl=sqs_queue.url, MaxNumberOfMessages=1
        )
        assert response.get("Messages", []) == []

    def test_raises_timeout_when_queue_empty(self, sqs_queue):
        with pytest.raises(SQSWaitTimeoutError) as exc_info:
            expect_sqs(sqs_queue).to_consume_message(
                body="hello", timeout=2, poll_interval=1
            )

        assert exc_info.value.body == "hello"
        assert exc_info.value.timeout == 2

    def test_non_matching_message_restored_and_matching_consumed(
        self, sqs_queue, sqs_client
    ):
        sqs_client.send_message(QueueUrl=sqs_queue.url, MessageBody="keep-me")

        def send_target() -> None:
            sqs_client.send_message(QueueUrl=sqs_queue.url, MessageBody="consume-me")

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
        response = sqs_client.receive_message(
            QueueUrl=sqs_queue.url, MaxNumberOfMessages=1
        )
        messages = response.get("Messages", [])
        assert len(messages) == 1
        assert messages[0]["Body"] == "keep-me"
        sqs_client.delete_message(
            QueueUrl=sqs_queue.url, ReceiptHandle=messages[0]["ReceiptHandle"]
        )

    def test_only_matching_message_deleted_from_batch(self, sqs_queue, sqs_client):
        for body in ["keep-1", "delete-me", "keep-2"]:
            sqs_client.send_message(QueueUrl=sqs_queue.url, MessageBody=body)

        result = expect_sqs(sqs_queue).to_consume_message(
            body="delete-me", timeout=5, poll_interval=1
        )
        assert result["Body"] == "delete-me"

        # Remaining messages must still be visible
        time.sleep(1.0)  # allow change_message_visibility to propagate in LocalStack
        response = sqs_client.receive_message(
            QueueUrl=sqs_queue.url, MaxNumberOfMessages=10
        )
        remaining_bodies = {m["Body"] for m in response.get("Messages", [])}
        assert "delete-me" not in remaining_bodies
        assert remaining_bodies == {"keep-1", "keep-2"}
        for m in response.get("Messages", []):
            sqs_client.delete_message(
                QueueUrl=sqs_queue.url, ReceiptHandle=m["ReceiptHandle"]
            )

    def test_succeeds_when_message_appears_mid_poll(self, sqs_queue, sqs_client):
        def send_later() -> None:
            sqs_client.send_message(QueueUrl=sqs_queue.url, MessageBody="delayed")

        timer = threading.Timer(2.0, send_later)
        timer.start()
        try:
            result = expect_sqs(sqs_queue).to_consume_message(
                body="delayed", timeout=8, poll_interval=1
            )
            assert result["Body"] == "delayed"
        finally:
            timer.cancel()

    def test_catchable_as_base_wait_timeout_error(self, sqs_queue):
        with pytest.raises(WaitTimeoutError):
            expect_sqs(sqs_queue).to_consume_message(
                body="hello", timeout=2, poll_interval=1
            )
