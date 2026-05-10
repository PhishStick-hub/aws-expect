from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Any, Callable

from aws_expect.exceptions import StopConditionError, StopConditionMetError

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


def _deep_matches(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Check whether *actual* contains all key-value pairs in *expected*.

    Recurses into nested dicts. Lists and all other types use exact equality.

    Args:
        actual: The parsed JSON dict to test against.
        expected: The subset dict to match against.

    Returns:
        True if every key in *expected* is present in *actual* and matches.
    """
    for key, value in expected.items():
        if key not in actual:
            return False
        if isinstance(value, dict):
            if not isinstance(actual[key], dict):
                return False
            if not _deep_matches(actual[key], value):
                return False
        elif actual[key] != value:
            return False
    return True


def _check_stop_condition(
    state: dict[str, Any],
    stop_when: Callable[[dict[str, Any]], bool | str] | None,
    resource_id: str,
    start: float,
    timeout: float,
) -> dict[str, Any] | None:
    """Evaluate *stop_when* predicate against a shallow-copied *state* dict.

    Returns:
        ``None`` when *stop_when* is ``None`` (no-op).
        ``None`` when predicate returns ``False`` (continue polling).

    Raises:
        StopConditionMetError: When predicate returns ``True`` or a string.
        StopConditionError: When predicate raises a non-StopConditionMetError.
    """
    if stop_when is None:
        return None

    state_copy = state.copy()
    try:
        result = stop_when(state_copy)
    except StopConditionMetError:
        raise
    except Exception as exc:
        raise StopConditionError(resource_id, exc) from exc

    if not result:
        return None

    if isinstance(result, str):
        stop_reason = result
    else:
        stop_reason = "stop condition met"

    elapsed = time.monotonic() - start
    raise StopConditionMetError(resource_id, stop_reason, elapsed, timeout)
