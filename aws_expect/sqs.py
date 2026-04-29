from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from aws_expect._utils import _compute_delay, _deep_matches
from aws_expect.exceptions import (
    SQSEventWaitTimeoutError,
    SQSUnexpectedEventError,
    SQSUnexpectedMessageError,
    SQSWaitTimeoutError,
)

if TYPE_CHECKING:
    from mypy_boto3_sqs.service_resource import Queue as SQSQueue
    from mypy_boto3_sqs.type_defs import MessageTypeDef


def _parse_actual_events(
    bodies: list[str] | None,
) -> list[dict[str, Any]] | None:
    if bodies is None:
        return None
    events = [
        parsed for body in bodies if isinstance(parsed := _try_parse_json(body), dict)
    ]
    return events or None


def _try_parse_json(body: str) -> Any:
    try:
        return json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None


class SQSQueueExpectation:
    """Expectation wrapper for a boto3 SQS Queue resource."""

    def __init__(self, queue: SQSQueue) -> None:
        self._queue_url: str = queue.url
        self._client = queue.meta.client

    def _receive_batches(
        self,
        error_hint: str,
        timeout: float,
        poll_interval: float,
        visibility_timeout: int,
    ) -> Iterator[list[MessageTypeDef]]:
        """Yield batches of messages from the queue until timeout.

        Handles the polling loop: delay computation, deadline tracking,
        receive_message call, sleep, and SQSWaitTimeoutError on expiry.

        Args:
            error_hint: String included in the timeout error (body or str(event)).
            timeout: Maximum seconds to poll.
            poll_interval: Seconds between polls (minimum 1).
            visibility_timeout: VisibilityTimeout passed to receive_message.

        Yields:
            List of message dicts from each receive_message call (may be empty).

        Raises:
            SQSWaitTimeoutError: When the deadline passes without the caller
                returning from the for loop.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout
        last_batch: list[MessageTypeDef] = []

        while True:
            response = self._client.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=10,
                VisibilityTimeout=visibility_timeout,
                WaitTimeSeconds=0,
            )
            last_batch = response.get("Messages", [])
            yield last_batch
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                actual_bodies = [m["Body"] for m in last_batch] if last_batch else None
                raise SQSWaitTimeoutError(
                    self._queue_url, error_hint, timeout, actual=actual_bodies
                )
            time.sleep(min(delay, remaining))

    def to_have_message(
        self,
        body: str,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> MessageTypeDef:
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

        Note:
            At most 10 messages are inspected per poll (SQS API limit).
            On queues with many messages the target may require multiple
            polls to be returned by ``receive_message``.

        Raises:
            SQSWaitTimeoutError: If no matching message appears within *timeout*.
        """
        for messages in self._receive_batches(
            body, timeout, poll_interval, visibility_timeout=0
        ):
            for message in messages:
                if message["Body"] == body:
                    return message
        raise AssertionError("unreachable")  # pragma: no cover

    def to_consume_message(
        self,
        body: str,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> MessageTypeDef:
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

        Note:
            At most 10 messages are inspected per poll (SQS API limit).
            On queues with many messages the target may require multiple
            polls to be returned by ``receive_message``.

        Raises:
            SQSWaitTimeoutError: If no matching message appears within *timeout*.
        """
        for messages in self._receive_batches(
            body, timeout, poll_interval, visibility_timeout=10
        ):
            matched: MessageTypeDef | None = None
            for message in messages:
                if message["Body"] == body:
                    matched = message
                    break

            if matched is not None:
                self._restore_messages(messages, exclude=matched)
                self._client.delete_message(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=matched["ReceiptHandle"],
                )
                return matched

            # No match — restore all received messages so they stay visible
            self._restore_messages(messages)
        raise AssertionError("unreachable")  # pragma: no cover

    def to_not_have_message(
        self,
        body: str,
        delay: float,
    ) -> None:
        """Assert that a message with the given body is absent after a fixed delay.

        Sleeps for *delay* seconds (clamped to a minimum of 1 via
        :meth:`_compute_delay`), then performs a single non-destructive
        receive_message check.

        Args:
            body: Exact string the message body must NOT equal.
            delay: Seconds to sleep before performing the check.

        Returns:
            ``None`` when no message with *body* is found.

        Note:
            At most 10 messages are inspected (SQS API limit). On queues
            with many messages the target may not be returned by a single
            ``receive_message`` call even if it is present.

        Raises:
            SQSUnexpectedMessageError: If a message matching *body* is found.
        """
        time.sleep(_compute_delay(delay))
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=10,
            VisibilityTimeout=0,
            WaitTimeSeconds=0,
        )
        for message in response.get("Messages", []):
            if message["Body"] == body:
                raise SQSUnexpectedMessageError(self._queue_url, body, delay)

    def _restore_messages(
        self,
        messages: list[MessageTypeDef],
        exclude: MessageTypeDef | None = None,
    ) -> None:
        """Restore visibility=0 for all messages in *messages* except *exclude*.

        Args:
            messages: Batch of SQS message dicts to restore.
            exclude: Single message to skip (e.g. the one being deleted). If
                ``None`` every message in the batch is restored.
        """
        for message in messages:
            if message is not exclude:
                self._client.change_message_visibility(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                    VisibilityTimeout=0,
                )

    def _matches_event(self, message: MessageTypeDef, event: dict[str, Any]) -> bool:
        """Return True if the message body is valid JSON and deep-matches *event*.

        Args:
            message: SQS message dict with a ``Body`` key.
            event: Dict of expected key-value pairs for subset matching.

        Returns:
            True when the parsed body is a dict containing all key-value pairs
            in *event* (recursively). False on JSON parse errors or type mismatch.
        """
        try:
            body = json.loads(message["Body"])
        except (json.JSONDecodeError, ValueError):
            return False
        return isinstance(body, dict) and _deep_matches(body, event)

    def to_have_event(
        self,
        event: dict[str, Any],
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> MessageTypeDef:
        """Wait for a message whose JSON body deep-matches *event*.

        Non-destructive: messages are received with ``VisibilityTimeout=0``
        so they remain visible and the queue state is unchanged.

        Args:
            event: Dict of expected key-value pairs. Matched recursively
                against the parsed JSON body (subset match).
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            The matching SQS message dict (includes ``Body``, ``MessageId``,
            ``ReceiptHandle``).

        Raises:
            SQSEventWaitTimeoutError: If no matching message appears within *timeout*.
        """
        try:
            for messages in self._receive_batches(
                str(event), timeout, poll_interval, visibility_timeout=0
            ):
                for message in messages:
                    if self._matches_event(message, event):
                        return message
        except SQSWaitTimeoutError as exc:
            raise SQSEventWaitTimeoutError(
                self._queue_url, event, timeout, actual=_parse_actual_events(exc.actual)
            ) from exc
        raise AssertionError("unreachable")  # pragma: no cover

    def to_consume_event(
        self,
        event: dict[str, Any],
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> MessageTypeDef:
        """Wait for a message whose JSON body deep-matches *event* and delete it.

        Destructive: the matching message is permanently deleted before returning.
        Non-matching messages received in the same batch are immediately restored
        via ``change_message_visibility(VisibilityTimeout=0)``.

        Args:
            event: Dict of expected key-value pairs. Matched recursively
                against the parsed JSON body (subset match).
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            The consumed SQS message dict (includes ``Body``, ``MessageId``,
            ``ReceiptHandle``).

        Raises:
            SQSEventWaitTimeoutError: If no matching message appears within *timeout*.
        """
        try:
            for messages in self._receive_batches(
                str(event), timeout, poll_interval, visibility_timeout=10
            ):
                matched: MessageTypeDef | None = None
                for message in messages:
                    if self._matches_event(message, event):
                        matched = message
                        break

                if matched is not None:
                    self._restore_messages(messages, exclude=matched)
                    self._client.delete_message(
                        QueueUrl=self._queue_url,
                        ReceiptHandle=matched["ReceiptHandle"],
                    )
                    return matched

                # No match in this batch — restore all so they stay visible
                self._restore_messages(messages)
        except SQSWaitTimeoutError as exc:
            raise SQSEventWaitTimeoutError(
                self._queue_url, event, timeout, actual=_parse_actual_events(exc.actual)
            ) from exc
        raise AssertionError("unreachable")  # pragma: no cover

    def to_not_have_event(
        self,
        event: dict[str, Any],
        delay: float,
    ) -> None:
        """Assert no message matching *event* is present after a fixed delay.

        Sleeps for *delay* seconds (minimum 1 via :meth:`_compute_delay`), then
        performs a single non-destructive receive_message check.

        Args:
            event: Dict of expected key-value pairs to match against parsed JSON body.
            delay: Seconds to sleep before performing the check (minimum 1).

        Returns:
            ``None`` when no matching message is found.

        Note:
            At most 10 messages are inspected (SQS API limit). On queues with
            many messages, a matching event may not be returned in the single
            poll even if it is present.

        Raises:
            SQSUnexpectedEventError: If a matching message is found.
        """
        time.sleep(_compute_delay(delay))
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=10,
            VisibilityTimeout=0,
            WaitTimeSeconds=0,
        )
        for message in response.get("Messages", []):
            if self._matches_event(message, event):
                raise SQSUnexpectedEventError(self._queue_url, event, delay)
