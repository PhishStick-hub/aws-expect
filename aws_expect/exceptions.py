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
