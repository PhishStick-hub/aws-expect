import math
import time
from typing import Any

from aws_expect.exceptions import SQSWaitTimeoutError


class SQSQueueExpectation:
    """Expectation wrapper for a boto3 SQS Queue resource."""

    def __init__(self, queue: Any) -> None:
        self._queue = queue
        self._queue_url: str = queue.url
        self._client = queue.meta.client

    def to_have_message(
        self,
        body: str,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> dict[str, Any]:
        """Wait for a message with the given body to be present in the queue.

        Non-destructive: messages are received with ``VisibilityTimeout=0``
        so they become re-visible immediately and the queue state is unchanged.

        Args:
            body: Exact string the message body must equal.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            The matching SQS message dict (includes ``Body``, ``MessageId``,
            ``ReceiptHandle``, and optional attribute keys).

        Raises:
            SQSWaitTimeoutError: If no matching message appears within *timeout*.
        """
        delay = self._compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            response = self._client.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=10,
                VisibilityTimeout=0,
                WaitTimeSeconds=0,
            )
            for message in response.get("Messages", []):
                if message["Body"] == body:
                    return message
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SQSWaitTimeoutError(self._queue_url, body, timeout)
            time.sleep(min(delay, remaining))

    def to_consume_message(
        self,
        body: str,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> dict[str, Any]:
        """Wait for a message with the given body and delete it from the queue.

        Destructive: the matching message is permanently deleted before returning.
        Non-matching messages received in the same batch are immediately restored
        via ``change_message_visibility(VisibilityTimeout=0)``.

        Args:
            body: Exact string the message body must equal.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            The consumed SQS message dict (includes ``Body``, ``MessageId``,
            ``ReceiptHandle``, and optional attribute keys).

        Raises:
            SQSWaitTimeoutError: If no matching message appears within *timeout*.
        """
        delay = self._compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            response = self._client.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=10,
                VisibilityTimeout=10,
                WaitTimeSeconds=0,
            )
            messages = response.get("Messages", [])
            matched: dict[str, Any] | None = None
            for message in messages:
                if message["Body"] == body:
                    matched = message
                    break

            if matched is not None:
                for message in messages:
                    if message is not matched:
                        self._client.change_message_visibility(
                            QueueUrl=self._queue_url,
                            ReceiptHandle=message["ReceiptHandle"],
                            VisibilityTimeout=0,
                        )
                self._client.delete_message(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=matched["ReceiptHandle"],
                )
                return matched

            # No match — restore all received messages so they stay visible
            for message in messages:
                self._client.change_message_visibility(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                    VisibilityTimeout=0,
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SQSWaitTimeoutError(self._queue_url, body, timeout)
            time.sleep(min(delay, remaining))

    @staticmethod
    def _compute_delay(poll_interval: float) -> int:
        """Clamp poll_interval to a minimum of 1 and round up."""
        return max(1, math.ceil(poll_interval))
