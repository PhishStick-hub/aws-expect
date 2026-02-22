from __future__ import annotations


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
    ) -> None:
        self.table_name = table_name
        self.key = key
        self.timeout = timeout
        if message is not None:
            msg = message
        else:
            msg = f"Timed out after {timeout}s waiting for item {key} in table {table_name}"
        super().__init__(msg)


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
