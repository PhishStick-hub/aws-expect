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
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
    from mypy_boto3_dynamodb.type_defs import TableDescriptionTypeDef


class DynamoDBItemExpectation:
    """Expectation wrapper for items in a DynamoDB Table resource.

    Provides polling-based assertions for individual items (``get_item``)
    and full-table scans (``scan``).  DynamoDB has no built-in waiters for
    item-level operations, so every method implements its own poll loop
    with configurable *timeout* and *poll_interval*.

    Construct via :func:`aws_expect.expect.expect_dynamodb_item`.
    """

    def __init__(self, table: Table) -> None:
        self._table = table
        self._table_name = table.name

    def _make_resource_id(self, key: dict[str, Any] | None = None) -> str:
        """Build a resource ID string for :class:`StopConditionMetError`.

        With *key*: ``dynamodb://{table}?pk=val1&sk=val2`` (sorted).
        Without *key*: ``dynamodb://{table}`` (used by scan-based methods).
        """
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
        """Poll ``get_item`` until the item exists and optionally matches *entries*.

        Without *entries*, succeeds as soon as the item is present.  With
        *entries*, performs a **shallow** subset match (top-level keys only)
        and keeps polling until all expected key-value pairs are present.

        The *stop_when* callable is evaluated only when the item exists but
        *entries* do not match — this "main-condition-wins" ordering ensures
        the primary success path is never short-circuited.

        Args:
            key: Primary key dict, e.g. ``{"pk": "val"}`` or
                ``{"pk": "val", "sk": "val"}``.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).
            entries: Optional dict of expected key-value pairs for shallow
                subset match.
            stop_when: Callable receiving a shallow copy of the current item
                dict.  Return ``True`` or a string reason to abort early via
                :class:`StopConditionMetError`.  Keyword-only.  Requires
                *entries*.

        Returns:
            The full item dict from DynamoDB.

        Raises:
            DynamoDBWaitTimeoutError: If the item does not exist or does
                not match *entries* within *timeout*.
            StopConditionMetError: If *stop_when* returns a truthy value.
            StopConditionError: If *stop_when* raises an exception.
            TypeError: If *stop_when* is provided without *entries*.

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
            # D-02/D-11: stop_when only when item exists and entries don't match
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
        """Poll ``get_item`` until a numeric field is within *delta* of *expected*.

        The condition is satisfied when ``abs(item[field] - expected) <= delta``.

        If the field exists but its value is not numeric (``int`` or
        ``Decimal`` — the only numeric types the DynamoDB Table resource
        returns), :class:`DynamoDBNonNumericFieldError` is raised
        **immediately** without waiting for the timeout.  A missing item
        or absent field is treated as the condition not yet being met,
        and polling continues.

        Args:
            key: Primary key dict, e.g. ``{"pk": "val"}`` or
                ``{"pk": "val", "sk": "val"}``.
            field: Name of the numeric attribute to check.
            expected: The target numeric value.
            delta: Maximum allowed absolute difference from *expected*.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            The full item dict from DynamoDB.

        Raises:
            DynamoDBNonNumericFieldError: Immediately if *field* contains
                a non-numeric value (e.g. ``str``, ``bool``, ``list``).
            DynamoDBWaitTimeoutError: After *timeout* if the item does not
                exist, *field* is absent, or the value does not converge
                within *delta*.

        Note:
            DynamoDB stores all numbers as ``Decimal``.  The comparison
            converts to ``float`` internally, which may lose precision for
            values with more than ~15 significant digits.

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
        """Poll ``get_item`` until a timestamp field is within *delta* of *expected*.

        The condition is satisfied when
        ``abs(parse(item[field]) - expected) <= delta``.

        The field value is auto-detected:

        - **Numeric** (``int``, ``Decimal``) — interpreted as
          Unix epoch seconds.
        - **String** — parsed as ISO 8601.  Naive strings (no timezone
          offset) are treated as UTC.

        Both the parsed field value and *expected* are normalized to
        timezone-aware UTC datetimes before comparison.  If *expected*
        is ``None``, it defaults to ``datetime.now(timezone.utc)``
        evaluated on **each poll iteration** so the comparison always
        uses a fresh "now".

        If the field exists but its value cannot be parsed as a timestamp,
        :class:`DynamoDBInvalidTimestampError` is raised immediately.
        A missing item or absent field is treated as the condition not yet
        being met, and polling continues.

        Args:
            key: Primary key dict, e.g. ``{"pk": "val"}`` or
                ``{"pk": "val", "sk": "val"}``.
            field: Name of the timestamp attribute to check.
            delta: Maximum allowed absolute difference from *expected*,
                as a :class:`~datetime.timedelta`.
            expected: The target datetime.  Defaults to
                ``datetime.now(timezone.utc)`` on each poll.  Naive
                datetimes are treated as UTC.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            The full item dict from DynamoDB.

        Raises:
            DynamoDBInvalidTimestampError: Immediately if *field* contains
                a value that cannot be parsed as a timestamp (e.g. ``bool``,
                ``list``, or an unparseable string).
            DynamoDBWaitTimeoutError: After *timeout* if the item does not
                exist, *field* is absent, or the timestamp does not
                converge within *delta*.

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
        target: datetime | None = None
        if expected is not None:
            target = (
                expected.replace(tzinfo=timezone.utc)
                if expected.tzinfo is None
                else expected
            )

        while True:
            response = self._table.get_item(Key=key)
            if (item := response.get("Item")) is not None:
                last_item = item
                if (value := item.get(field)) is not None:
                    parsed = self._parse_timestamp(value)
                    if parsed is None:
                        raise DynamoDBInvalidTimestampError(
                            self._table_name, key, field, value, timeout
                        )
                    effective_target = (
                        target if target is not None else datetime.now(timezone.utc)
                    )
                    if self._is_datetime_close(parsed, effective_target, delta_seconds):
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

    def to_be_empty(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> None:
        """Poll ``scan`` until the table contains no items.

        Uses ``scan(Select="COUNT", Limit=1)`` to efficiently check for
        the presence of any item without reading the entire table.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            ``None`` when the table is empty.

        Raises:
            DynamoDBWaitTimeoutError: If the table still contains items
                after *timeout*.

        Note:
            DynamoDB ``scan`` is eventually consistent.  Recently deleted
            items may still appear in results for a short period.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            response = self._table.scan(
                Select="COUNT",
                Limit=1,
            )
            if response.get("Count", 0) == 0:
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBWaitTimeoutError(
                    self._table_name,
                    key=None,
                    timeout=timeout,
                    message=(
                        f"Timed out after {timeout}s waiting for table "
                        f"{self._table_name} to be empty"
                    ),
                )
            time.sleep(min(delay, remaining))

    def to_be_not_empty(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> None:
        """Poll ``scan`` until the table contains at least one item.

        Uses ``scan(Select="COUNT", Limit=1)`` to efficiently check for
        the presence of any item without reading the entire table.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            ``None`` when the table contains at least one item.

        Raises:
            DynamoDBWaitTimeoutError: If the table is still empty after
                *timeout*.

        Note:
            DynamoDB ``scan`` is eventually consistent.  Recently written
            items may not appear in results for a short period.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            response = self._table.scan(
                Select="COUNT",
                Limit=1,
            )
            if response.get("Count", 0) > 0:
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBWaitTimeoutError(
                    self._table_name,
                    key=None,
                    timeout=timeout,
                    message=(
                        f"Timed out after {timeout}s waiting for table "
                        f"{self._table_name} to not be empty"
                    ),
                )
            time.sleep(min(delay, remaining))

    def to_find_item(
        self,
        entries: dict[str, Any],
        timeout: float = 30,
        poll_interval: float = 5,
        *,
        stop_when: Callable[[dict[str, Any]], bool | str] | None = None,
    ) -> dict[str, Any]:
        """Scan the table until at least one item deep-matches *entries*.

        Each poll iteration performs a **full paginated scan** (following
        ``LastEvaluatedKey`` across all pages).  Returns immediately when
        the first matching item is found, without fetching further pages.

        The ``.actual`` field on the timeout error reflects the last
        *complete* (no-match) scan pass — not a partial pass interrupted
        by the deadline.

        The *stop_when* callable is evaluated per-item during the scan.
        It is only checked when the item does **not** deep-match *entries*
        (main-condition-wins ordering).  When *stop_when* fires, the
        entire scan aborts immediately.

        Args:
            entries: Subset dict to match against each scanned item using
                recursive deep matching.  Nested dicts are compared
                recursively; lists and scalars use exact equality.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).
            stop_when: Callable receiving a shallow copy of each scanned
                item dict.  Return ``True`` or a string reason to abort
                early via :class:`StopConditionMetError`.  Keyword-only.

        Returns:
            The first full item dict that deep-matches *entries*.

        Raises:
            DynamoDBFindItemTimeoutError: If no matching item is found
                within *timeout*.  Stores ``.expected``, ``.actual``
                (last complete scan result or ``None``), ``.timeout``,
                ``.table_name``.
            StopConditionMetError: If *stop_when* returns a truthy value.
            StopConditionError: If *stop_when* raises an exception.

        Note:
            DynamoDB ``scan`` is eventually consistent.  Recently written
            items may not appear in results for a short period.

        Example::

            item = expect_dynamodb_item(table).to_find_item(
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
                # D-03/D-09: per-item stop_when evaluation.
                # Main-condition-wins: deep_matches already returned above.
                # When stop_when fires, entire scan aborts immediately.
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
        """Assert no item in the table deep-matches *entries* after a delay.

        Sleeps for *delay* seconds (minimum 1), then performs a single
        paginated scan.  Raises :class:`DynamoDBUnexpectedItemError`
        immediately if any item on any page deep-matches *entries*,
        without scanning further pages.

        Args:
            entries: Subset dict to match against each scanned item using
                recursive deep matching.
            delay: Seconds to wait before the check (minimum 1).

        Returns:
            ``None`` when no matching item is found.

        Raises:
            DynamoDBUnexpectedItemError: If any item deep-matches *entries*.
                Stores ``.table_name``, ``.entries``, ``.found_item``,
                ``.delay`` (actual seconds waited, after clamping).

        Note:
            DynamoDB ``scan`` is eventually consistent.  Recently deleted
            items may still appear in results for a short period.
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
        """Yield every item in the table via paginated ``scan``.

        Follows ``LastEvaluatedKey`` across pages automatically.  The
        caller is responsible for any timeout enforcement between items.

        Yields:
            Individual item dicts from each scan page.
        """
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

    def to_not_exist(
        self,
        key: dict[str, Any],
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> None:
        """Poll ``get_item`` until the item no longer exists.

        Succeeds as soon as ``get_item`` returns no ``Item`` key.

        Args:
            key: Primary key dict, e.g. ``{"pk": "val"}`` or
                ``{"pk": "val", "sk": "val"}``.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            ``None`` when the item no longer exists.

        Raises:
            DynamoDBWaitTimeoutError: If the item still exists after *timeout*.
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
        """Return ``True`` when ``abs(value - expected) <= delta``.

        Converts *value* to ``float`` for comparison.  This may lose
        precision for ``Decimal`` values with more than ~15 significant
        digits.
        """
        return abs(float(value) - expected) <= delta

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        """Parse a DynamoDB field value into a timezone-aware UTC datetime.

        Accepted types:

        - ``int``, ``Decimal`` — interpreted as Unix epoch seconds.
        - ``str`` — parsed as ISO 8601.  Naive strings (no timezone
          offset) are treated as UTC.

        ``bool`` values are explicitly rejected (``bool`` is a subclass
        of ``int`` in Python, so the check must come first).

        Args:
            value: The raw DynamoDB attribute value.

        Returns:
            A timezone-aware :class:`~datetime.datetime` in UTC, or
            ``None`` if the value cannot be parsed.
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

    @staticmethod
    def _is_datetime_close(
        actual: datetime, expected: datetime, delta_seconds: float
    ) -> bool:
        """Return ``True`` when ``abs(actual - expected) <= delta_seconds``.

        Both *actual* and *expected* must be timezone-aware.
        """
        return abs((actual - expected).total_seconds()) <= delta_seconds


class DynamoDBTableExpectation:
    """Expectation wrapper for DynamoDB table-level existence checks.

    Uses the low-level ``describe_table`` client call (not the resource
    API) to poll for table creation and deletion.  The table must reach
    ``ACTIVE`` status for :meth:`to_exist` to succeed.

    Construct via :func:`aws_expect.expect.expect_dynamodb_table`.
    """

    def __init__(
        self, dynamodb_resource: DynamoDBServiceResource, table_name: str
    ) -> None:
        self._client: DynamoDBClient = dynamodb_resource.meta.client
        self._table_name = table_name

    def to_exist(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> TableDescriptionTypeDef:
        """Poll ``describe_table`` until the table exists and is ``ACTIVE``.

        Catches ``ResourceNotFoundException`` on each poll and retries
        until the table appears and reaches ``ACTIVE`` status.  Tables
        in ``CREATING``, ``UPDATING``, or ``DELETING`` states are treated
        as not yet ready.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            The ``Table`` description dict from ``describe_table``
            (typed as :class:`TableDescriptionTypeDef`).  Contains keys
            such as ``TableName``, ``TableStatus``, ``KeySchema``,
            ``AttributeDefinitions``, ``TableArn``, etc.

        Raises:
            DynamoDBWaitTimeoutError: If the table does not exist or does
                not become ``ACTIVE`` within *timeout*.
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
        """Poll ``describe_table`` until the table no longer exists.

        Succeeds when ``describe_table`` raises
        ``ResourceNotFoundException``.  Tables in ``DELETING`` state are
        treated as still existing.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            ``None`` when the table no longer exists.

        Raises:
            DynamoDBWaitTimeoutError: If the table still exists after
                *timeout*.
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
        """Poll until the table exists, is ``ACTIVE``, and contains no items.

        Each poll iteration first checks that the table exists and is
        ``ACTIVE`` via ``describe_table``.  Only then does it perform a
        lightweight ``scan(Select="COUNT", Limit=1)`` to check for items.
        Tables that do not yet exist or are still in ``CREATING`` state
        are treated as not yet ready.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            ``None`` when the table is empty.

        Raises:
            DynamoDBWaitTimeoutError: If the table does not exist, does
                not become ``ACTIVE``, or still contains items after
                *timeout*.

        Note:
            DynamoDB ``scan`` is eventually consistent.  Recently deleted
            items may still appear in results for a short period.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            try:
                response = self._client.describe_table(
                    TableName=self._table_name,
                )
                if response["Table"].get("TableStatus") == "ACTIVE":
                    scan_response = self._client.scan(
                        TableName=self._table_name,
                        Select="COUNT",
                        Limit=1,
                    )
                    if scan_response.get("Count", 0) == 0:
                        return None
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
                        f"{self._table_name} to be empty"
                    ),
                )
            time.sleep(min(delay, remaining))

    def to_be_not_empty(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> None:
        """Poll until the table exists, is ``ACTIVE``, and contains items.

        Each poll iteration first checks that the table exists and is
        ``ACTIVE`` via ``describe_table``.  Only then does it perform a
        lightweight ``scan(Select="COUNT", Limit=1)`` to check for items.
        Tables that do not yet exist or are still in ``CREATING`` state
        are treated as not yet ready.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            ``None`` when the table contains at least one item.

        Raises:
            DynamoDBWaitTimeoutError: If the table does not exist, does
                not become ``ACTIVE``, or remains empty after *timeout*.

        Note:
            DynamoDB ``scan`` is eventually consistent.  Recently written
            items may not appear in results for a short period.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            try:
                response = self._client.describe_table(
                    TableName=self._table_name,
                )
                if response["Table"].get("TableStatus") == "ACTIVE":
                    scan_response = self._client.scan(
                        TableName=self._table_name,
                        Select="COUNT",
                        Limit=1,
                    )
                    if scan_response.get("Count", 0) > 0:
                        return None
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
                        f"{self._table_name} to not be empty"
                    ),
                )
            time.sleep(min(delay, remaining))
