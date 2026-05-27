from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Callable, overload

from botocore.exceptions import ClientError, WaiterError

from aws_expect._utils import (
    _build_waiter_config,
    _check_stop_condition,
    _compute_delay,
    _deep_matches,
    _matches_entries,
)
from aws_expect.exceptions import (
    S3ContentWaitTimeoutError,
    S3ObjectAppearedError,
    S3UnexpectedContentError,
    S3WaitTimeoutError,
)

_S3_NOT_FOUND_CODES: frozenset[str] = frozenset({"NoSuchKey", "404"})

if TYPE_CHECKING:
    from mypy_boto3_s3.service_resource import Object as S3Object
    from mypy_boto3_s3.type_defs import HeadObjectOutputTypeDef


class S3ObjectExpectation:
    """Expectation wrapper for an S3 resource Object, using native boto3 waiters."""

    def __init__(self, s3_object: S3Object) -> None:
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

    @overload
    def to_exist(
        self,
        timeout: float = ...,
        poll_interval: float = ...,
        entries: dict[str, Any] = ...,
        *,
        stop_when: Callable[[dict[str, Any]], bool | str] | None = ...,
    ) -> dict[str, Any]: ...

    def to_exist(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
        entries: dict[str, Any] | None = None,
        *,
        stop_when: Callable[[dict[str, Any]], bool | str] | None = None,
    ) -> HeadObjectOutputTypeDef | dict[str, Any]:
        """Wait for the S3 object to exist and optionally match *entries*.

        Without *entries*, uses the native ``object_exists`` waiter and returns
        ``head_object`` metadata. With *entries*, polls the object body and
        checks for a **shallow** subset match (top-level keys only — nested
        dicts must match exactly). For deep recursive matching use
        :meth:`to_have_content`.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).
            entries: Optional expected key-value pairs for shallow subset match.
            stop_when: Callable receiving the current body state; return ``True``
                or a string to abort early. Requires *entries*. Keyword-only.

        Returns:
            ``head_object`` metadata dict (no *entries*) or parsed JSON body.

        Raises:
            S3WaitTimeoutError: Object does not exist or match within *timeout*.
            StopConditionMetError: *stop_when* returns a truthy value.
            StopConditionError: *stop_when* raises an exception.
            TypeError: *stop_when* provided without *entries*.
        """
        if stop_when is not None and entries is None:
            raise TypeError(
                "stop_when requires entries to be provided. "
                "Use to_exist(entries={...}, stop_when=...)"
            )
        if entries is not None:
            return self._poll_for_entries(timeout, poll_interval, entries, stop_when)

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

    def _head_object(self) -> HeadObjectOutputTypeDef | None:
        """Return ``head_object`` metadata, or ``None`` when the object is absent."""
        try:
            return self._client.head_object(Bucket=self._bucket, Key=self._key)
        except ClientError as err:
            if err.response["Error"]["Code"] not in _S3_NOT_FOUND_CODES:
                raise
            return None

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
            if err.response["Error"]["Code"] not in _S3_NOT_FOUND_CODES:
                raise
            return None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _poll_for_entries(
        self,
        timeout: float,
        poll_interval: float,
        entries: dict[str, Any],
        stop_when: Callable[[dict[str, Any]], bool | str] | None = None,
    ) -> dict[str, Any]:
        """Poll ``get_object``, parse JSON, and wait for a subset match.

        Args:
            stop_when: Optional callable evaluated after entries mismatch.
                Receives a shallow-copied state dict. Returns ``True`` or a
                string reason to abort polling early via StopConditionMetError.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout
        start = time.monotonic()

        while True:
            body = self._fetch_body()
            if body is not None and _matches_entries(body, entries):
                return body

            if body is not None and stop_when is not None:
                resource_id = f"s3://{self._bucket}/{self._key}"
                _check_stop_condition(body, stop_when, resource_id, start, timeout)

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

        Reads the object body once after waiting. Returns None if the object is
        missing, body is non-JSON, or body does not match.

        Args:
            entries: Dict to check against the object body.
            delay: Seconds to wait before the check (minimum 1). Defaults to 0.

        Raises:
            S3UnexpectedContentError: If the body deep-matches *entries*.
        """
        time.sleep(_compute_delay(delay))
        body = self._fetch_body()
        if body is not None and _deep_matches(body, entries):
            raise S3UnexpectedContentError(self._bucket, self._key, entries, delay)

    def to_not_exist(self, timeout: float = 30, poll_interval: float = 5) -> None:
        """Wait for the S3 object to not exist using the native ``object_not_exists`` waiter.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

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

    def to_not_appear(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> None:
        """Assert the S3 object does not appear within *timeout* seconds.

        Polls every *poll_interval* seconds. Raises immediately if the object
        is found at any point.

        Args:
            timeout: Maximum seconds to guard against object creation.
            poll_interval: Seconds between polls (minimum 1).

        Raises:
            S3ObjectAppearedError: If the object is found during the wait.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            metadata = self._head_object()
            if metadata is not None:
                raise S3ObjectAppearedError(self._bucket, self._key, timeout, metadata)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(delay, remaining))
