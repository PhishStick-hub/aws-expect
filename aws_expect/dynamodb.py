from __future__ import annotations

import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from aws_expect._utils import _compute_delay, _matches_entries
from aws_expect.exceptions import DynamoDBNonNumericFieldError, DynamoDBWaitTimeoutError

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

    def to_exist(
        self,
        key: dict[str, Any],
        timeout: float = 30,
        poll_interval: float = 5,
        entries: dict[str, Any] | None = None,
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

        Returns:
            The full item dict from DynamoDB.

        Raises:
            DynamoDBWaitTimeoutError: If the item does not exist or does
                not match *entries* within *timeout*.
        """
        delay = _compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            response = self._table.get_item(Key=key)
            item = response.get("Item")
            if item is not None:
                if entries is None or _matches_entries(item, entries):
                    return item
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBWaitTimeoutError(
                    self._table_name, key, timeout, entries=entries
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

        while True:
            response = self._table.get_item(Key=key)
            if (item := response.get("Item")) is not None:
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
                    self._table_name, key, timeout, message=timeout_message
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
        self._resource = dynamodb_resource
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
