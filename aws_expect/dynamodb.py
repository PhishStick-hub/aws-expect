from __future__ import annotations

import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable, Iterator

from aws_expect._utils import (
    _check_stop_condition,
    _compute_delay,
    _deep_matches,
    _matches_entries,
)
from aws_expect.exceptions import (
    DynamoDBFindItemTimeoutError,
    DynamoDBNonNumericFieldError,
    DynamoDBUnexpectedItemError,
    DynamoDBWaitTimeoutError,
    StopConditionError,  # noqa: F401 — documented in to_exist/to_find_item Raises
    StopConditionMetError,  # noqa: F401 — documented in to_exist/to_find_item Raises
)

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
    from mypy_boto3_dynamodb.type_defs import TableDescriptionTypeDef


class DynamoDBItemExpectation:
    """Expectation wrapper for a DynamoDB Table resource item.

    Uses a custom polling loop over ``get_item`` because DynamoDB does not
    provide built-in waiters for individual items.
    """

    def __init__(self, table: Table) -> None:
        self._table = table
        self._table_name: str = table.name

    def _make_resource_id(self, key: dict[str, Any] | None = None) -> str:
        """Build a resource ID string for StopConditionMetError.

        Per D-12: when *key* is provided, format is
        ``dynamodb://{table}?pk=val1&sk=val2`` with keys in sorted order.
        Per D-13: when *key* is None, format is ``dynamodb://{table}``
        (used by to_find_item which scans all items).
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

        Args:
            key: Primary key dict, e.g. ``{"pk": "val"}`` or
                ``{"pk": "val", "sk": "val"}``.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).
            entries: Optional dict of expected key-value pairs.  When
                provided the item must contain **at least** these entries
                (subset match) before the wait succeeds.
            stop_when: Optional callable that receives a shallow-copied dict of
                the current DynamoDB item state and can return ``True`` or a
                string reason to abort polling early via
                :class:`StopConditionMetError`.  Only evaluated when *item
                exists* and *entries* don't match — main-condition-wins
                ordering.  Keyword-only.  Raises :class:`TypeError` if provided
                without *entries*.

        Returns:
            The full item dict from DynamoDB.

        Raises:
            DynamoDBWaitTimeoutError: If the item does not exist or does
                not match *entries* within *timeout*.
            StopConditionMetError: If *stop_when* returns a truthy value.
            StopConditionError: If *stop_when* raises an exception.
            TypeError: If *stop_when* is provided without *entries*.
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
        """Poll ``get_item`` until the item exists and a numeric field is within *delta* of *expected*.

        The condition is satisfied when ``abs(item[field] - expected) <= delta``.

        If the field exists but its value is not a number (``int``, ``float``,
        or ``Decimal`` as returned by the boto3 DynamoDB resource layer),
        a :class:`DynamoDBWaitTimeoutError` is raised immediately rather than
        waiting for the timeout.  A missing item or absent field is treated as
        the condition not yet being met, and polling continues.

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
            DynamoDBWaitTimeoutError: Immediately if *field* contains a
                non-numeric value; after *timeout* if the item does not exist,
                *field* is absent, or the value does not converge within *delta*.
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
                    if not isinstance(value, (int, float, Decimal)):
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

    def to_be_empty(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> None:
        """Poll ``scan`` until the table contains no items.

        Uses ``scan(Limit=1)`` to efficiently check for the presence of
        any item without reading the entire table.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            None when the table is empty.

        Raises:
            DynamoDBWaitTimeoutError: If the table still contains items
                after *timeout*.
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

        Uses ``scan(Limit=1)`` to efficiently check for the presence of
        any item without reading the entire table.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            None when the table contains at least one item.

        Raises:
            DynamoDBWaitTimeoutError: If the table is still empty after
                *timeout*.
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

        Paginates through all pages on each poll iteration following
        ``LastEvaluatedKey``. Returns immediately when the first matching
        item is found, without fetching further pages. The ``actual`` field
        in the timeout error reflects the last *complete* (no-match) pass,
        not a partial pass that was interrupted by timeout.

        Args:
            entries: Subset dict to match against each scanned item using
                recursive deep matching. Partial dicts match items that
                contain at least those key-value pairs.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).
            stop_when: Optional callable evaluated per-item during the paginated
                scan. Receives a shallow-copied dict of the current scanned item
                and can return ``True`` or a string reason to abort the entire
                scan early via :class:`StopConditionMetError`. Only checked when
                the item doesn't deep-match *entries* — main-condition-wins
                ordering. Keyword-only.

        Returns:
            The first full item dict that deep-matches *entries*.

        Raises:
            DynamoDBFindItemTimeoutError: If no matching item is found
                within *timeout*. Error stores ``.expected``, ``.actual``
                (last complete scan result or None), ``.timeout``,
                ``.table_name``.
            StopConditionMetError: If *stop_when* returns a truthy value
                during the scan — entire scan aborts immediately.
            StopConditionError: If *stop_when* raises an exception.
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

        Waits *computed_delay* seconds (clamped to a minimum of 1 via
        ``_compute_delay``), then performs a single paginated scan across all
        pages.  Callers that pass ``delay=0`` will still wait at least 1 second
        because of the enforced minimum.

        If any item on any page deep-matches *entries*, raises
        ``DynamoDBUnexpectedItemError`` immediately without scanning further
        pages.

        Args:
            entries: Subset dict to match against each scanned item using
                recursive deep matching.
            delay: Seconds to wait before the check.  Values below 1 are
                clamped to a minimum of 1 second.

        Returns:
            None when no matching item is found.

        Raises:
            DynamoDBUnexpectedItemError: If any item deep-matches *entries*.
                Error stores ``.table_name``, ``.entries``, ``.found_item``,
                ``.delay`` (the actually waited seconds, after clamping).
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
        """Yield every item in the table, paginating automatically."""
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

        Args:
            key: Primary key dict.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            None when the item no longer exists.

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
    def _is_close(value: int | float | Decimal, expected: float, delta: float) -> bool:
        """Return True when ``abs(value - expected) <= delta``."""
        return abs(float(value) - expected) <= delta


class DynamoDBTableExpectation:
    """Expectation wrapper for a DynamoDB table existence check.

    Uses ``describe_table`` to poll for table existence and status.
    """

    def __init__(
        self, dynamodb_resource: DynamoDBServiceResource, table_name: str
    ) -> None:
        self._client = dynamodb_resource.meta.client
        self._table_name = table_name

    def to_exist(
        self,
        timeout: float = 30,
        poll_interval: float = 5,
    ) -> TableDescriptionTypeDef:
        """Poll ``describe_table`` until the table exists and is ACTIVE.

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            The table description dict from DynamoDB containing keys such
            as ``TableName``, ``TableStatus``, ``KeySchema``, etc.

        Raises:
            DynamoDBWaitTimeoutError: If the table does not exist or does
                not become ACTIVE within *timeout*.
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

        Args:
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls (minimum 1).

        Returns:
            None when the table no longer exists.

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
