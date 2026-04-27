from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, overload

from botocore.exceptions import ClientError, WaiterError

from aws_expect._utils import (
    _build_waiter_config,
    _compute_delay,
    _deep_matches,
    _matches_entries,
)
from aws_expect.exceptions import (
    S3ContentWaitTimeoutError,
    S3UnexpectedContentError,
    S3WaitTimeoutError,
)

if TYPE_CHECKING:
    from mypy_boto3_s3.service_resource import Object as S3Object
    from mypy_boto3_s3.type_defs import HeadObjectOutputTypeDef


class S3ObjectExpectation:
    """Expectation wrapper for an S3 resource Object, using native boto3 waiters."""

    def __init__(self, s3_object: S3Object) -> None:
        self._obj = s3_object
        self._bucket = s3_object.bucket_name
        self._key = s3_object.key
        self._client = s3_object.meta.client

    @overload
    def to_exist(
        self,
        timeout: float = ...,
        poll_interval: float = ...,
        entries: dict[str, Any] = ...,
    ) -> dict[str, Any]: ...

    @overload
    def to_exist(
        self,
        timeout: float = ...,
        poll_interval: float = ...,
        entries: None = ...,
    ) -> HeadObjectOutputTypeDef: ...

    def to_exist(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
        entries: dict[str, Any] | None = None,
    ) -> HeadObjectOutputTypeDef | dict[str, Any]:
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

        waiter_config = _build_waiter_config(timeout, poll_interval)
        try:
            self._client.get_waiter("object_exists").wait(
                Bucket=self._bucket,
                Key=self._key,
                WaiterConfig=waiter_config,
            )
        except WaiterError as exc:
            raise S3WaitTimeoutError(self._bucket, self._key, timeout) from exc
        return self._client.head_object(Bucket=self._bucket, Key=self._key)

    def _fetch_body(self) -> dict[str, Any] | None:
        """Fetch and parse the S3 object body as JSON.

        Returns the parsed dict on success, or ``None`` when the object
        does not yet exist (NoSuchKey/404) or the body is not valid JSON.
        Re-raises any other ``ClientError``.
        """
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=self._key)
            body = json.loads(response["Body"].read())
            return body if isinstance(body, dict) else None
        except ClientError as err:
            if err.response["Error"]["Code"] not in ("NoSuchKey", "404"):
                raise
            return None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _poll_for_entries(
        self,
        timeout: float,
        poll_interval: float,
        entries: dict[str, Any],
    ) -> dict[str, Any]:
        """Poll ``get_object``, parse JSON, and wait for a subset match."""
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            body = self._fetch_body()
            if body is not None and _matches_entries(body, entries):
                return body

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise S3WaitTimeoutError(self._bucket, self._key, timeout)
            time.sleep(min(delay, remaining))

    def to_have_content(
        self,
        entries: dict[str, Any],
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> dict[str, Any]:
        """Wait until the S3 object body is valid JSON that deep-matches *entries*.

        Args:
            entries: Dict whose key-value pairs must all be present (recursively)
                in the parsed JSON body.
            timeout: Maximum seconds to wait. Defaults to 30.
            poll_interval: Seconds between polls. Clamped to minimum 1 second.
                Defaults to 5.

        Returns:
            The full parsed JSON body dict when a match is found.

        Raises:
            S3ContentWaitTimeoutError: If no matching body is found before timeout.
                The error stores .expected and .actual for debugging.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout
        last_body: dict[str, Any] | None = None

        while True:
            body = self._fetch_body()
            if body is not None:
                last_body = body
                if _deep_matches(body, entries):
                    return body

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise S3ContentWaitTimeoutError(
                    self._bucket, self._key, entries, last_body, timeout
                )
            time.sleep(min(delay, remaining))

    def to_not_have_content(
        self,
        entries: dict[str, Any],
        delay: float = 0,
    ) -> None:
        """Assert the S3 object body does not deep-match *entries* after *delay* seconds.

        Waits *delay* seconds (minimum 1 second via _compute_delay), then reads
        the object body once. If the body is valid JSON and deep-matches *entries*,
        raises S3UnexpectedContentError. Otherwise returns None.

        Args:
            entries: Dict to check against the object body.
            delay: Seconds to wait before the check. Minimum 1 second. Defaults to 0.

        Returns:
            None if the object is missing, body is non-JSON, or body does not match.

        Raises:
            S3UnexpectedContentError: If the body IS valid JSON and DOES deep-match
                *entries*.
        """
        time.sleep(_compute_delay(delay))
        body = self._fetch_body()
        if body is not None and _deep_matches(body, entries):
            raise S3UnexpectedContentError(self._bucket, self._key, entries, delay)

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
        waiter_config = _build_waiter_config(timeout, poll_interval)
        try:
            self._client.get_waiter("object_not_exists").wait(
                Bucket=self._bucket,
                Key=self._key,
                WaiterConfig=waiter_config,
            )
        except WaiterError as exc:
            raise S3WaitTimeoutError(self._bucket, self._key, timeout) from exc
        return None
