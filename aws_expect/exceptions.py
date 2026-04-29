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


class S3ContentWaitTimeoutError(S3WaitTimeoutError):
    """Raised when to_have_content times out without finding a matching body.

    Inherits S3WaitTimeoutError so callers catching S3WaitTimeoutError or
    WaitTimeoutError still catch it.

    Attributes:
        bucket: S3 bucket name.
        key: S3 object key.
        expected: The subset dict that was never matched.
        actual: The last parsed JSON body seen during polling, or None if the
            object was never readable as JSON.
        timeout: The timeout that was configured for the wait operation.
    """

    def __init__(
        self,
        bucket: str,
        key: str,
        expected: dict[str, Any],
        actual: dict[str, Any] | None,
        timeout: float,
    ) -> None:
        self.bucket = bucket
        self.key = key
        self.expected = expected
        self.actual = actual
        self.timeout = timeout
        WaitTimeoutError.__init__(
            self,
            f"Timed out after {timeout}s waiting for s3://{bucket}/{key}"
            f" to have content matching expected={expected!r}; last body: {actual!r}",
        )


class S3UnexpectedContentError(Exception):
    """Raised when to_not_have_content finds the object body matches entries.

    Does NOT inherit WaitTimeoutError — mirrors SQSUnexpectedEventError.

    Attributes:
        bucket: S3 bucket name.
        key: S3 object key.
        entries: The subset dict that was unexpectedly found.
        delay: The number of seconds waited before the check.
    """

    def __init__(
        self,
        bucket: str,
        key: str,
        entries: dict[str, Any],
        delay: float,
    ) -> None:
        self.bucket = bucket
        self.key = key
        self.entries = entries
        self.delay = delay
        super().__init__(
            f"Unexpected content matching {entries!r} found"
            f" in s3://{bucket}/{key} after {delay}s delay"
        )


class DynamoDBWaitTimeoutError(WaitTimeoutError):
    """Raised when a DynamoDB wait operation exceeds the specified timeout."""

    def __init__(
        self,
        table_name: str,
        key: dict[str, str] | None,
        timeout: float,
        message: str | None = None,
        entries: dict[str, Any] | None = None,
        actual: dict[str, Any] | None = None,
    ) -> None:
        self.table_name = table_name
        self.key = key
        self.timeout = timeout
        self.entries = entries
        self.actual = actual
        actual_str = repr(actual) if actual is not None else "None"
        if message is not None:
            msg = f"{message}\n\nActual (last seen):\n  {actual_str}"
        elif entries is not None:
            msg = (
                f"Timed out after {timeout}s waiting for item {key} in table {table_name}\n\n"
                f"Expected entries:\n"
                f"  {entries!r}\n\n"
                f"Actual (last seen):\n"
                f"  {actual_str}"
            )
        else:
            msg = f"Timed out after {timeout}s waiting for item {key} in table {table_name}"
        super().__init__(msg)


class DynamoDBFindItemTimeoutError(DynamoDBWaitTimeoutError):
    """Raised when to_find_item times out without finding a matching item.

    Inherits DynamoDBWaitTimeoutError so callers catching DynamoDBWaitTimeoutError
    or WaitTimeoutError still catch it.

    Attributes:
        table_name: Name of the DynamoDB table that was scanned.
        expected: The subset dict that was never matched.
        actual: All items seen in the last complete scan pass, or None if no
            pass completed before timeout (table always empty or first poll
            timed out mid-scan).
        timeout: The timeout that was configured for the wait operation.
    """

    def __init__(
        self,
        table_name: str,
        expected: dict[str, Any],
        actual: list[dict[str, Any]] | None,
        timeout: float,
    ) -> None:
        self.table_name = table_name
        self.expected = expected
        self.actual = actual
        self.timeout = timeout
        # Initialise parent-class attributes that DynamoDBWaitTimeoutError.__init__
        # would set, so that callers catching as DynamoDBWaitTimeoutError can
        # safely access .key and .entries without AttributeError.
        self.key = None
        self.entries = None
        item_count = len(actual) if actual is not None else 0
        WaitTimeoutError.__init__(
            self,
            f"Timed out after {timeout}s waiting for an item matching {expected!r}"
            f" in table {table_name};"
            f" last scan returned {item_count} item(s): {actual!r}",
        )


class DynamoDBUnexpectedItemError(Exception):
    """Raised when to_not_find_item finds a matching item in the table.

    Does NOT inherit WaitTimeoutError — mirrors S3UnexpectedContentError,
    SQSUnexpectedMessageError, and SQSUnexpectedEventError.

    Attributes:
        table_name: Name of the DynamoDB table that was scanned.
        entries: The subset dict that was unexpectedly found.
        found_item: The full item dict that matched entries.
        delay: The number of seconds waited before the check.
    """

    def __init__(
        self,
        table_name: str,
        entries: dict[str, Any],
        found_item: dict[str, Any],
        delay: float,
    ) -> None:
        self.table_name = table_name
        self.entries = entries
        self.found_item = found_item
        self.delay = delay
        super().__init__(
            f"Unexpected item matching {entries!r} found"
            f" in table {table_name} after {delay}s delay: {found_item!r}"
        )


class DynamoDBNonNumericFieldError(Exception):
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


class LambdaInvocableTimeoutError(LambdaWaitTimeoutError):
    """Raised when to_be_invocable times out without a matching response.

    Attributes:
        function_name: Name or ARN of the Lambda function.
        expected: The entries dict that was never matched.
        actual: The last parsed response payload dict, or None if no invocation
            produced a parseable response.
        timeout: The timeout that was configured.
    """

    def __init__(
        self,
        function_name: str,
        expected: dict[str, Any],
        actual: dict[str, Any] | None,
        timeout: float,
    ) -> None:
        self.function_name = function_name
        self.expected = expected
        self.actual = actual
        self.timeout = timeout
        actual_str = repr(actual) if actual is not None else "None"
        WaitTimeoutError.__init__(
            self,
            f"Timed out after {timeout}s waiting for Lambda function {function_name!r}"
            f" to be invocable\n\n"
            f"Expected entries:\n"
            f"  {expected!r}\n\n"
            f"Actual (last seen):\n"
            f"  {actual_str}",
        )


class LambdaResponseMismatchError(Exception):
    """Raised when a Lambda invocation response does not match expectations.

    Unlike :class:`LambdaWaitTimeoutError`, this is not a polling timeout —
    it signals that the single invocation returned an unexpected response.

    Attributes:
        function_name: Name or ARN of the Lambda function that was invoked.
        actual: The full parsed response payload that was returned, or None if
            the function raised an error before a payload could be parsed.
        expected_status: The status code the caller expected, or None if not checked.
        expected_body: The body subset the caller expected, or None if not checked.
    """

    def __init__(
        self,
        function_name: str,
        actual: dict[str, Any] | None,
        *,
        expected_status: int | None = None,
        expected_body: dict[str, Any] | None = None,
    ) -> None:
        self.function_name = function_name
        self.actual = actual
        self.expected_status = expected_status
        self.expected_body = expected_body
        parts: list[str] = []
        if expected_status is not None:
            parts.append(f"expected_status={expected_status!r}")
        if expected_body is not None:
            parts.append(f"expected_body={expected_body!r}")
        expected_desc = ", ".join(parts) if parts else "no expectations provided"
        super().__init__(
            f"Lambda function {function_name!r} response did not match expectations"
            f" ({expected_desc}); got actual={actual!r}"
        )


class SQSWaitTimeoutError(WaitTimeoutError):
    """Raised when an SQS wait operation exceeds the specified timeout."""

    def __init__(
        self,
        queue_url: str,
        body: str,
        timeout: float,
        actual: list[str] | None = None,
    ) -> None:
        self.queue_url = queue_url
        self.body = body
        self.timeout = timeout
        self.actual = actual
        actual_str = repr(actual) if actual is not None else "None"
        msg = (
            f"Timed out after {timeout}s waiting for message in queue {queue_url}\n\n"
            f"Expected body:\n"
            f"  {body!r}\n\n"
            f"Actual (last seen):\n"
            f"  {actual_str}"
        )
        super().__init__(msg)


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

    def __init__(
        self,
        queue_url: str,
        event: dict[str, Any],
        timeout: float,
        actual: list[dict[str, Any]] | None = None,
    ) -> None:
        self.queue_url = queue_url
        self.event = event
        self.timeout = timeout
        self.actual = actual
        actual_str = repr(actual) if actual is not None else "None"
        msg = (
            f"Timed out after {timeout}s waiting for event in queue {queue_url}\n\n"
            f"Expected event:\n"
            f"  {event!r}\n\n"
            f"Actual (last seen):\n"
            f"  {actual_str}"
        )
        super().__init__(msg)


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
