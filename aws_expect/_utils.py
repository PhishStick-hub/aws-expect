from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mypy_boto3_s3.type_defs import WaiterConfigTypeDef


def _compute_delay(poll_interval: float) -> int:
    """Clamp poll_interval to a minimum of 1 second and round up."""
    return max(1, math.ceil(poll_interval))


def _matches_entries(item: dict[str, Any], entries: dict[str, Any]) -> bool:
    """Shallow subset match: check *item* contains all key-value pairs in *entries*."""
    return all(item.get(k) == v for k, v in entries.items())


def _build_waiter_config(timeout: float, poll_interval: float) -> WaiterConfigTypeDef:
    """Convert timeout/poll_interval into a botocore WaiterConfig dict.

    Botocore expects ``Delay`` as an integer (seconds), so we clamp
    to a minimum of 1 and round up.
    """
    delay = _compute_delay(poll_interval)
    max_attempts = max(1, math.ceil(timeout / delay))
    return {"Delay": delay, "MaxAttempts": max_attempts}
