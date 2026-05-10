from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Any, Callable

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


def _truncate_value(value: Any) -> str:
    """Format *value* with truncation for error messages.

    Never raises — always returns a string.

    Rules:
    - ``None`` → ``"None"``
    - ``list``/``tuple`` with ≤ 50 items → ``repr(value)``
    - ``list``/``tuple`` with > 50 items → ``repr(first_50)`` +
      ``"\\n... (N more items not shown)"``
    - All other types where ``len(repr(value))`` ≤ 500 → ``repr(value)``
    - All other types where ``len(repr(value))`` > 500 →
      ``repr(value)[:500]`` +
      ``"\\n... (value truncated, showing first 500 of NNNN chars)"``

    Args:
        value: Any value to format for display in an error message.

    Returns:
        A string representation, possibly truncated.
    """
    if value is None:
        return "None"

    if isinstance(value, (list, tuple)):
        if len(value) > 50:
            rendered = repr(
                list(value[:50]) if isinstance(value, tuple) else value[:50]
            )
            remaining = len(value) - 50
            return f"{rendered}\n... ({remaining} more items not shown)"
        return repr(value)

    rendered = repr(value)
    if len(rendered) <= 500:
        return rendered

    total_len = len(rendered)
    return (
        f"{rendered[:500]}\n"
        f"... (value truncated, showing first 500 of {total_len} chars)"
    )


def _format_timeout_error(
    resource_desc: str,
    expected: Any,
    actual: Any,
    timeout: float,
) -> str:
    """Produce a structured timeout error message with Expected:/Actual: sections.

    The function emits a single-line header followed by optional sections
    showing what was expected and what was actually observed.  Each value
    is formatted via :func:`_truncate_value`.

    Args:
        resource_desc: Human-readable description of the waited-on resource
            (e.g. ``"s3://bucket/key"``, ``"table my-table"``).
        expected: What the waiter expected to find, or ``None``.
        actual: What was actually observed, or ``None``.
        timeout: The timeout in seconds.

    Returns:
        A multi-line string suitable as the ``args`` for ``Exception()``.
    """
    lines: list[str] = [
        f"Timed out after {timeout}s waiting for {resource_desc}",
    ]

    if expected is None and actual is None:
        return lines[0]

    lines.append("")
    sections: list[str] = []

    if expected is not None:
        sections.append(f"Expected:\n  {_truncate_value(expected)}")

    if actual is not None:
        if sections:
            sections.append("")
        sections.append(f"Actual:\n  {_truncate_value(actual)}")

    lines.extend(sections)
    return "\n".join(lines)


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
    # Lazy import to break circular dependency with exceptions.py
    from aws_expect.exceptions import StopConditionError, StopConditionMetError  # noqa: PLC0415
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
