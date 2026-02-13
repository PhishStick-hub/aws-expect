import math
import time
from typing import Any

from aws_expect.exceptions import DynamoDBWaitTimeoutError


class DynamoDBItemExpectation:
    """Expectation wrapper for a DynamoDB Table resource item.

    Uses a custom polling loop over ``get_item`` because DynamoDB does not
    provide built-in waiters for individual items.
    """

    def __init__(self, table: Any) -> None:
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
        delay = self._compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            response: dict[str, Any] = self._table.get_item(Key=key)
            item: dict[str, Any] | None = response.get("Item")
            if item is not None:
                if entries is None or self._matches_entries(item, entries):
                    return item
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBWaitTimeoutError(self._table_name, key, timeout)
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
        delay = self._compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            response: dict[str, Any] = self._table.scan(
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

    def to_not_be_empty(
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
        delay = self._compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            response: dict[str, Any] = self._table.scan(
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
        delay = self._compute_delay(poll_interval)
        deadline = time.monotonic() + timeout

        while True:
            response: dict[str, Any] = self._table.get_item(Key=key)
            item: dict[str, Any] | None = response.get("Item")
            if item is None:
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DynamoDBWaitTimeoutError(self._table_name, key, timeout)
            time.sleep(min(delay, remaining))

    @staticmethod
    def _compute_delay(poll_interval: float) -> int:
        """Clamp poll_interval to a minimum of 1 and round up."""
        return max(1, math.ceil(poll_interval))

    @staticmethod
    def _matches_entries(item: dict[str, Any], entries: dict[str, Any]) -> bool:
        """Check that *item* contains all expected *entries* (subset match)."""
        return all(item.get(k) == v for k, v in entries.items())
