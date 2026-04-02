from __future__ import annotations

from typing import Any

NON_NUMERIC_FIELD_MSG = (
    "Field '{field}' has non-numeric value {value!r}"
    " (type {type}) for item {key} in table {table_name}"
)


class WaitTimeoutError(Exception):
    """Base class for all wait timeout errors.

    Subclassed per AWS service so callers can catch either the
    service-specific exception or this common base.
    """

    timeout: float


class S3WaitTimeoutError(WaitTimeoutError):
    """Raised when an S3 wait operation exceeds the specified timeout."""

    def __init__(self, bucket: str, key: str, timeout: float) -> None:
        self.bucket = bucket
        self.key = key
        self.timeout = timeout
        super().__init__(f"Timed out after {timeout}s waiting for s3://{bucket}/{key}")


class DynamoDBWaitTimeoutError(WaitTimeoutError):
    """Raised when a DynamoDB wait operation exceeds the specified timeout."""

    def __init__(
        self,
        table_name: str,
        key: dict[str, str] | None,
        timeout: float,
        message: str | None = None,
        entries: dict[str, Any] | None = None,
    ) -> None:
        self.table_name = table_name
        self.key = key
        self.timeout = timeout
        self.entries = entries
        if message is not None:
            msg = message
        elif entries is not None:
            msg = f"Timed out after {timeout}s waiting for item {key} with entries {entries} in table {table_name}"
        else:
            msg = f"Timed out after {timeout}s waiting for item {key} in table {table_name}"
        super().__init__(msg)


class DynamoDBNonNumericFieldError(WaitTimeoutError):
    """Raised immediately when a DynamoDB item field contains a non-numeric value.

    Unlike :class:`DynamoDBWaitTimeoutError`, this is not a polling timeout —
    it signals that the field value is of the wrong type and polling cannot
    succeed regardless of how long the wait continues.

    Attributes:
        table_name: Name of the DynamoDB table.
        key: Primary key dict used to look up the item.
        field: Name of the attribute that held the non-numeric value.
        value: The actual value found in the field.
        timeout: The timeout that was configured for the wait operation.
    """

    def __init__(
        self,
        table_name: str,
        key: dict[str, Any],
        field: str,
        value: Any,
        timeout: float,
    ) -> None:
        self.table_name = table_name
        self.key = key
        self.field = field
        self.value = value
        self.timeout = timeout
        super().__init__(
            NON_NUMERIC_FIELD_MSG.format(
                field=field,
                value=value,
                type=type(value).__name__,
                key=key,
                table_name=table_name,
            )
        )


class LambdaWaitTimeoutError(WaitTimeoutError):
    """Raised when a Lambda wait operation exceeds the specified timeout.

    Attributes:
        function_name: Name or ARN of the Lambda function that was waited on.
        timeout: The timeout that was configured for the wait operation.
    """

    def __init__(self, function_name: str, timeout: float) -> None:
        self.function_name = function_name
        self.timeout = timeout
        super().__init__(
            f"Timed out after {timeout}s waiting for Lambda function {function_name!r}"
        )


class SQSWaitTimeoutError(WaitTimeoutError):
    """Raised when an SQS wait operation exceeds the specified timeout."""

    def __init__(self, queue_url: str, body: str, timeout: float) -> None:
        self.queue_url = queue_url
        self.body = body
        self.timeout = timeout
        super().__init__(
            f"Timed out after {timeout}s waiting for message with body={body!r}"
            f" in queue {queue_url}"
        )


class SQSUnexpectedMessageError(Exception):
    """Raised when a message that should be absent is found in an SQS queue.

    Attributes:
        queue_url: The URL of the SQS queue that was checked.
        body: The message body that was unexpectedly found.
        delay: The number of seconds waited before the check.
    """

    def __init__(self, queue_url: str, body: str, delay: float) -> None:
        self.queue_url = queue_url
        self.body = body
        self.delay = delay
        super().__init__(
            f"Unexpected message with body={body!r} found in queue {queue_url}"
            f" after {delay}s delay"
        )


class SQSEventWaitTimeoutError(WaitTimeoutError):
    """Raised when to_have_event / to_consume_event exceeds timeout.

    Inherits WaitTimeoutError directly (not SQSWaitTimeoutError) because
    it stores event: dict[str, Any] rather than body: str. Callers that
    catch SQSWaitTimeoutError will NOT catch this exception; they must
    catch SQSEventWaitTimeoutError or the common base WaitTimeoutError.

    Attributes:
        queue_url: URL of the SQS queue that was polled.
        event: The event subset dict that was not found.
        timeout: The timeout that was configured for the wait.
    """

    def __init__(self, queue_url: str, event: dict[str, Any], timeout: float) -> None:
        self.queue_url = queue_url
        self.event = event
        self.timeout = timeout
        super().__init__(
            f"Timed out after {timeout}s waiting for event matching {event!r}"
            f" in queue {queue_url}"
        )


class SQSUnexpectedEventError(Exception):
    """Raised when to_not_have_event finds a matching event.

    Does NOT inherit WaitTimeoutError — mirrors SQSUnexpectedMessageError.

    Attributes:
        queue_url: URL of the SQS queue that was checked.
        event: The event subset dict that was unexpectedly found.
        delay: The number of seconds waited before the check.
    """

    def __init__(self, queue_url: str, event: dict[str, Any], delay: float) -> None:
        self.queue_url = queue_url
        self.event = event
        self.delay = delay
        super().__init__(
            f"Unexpected event matching {event!r} found in queue {queue_url}"
            f" after {delay}s delay"
        )


class AggregateWaitTimeoutError(WaitTimeoutError):
    """Raised when one or more parallel expectations fail.

    Contains individual errors and any successful results from the
    parallel execution.

    Attributes:
        errors: List of :class:`WaitTimeoutError` exceptions that occurred.
        results: Ordered list matching the input expectations. Each entry is
            the successful return value or ``None`` if that expectation failed.
        timeout: The maximum timeout among all individual errors.
    """

    def __init__(
        self,
        errors: list[WaitTimeoutError],
        results: list[object],
    ) -> None:
        self.errors = errors
        self.results = results
        self.timeout = max(e.timeout for e in errors) if errors else 0.0
        failed = len(errors)
        total = len(results)
        succeeded = total - failed
        summary = f"{failed} of {total} expectations timed out ({succeeded} succeeded)"
        details = "\n".join(f"  - {e}" for e in errors)
        super().__init__(f"{summary}\n{details}")
