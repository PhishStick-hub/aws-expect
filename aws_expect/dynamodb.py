from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from aws_expect._utils import (
    _check_stop_condition,
    _compute_delay,
    _deep_matches,
    _matches_entries,
)
from aws_expect.exceptions import (
    DynamoDBFindItemTimeoutError,
    DynamoDBInvalidTimestampError,
    DynamoDBNonNumericFieldError,
    DynamoDBUnexpectedItemError,
    DynamoDBWaitTimeoutError,
)

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.client import DynamoDBClient
    from mypy_boto3_dynamodb.service_resource import Table
    from mypy_boto3_dynamodb.type_defs import TableDescriptionTypeDef


class DynamoDBItemExpectation:
    """Polling-based assertions for DynamoDB items (``get_item``).

    For table-level operations (scans, emptiness checks), use
    :class:`DynamoDBTableExpectation`.

    Construct via :func:`aws_expect.expect.expect_dynamodb_item`.
    """

    def __init__(self, table: Table) -> None:
        self._table = table
        self._table_name = table.name

    def _make_resource_id(self, key: dict[str, Any] | None = None) -> str:
        """Build resource ID: ``dynamodb://{table}`` or with sorted key params."""
        base = f"dynamodb://{self._table_name}"
        if key is None:
            return base
        params = "&".join(f"{k}={v}" for k, v in sorted(key.items()))
        return f"{base}?{params}"

    def to_exist(
        self,
        key: dict[str, Any],
        timeout: float = 30,
        poll_interval: float = 5,
        entries: dict[str, Any] | None = None,
        *,
        stop_when: Callable[[dict[str, Any]], bool | str] | None = None,
    ) -> dict[str, Any]:
        """Poll until item exists and optionally matches *entries* (shallow match).

        Args:
            key: Primary key dict (e.g. ``{"pk": "val"}``).
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).
            entries: Optional shallow subset match.
            stop_when: Keyword-only. Abort early if callable returns truthy.
                Requires *entries*.

        Returns:
            Full item dict.

        Raises:
            DynamoDBWaitTimeoutError: Item not found or doesn't match within timeout.
            StopConditionMetError: *stop_when* returned truthy.
            StopConditionError: *stop_when* raised exception.
            TypeError: *stop_when* provided without *entries*.

        Example::

            expect_dynamodb_item(table).to_exist(
                key={"pk": "user-1"},
                entries={"status": "active"},
                timeout=10,
            )
        """
        if stop_when is not None and entries is None:
            raise TypeError(
                "stop_when requires entries to be provided. "
                "Use to_exist(entries={...}, stop_when=...)"
            )

        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout
        start = time.monotonic()
        last_item: dict[str, Any] | None = None

        while True:
            response = self._table.get_item(Key=key)
            item = response.get("Item")
            last_item = item
            if item is not None:
                if entries is None or _matches_entries(item, entries):
                    return item
            if item is not None and stop_when is not None:
                resource_id = self._make_resource_id(key)
                _check_stop_condition(item, stop_when, resource_id, start, timeout)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBWaitTimeoutError(
                    self._table_name, key, timeout, expected=entries, actual=last_item
                )
            time.sleep(min(delay, remaining))

    def to_have_numeric_value_close_to(
        self,
        key: dict[str, Any],
        field: str,
        expected: float,
        delta: float,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> dict[str, Any]:
        """Poll until numeric field is within *delta* of *expected*.

        Raises :class:`DynamoDBNonNumericFieldError` immediately if field is not numeric.

        Args:
            key: Primary key dict.
            field: Numeric attribute name.
            expected: Target value.
            delta: Maximum absolute difference.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            Full item dict.

        Raises:
            DynamoDBNonNumericFieldError: Field is not numeric.
            DynamoDBWaitTimeoutError: Item/field not found or value doesn't converge.

        Example::

            expect_dynamodb_item(table).to_have_numeric_value_close_to(
                key={"pk": "counter-1"},
                field="count",
                expected=100,
                delta=5,
                timeout=10,
            )
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout
        timeout_message = (
            f"Timed out after {timeout}s waiting for item {key} field '{field}'"
            f" to be within {delta} of {expected} in table {self._table_name}"
        )
        last_item: dict[str, Any] | None = None

        while True:
            response = self._table.get_item(Key=key)
            if (item := response.get("Item")) is not None:
                last_item = item
                if (value := item.get(field)) is not None:
                    if not isinstance(value, (int, Decimal)):
                        raise DynamoDBNonNumericFieldError(
                            self._table_name, key, field, value, timeout
                        )
                    if self._is_close(value, expected, delta):
                        return item
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBWaitTimeoutError(
                    self._table_name,
                    key,
                    timeout,
                    message=timeout_message,
                    actual=last_item,
                )
            time.sleep(min(delay, remaining))

    def to_have_datetime_close_to(
        self,
        key: dict[str, Any],
        field: str,
        delta: timedelta,
        expected: datetime | None = None,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> dict[str, Any]:
        """Poll until timestamp field is within *delta* of *expected*.

        Auto-detects field type: numeric (epoch seconds) or ISO 8601 string.
        If *expected* is ``None``, defaults to ``datetime.now(timezone.utc)`` on each poll.

        Raises :class:`DynamoDBInvalidTimestampError` immediately if field cannot be parsed.

        Args:
            key: Primary key dict.
            field: Timestamp attribute name.
            delta: Maximum time difference.
            expected: Target datetime (defaults to now). Naive datetimes treated as UTC.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            Full item dict.

        Raises:
            DynamoDBInvalidTimestampError: Field cannot be parsed as timestamp.
            DynamoDBWaitTimeoutError: Item/field not found or timestamp doesn't converge.

        Example::

            from datetime import timedelta, timezone, datetime

            expect_dynamodb_item(table).to_have_datetime_close_to(
                key={"pk": "event-1"},
                field="created_at",
                delta=timedelta(seconds=30),
                expected=datetime(2025, 1, 1, tzinfo=timezone.utc),
                timeout=10,
            )
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout
        delta_seconds = delta.total_seconds()
        timeout_message = (
            f"Timed out after {timeout}s waiting for item {key} field '{field}'"
            f" to be within {delta} of {expected or 'now(UTC)'}"
            f" in table {self._table_name}"
        )
        last_item: dict[str, Any] | None = None
        target = self._normalize_to_utc(expected) if expected else None

        while True:
            item = self._table.get_item(Key=key).get("Item")
            if item is not None:
                last_item = item
                if self._check_datetime_field(
                    item, field, key, target, delta_seconds, timeout
                ):
                    return item

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBWaitTimeoutError(
                    self._table_name,
                    key,
                    timeout,
                    message=timeout_message,
                    actual=last_item,
                )
            time.sleep(min(delay, remaining))

    def to_not_exist(
        self,
        key: dict[str, Any],
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> None:
        """Poll until item no longer exists.

        Args:
            key: Primary key dict.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            ``None`` when item is deleted.

        Raises:
            DynamoDBWaitTimeoutError: Item still exists after timeout.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            response = self._table.get_item(Key=key)
            item = response.get("Item")
            if item is None:
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBWaitTimeoutError(self._table_name, key, timeout)
            time.sleep(min(delay, remaining))

    @staticmethod
    def _is_close(value: int | Decimal, expected: float, delta: float) -> bool:
        """Return ``True`` when ``abs(value - expected) <= delta``."""
        return abs(float(value) - expected) <= delta

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        """Parse DynamoDB field to UTC datetime.

        Accepts: numeric (epoch seconds), ISO 8601 strings.
        Rejects: ``bool``, unparseable values.
        """
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, Decimal)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
            except ValueError:
                return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        return None

    def _check_datetime_field(
        self,
        item: dict[str, Any],
        field: str,
        key: dict[str, Any],
        target: datetime | None,
        delta_seconds: float,
        timeout: float,
    ) -> bool:
        value = item.get(field)
        if value is None:
            return False
        parsed = self._parse_timestamp(value)
        if parsed is None:
            raise DynamoDBInvalidTimestampError(
                self._table_name, key, field, value, timeout
            )
        effective_target = target or datetime.now(timezone.utc)
        return self._is_datetime_close(parsed, effective_target, delta_seconds)

    @staticmethod
    def _normalize_to_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def _is_datetime_close(
        actual: datetime, expected: datetime, delta_seconds: float
    ) -> bool:
        """Return ``True`` when ``abs(actual - expected) <= delta_seconds``."""
        return abs((actual - expected).total_seconds()) <= delta_seconds


class DynamoDBTableExpectation:
    """Polling-based assertions for DynamoDB tables (``describe_table`` + ``scan``).

    Construct via :func:`aws_expect.expect.expect_dynamodb_table`.
    """

    def __init__(self, table: Table) -> None:
        self._table = table
        self._table_name = table.name
        self._client: DynamoDBClient = table.meta.client

    def _make_resource_id(self, key: dict[str, Any] | None = None) -> str:
        """Build resource ID: ``dynamodb://{table}`` or with sorted key params."""
        base = f"dynamodb://{self._table_name}"
        if key is None:
            return base
        params = "&".join(f"{k}={v}" for k, v in sorted(key.items()))
        return f"{base}?{params}"

    def to_exist(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> TableDescriptionTypeDef:
        """Poll until table exists and is ``ACTIVE``.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            Table description dict from ``describe_table``.

        Raises:
            DynamoDBWaitTimeoutError: Table not active within timeout.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            try:
                response = self._client.describe_table(
                    TableName=self._table_name,
                )
                table_desc = response["Table"]
                if table_desc.get("TableStatus") == "ACTIVE":
                    return table_desc
            except self._client.exceptions.ResourceNotFoundException:
                pass

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBWaitTimeoutError(
                    self._table_name,
                    key=None,
                    timeout=timeout,
                    message=(
                        f"Timed out after {timeout}s waiting for table "
                        f"{self._table_name} to exist"
                    ),
                )
            time.sleep(min(delay, remaining))

    def to_not_exist(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> None:
        """Poll until table no longer exists.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            ``None`` when table is deleted.

        Raises:
            DynamoDBWaitTimeoutError: Table still exists after timeout.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            try:
                self._client.describe_table(TableName=self._table_name)
            except self._client.exceptions.ResourceNotFoundException:
                return None

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBWaitTimeoutError(
                    self._table_name,
                    key=None,
                    timeout=timeout,
                    message=(
                        f"Timed out after {timeout}s waiting for table "
                        f"{self._table_name} to not exist"
                    ),
                )
            time.sleep(min(delay, remaining))

    def to_be_empty(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> None:
        """Poll until table is ``ACTIVE`` and contains no items.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            ``None`` when table is empty.

        Raises:
            DynamoDBWaitTimeoutError: Table not active or still has items.

        Note:
            DynamoDB ``scan`` is eventually consistent.
        """
        self._wait_for_table_empty_state(
            expect_empty=True, timeout=timeout, poll_interval=poll_interval
        )

    def to_be_not_empty(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> None:
        """Poll until table is ``ACTIVE`` and contains at least one item.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            ``None`` when table has items.

        Raises:
            DynamoDBWaitTimeoutError: Table not active or still empty.

        Note:
            DynamoDB ``scan`` is eventually consistent.
        """
        self._wait_for_table_empty_state(
            expect_empty=False, timeout=timeout, poll_interval=poll_interval
        )

    def to_find_item(
        self,
        entries: dict[str, Any],
        timeout: float = 30,
        poll_interval: float = 5,
        *,
        stop_when: Callable[[dict[str, Any]], bool | str] | None = None,
    ) -> dict[str, Any]:
        """Scan table until an item deep-matches *entries*.

        Performs full paginated scans each poll. Returns first match immediately.

        Args:
            entries: Subset dict for recursive deep matching.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).
            stop_when: Keyword-only. Abort early if callable returns truthy.

        Returns:
            First matching item dict.

        Raises:
            DynamoDBFindItemTimeoutError: No match found within timeout.
            StopConditionMetError: *stop_when* returned truthy.
            StopConditionError: *stop_when* raised exception.

        Note:
            DynamoDB ``scan`` is eventually consistent.

        Example::

            item = expect_dynamodb_table(table).to_find_item(
                entries={"type": "order", "status": "shipped"},
                timeout=15,
            )
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout
        start = time.monotonic()
        last_scan: list[dict[str, Any]] | None = None

        while True:
            current_scan: list[dict[str, Any]] = []
            for item in self._scan_pages():
                if time.monotonic() >= deadline:
                    raise DynamoDBFindItemTimeoutError(
                        self._table_name, entries, last_scan, timeout
                    )
                if _deep_matches(item, entries):
                    return item
                if stop_when is not None:
                    resource_id = self._make_resource_id(key=None)
                    _check_stop_condition(item, stop_when, resource_id, start, timeout)
                current_scan.append(item)

            last_scan = current_scan
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBFindItemTimeoutError(
                    self._table_name, entries, last_scan, timeout
                )
            time.sleep(min(delay, remaining))

    def to_not_find_item(
        self,
        entries: dict[str, Any],
        delay: float = 1,
    ) -> None:
        """Assert no item deep-matches *entries* after a delay.

        Args:
            entries: Subset dict for recursive deep matching.
            delay: Seconds to wait before check (minimum 1).

        Returns:
            ``None`` when no match found.

        Raises:
            DynamoDBUnexpectedItemError: Match found after delay.

        Note:
            DynamoDB ``scan`` is eventually consistent.
        """
        computed_delay = _compute_delay(delay)
        time.sleep(computed_delay)

        for item in self._scan_pages():
            if _deep_matches(item, entries):
                raise DynamoDBUnexpectedItemError(
                    self._table_name, entries, item, computed_delay
                )

        return None

    def _scan_pages(self) -> Iterator[dict[str, Any]]:
        """Yield all items via paginated ``scan``."""
        exclusive_start_key: dict[str, Any] | None = None
        while True:
            kwargs: dict[str, Any] = {}
            if exclusive_start_key is not None:
                kwargs["ExclusiveStartKey"] = exclusive_start_key
            response = self._table.scan(**kwargs)
            for item in response.get("Items", []):
                yield item
            exclusive_start_key = response.get("LastEvaluatedKey")
            if exclusive_start_key is None:
                break

    def _wait_for_table_empty_state(
        self,
        *,
        expect_empty: bool,
        timeout: float,
        poll_interval: float,
    ) -> None:
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            try:
                response = self._client.describe_table(
                    TableName=self._table_name,
                )
                if response["Table"].get("TableStatus") == "ACTIVE":
                    scan_response = self._table.scan(
                        Select="COUNT",
                        Limit=1,
                    )
                    is_empty = scan_response.get("Count", 0) == 0
                    if is_empty == expect_empty:
                        return None
            except self._client.exceptions.ResourceNotFoundException:
                pass

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                label = "empty" if expect_empty else "not empty"
                raise DynamoDBWaitTimeoutError(
                    self._table_name,
                    key=None,
                    timeout=timeout,
                    message=(
                        f"Timed out after {timeout}s waiting for table "
                        f"{self._table_name} to be {label}"
                    ),
                )
            time.sleep(min(delay, remaining))
