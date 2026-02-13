import json
import math
import time
from typing import Any

from botocore.exceptions import ClientError, WaiterError

from aws_expect.exceptions import S3WaitTimeoutError


class S3ObjectExpectation:
    """Expectation wrapper for an S3 resource Object, using native boto3 waiters."""

    def __init__(self, s3_object: Any) -> None:
        self._obj = s3_object
        self._bucket = s3_object.bucket_name
        self._key = s3_object.key
        self._client = s3_object.meta.client

    def to_exist(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
        entries: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Wait for the S3 object to exist and optionally match *entries*.

        When *entries* is ``None`` the native ``object_exists`` waiter is used
        and the ``head_object`` response metadata dict is returned.

        When *entries* is provided the object body is retrieved on each poll,
        parsed as JSON, and checked for a **subset match** against *entries*.
        The parsed body dict is returned on success.

        Args:
            timeout: Maximum time in seconds to wait.
            poll_interval: Time in seconds between polling attempts (minimum 1).
            entries: Optional dict of expected key-value pairs.  When
                provided the item must contain **at least** these entries
                (subset match) before the wait succeeds.

        Returns:
            The ``head_object`` response metadata dict when *entries* is
            ``None``, or the parsed JSON body dict when *entries* is given.

        Raises:
            S3WaitTimeoutError: If the object does not exist (or does not
                match *entries*) within *timeout*.
        """
        if entries is not None:
            return self._poll_for_entries(timeout, poll_interval, entries)

        waiter_config = self._build_waiter_config(timeout, poll_interval)
        try:
            self._client.get_waiter("object_exists").wait(
                Bucket=self._bucket,
                Key=self._key,
                WaiterConfig=waiter_config,
            )
        except WaiterError as exc:
            raise S3WaitTimeoutError(self._bucket, self._key, timeout) from exc
        return self._client.head_object(Bucket=self._bucket, Key=self._key)

    def _poll_for_entries(
        self,
        timeout: float,
        poll_interval: float,
        entries: dict[str, Any],
    ) -> dict[str, Any]:
        """Poll ``get_object``, parse JSON, and wait for a subset match."""
        delay = max(1, math.ceil(poll_interval))
        deadline = time.monotonic() + timeout

        while True:
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=self._key)
                body = json.loads(response["Body"].read())
                if isinstance(body, dict) and self._matches_entries(body, entries):
                    return body
            except ClientError as err:
                # Object does not exist yet – keep polling.
                if err.response["Error"]["Code"] not in ("NoSuchKey", "404"):
                    raise
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Body isn't valid JSON – treat as non-match, keep polling.
                pass

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise S3WaitTimeoutError(self._bucket, self._key, timeout)
            time.sleep(min(delay, remaining))

    def to_not_exist(self, timeout: float = 30, poll_interval: float = 5) -> None:
        """Wait for the S3 object to not exist using the native ``object_not_exists`` waiter.

        Args:
            timeout: Maximum time in seconds to wait.
            poll_interval: Time in seconds between polling attempts (minimum 1).

        Returns:
            None when the object no longer exists.

        Raises:
            S3WaitTimeoutError: If the object still exists after *timeout*.
        """
        waiter_config = self._build_waiter_config(timeout, poll_interval)
        try:
            self._client.get_waiter("object_not_exists").wait(
                Bucket=self._bucket,
                Key=self._key,
                WaiterConfig=waiter_config,
            )
        except WaiterError as exc:
            raise S3WaitTimeoutError(self._bucket, self._key, timeout) from exc
        return None

    @staticmethod
    def _build_waiter_config(timeout: float, poll_interval: float) -> dict[str, int]:
        """Convert timeout/poll_interval into a botocore WaiterConfig dict.

        Botocore expects ``Delay`` as an integer (seconds), so we clamp
        to a minimum of 1 and round up.
        """
        delay = max(1, math.ceil(poll_interval))
        max_attempts = max(1, math.ceil(timeout / delay))
        return {"Delay": delay, "MaxAttempts": max_attempts}

    @staticmethod
    def _matches_entries(item: dict[str, Any], entries: dict[str, Any]) -> bool:
        """Check that *item* contains all expected *entries* (subset match)."""
        return all(item.get(k) == v for k, v in entries.items())
