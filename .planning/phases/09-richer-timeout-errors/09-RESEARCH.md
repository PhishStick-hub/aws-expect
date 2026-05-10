# Phase 9: Richer Timeout Errors — Research

**Researched:** 2026-05-10
**Confidence:** HIGH
**Mode:** implementation (purely mechanical refactoring — all design decisions locked in CONTEXT.md)

## Research Summary

This phase is a **mechanical refactoring** with zero external dependencies. All 13 design decisions are locked in CONTEXT.md. Research confirms: no circular import risks, all existing patterns are compatible, and the implementation is a straight-line refactoring across 6 files.

## Standard Stack

No external libraries required. The implementation uses only:

| Concern | Solution | File |
|---------|----------|------|
| String formatting | Python f-strings + `repr()` | `aws_expect/_utils.py` |
| Truncation logic | `len()` + slicing | `aws_expect/_utils.py` |
| Type annotations | `typing.Any` (existing pattern) | All files |
| Testing | `pytest` + existing test patterns | `tests/test_exceptions.py` |

## Architecture Patterns

### Pattern 1: Shared Helper in `_utils.py` (Confirmed)

All service modules (`s3.py`, `dynamodb.py`, `sqs.py`, `lambda_function.py`) already import from `aws_expect/_utils.py`:

```python
# Existing imports (verified in all 4 service modules)
from aws_expect._utils import _build_waiter_config, _compute_delay, _matches_entries
```

Adding `_format_timeout_error` and `_truncate_value` to this module follows the established pattern. No circular import risk — `_utils.py` imports from `aws_expect.exceptions` only for `StopConditionError`/`StopConditionMetError` (lines 7), and these are unrelated to timeout formatting.

### Pattern 2: Class-Level Default Attributes on Base Class (Confirmed)

`WaitTimeoutError` already uses class-level attribute assignment for `timeout`:

```python
class WaitTimeoutError(Exception):
    timeout: float  # type annotation only, set in subclass __init__
```

Adding `expected: Any = None` and `actual: Any = None` as class-level defaults follows the same pattern. Subclasses that don't set these fields (e.g., `S3WaitTimeoutError`, `LambdaWaitTimeoutError`) will inherit `None` automatically — no changes needed to their constructors.

### Pattern 3: Direct `WaitTimeoutError.__init__` Call (Confirmed)

Several subclasses bypass intermediate `__init__` to avoid signature mismatches:

```python
# S3ContentWaitTimeoutError.__init__ (exceptions.py:111-115)
WaitTimeoutError.__init__(
    self,
    f"Timed out after {timeout}s waiting for s3://{bucket}/{key}"
    f" to have content matching expected={expected!r}; last body: {actual!r}",
)
```

This pattern is preserved — all three classes doing this (`S3ContentWaitTimeoutError`, `DynamoDBFindItemTimeoutError`, `LambdaInvocableTimeoutError`) will switch to:

```python
WaitTimeoutError.__init__(
    self,
    _format_timeout_error(resource_desc, self.expected, self.actual, self.timeout),
)
```

### Pattern 4: `AggregateWaitTimeoutError` Auto-Enrichment (Confirmed)

`AggregateWaitTimeoutError.__init__` (exceptions.py:503) iterates sub-errors with `str(e)`:

```python
details = "\n".join(f"  - {e}" for e in errors)
```

Once sub-error `__str__` includes `Expected:`/`Actual:` via the shared helper, aggregate output is automatically enriched. **No changes needed to AggregateWaitTimeoutError.**

## Don't Hand-Roll

Nothing to hand-roll. This phase uses Python built-ins exclusively.

## Common Pitfalls

### Pitfall 1: Breaking `DynamoDBFindItemTimeoutError` Attribute Access

`DynamoDBFindItemTimeoutError.__init__` currently sets `self.entries = None` (line 210) for backward compatibility so callers catching as `DynamoDBWaitTimeoutError` can access `.entries` without `AttributeError`. With the rename to `.expected`, the compatibility attribute must still exist on instances.

**Mitigation:** After renaming the constructor parameter from `entries` to `expected`, set `self.entries = expected` as a backward-compat alias. The canonical field is `.expected`; `.entries` is a deprecated alias.

### Pitfall 2: `DynamoDBWaitTimeoutError.message` Override Path (D-06)

When `message` is provided, the legacy path appends `Actual:` to the custom message. With the shared helper, this path must still work. The simplest approach: when `message is not None`, construct the message manually as before (preserving the legacy format) rather than going through `_format_timeout_error`. Document as deprecated compatibility path.

**Mitigation:** Keep the `if message is not None` branch in `DynamoDBWaitTimeoutError.__init__` and append to it manually. Only use `_format_timeout_error` when `message is None`.

### Pitfall 3: `repr()` Output Length vs Content Length

`_truncate_value` uses `len(repr(value))` for the 500-char threshold (D-09). Must use `repr()` output for threshold check AND content — not `str()` which may differ for some types (e.g., strings where `repr` adds quotes).

**Mitigation:** Always use `repr(value)` for both length checks and output generation.

### Pitfall 4: Call Site Parameter Renames

`dynamodb.py` has 9 call sites passing `entries=` to `DynamoDBWaitTimeoutError`. `sqs.py` has call sites passing `body=` and `event=`. All must be renamed to `expected=`.

**Mitigation:** Use grep to find all call sites, rename systematically. Verify with `grep -rn "entries=" aws_expect/dynamodb.py` returns zero matches after the change.

## Implementation Strategy

The implementation follows a **shared-helper-first** approach:

1. **`_utils.py` first** — Write `_truncate_value` and `_format_timeout_error` with comprehensive docstrings and type annotations. These are pure functions with no imports from `aws_expect.*` — fully testable in isolation.

2. **Base class second** — Add `expected`/`actual` class-level attributes to `WaitTimeoutError`.

3. **Exceptions third** — Update each `WaitTimeoutError` subclass to use the shared helper, preserving backward compatibility.

4. **Call sites fourth** — Rename `entries=` → `expected=`, `body=` → `expected=`, `event=` → `expected=` in all service modules.

5. **Tests fifth** — Add unit tests for `_truncate_value` and `_format_timeout_error`, update existing exception tests to verify new `__str__` format.

## Validation Architecture

### Unit Tests (new: `tests/test_utils_truncate.py`, `tests/test_utils_format.py`)

| Test Suite | What It Verifies | Dimension |
|-----------|-----------------|-----------|
| `test_truncate_value` | Truncation rules: None, small list, large list, short value, long value, edge cases | 1 |
| `test_format_timeout_error` | Message format: both None, expected only, actual only, both present, truncation in output | 1 |

### Integration Tests (update: `tests/test_exceptions.py`)

| Test | What It Verifies | Dimension |
|------|-----------------|-----------|
| Each `WaitTimeoutError` subclass `__str__` | Contains `Expected:`/`Actual:` when fields are present | 2 |
| `AggregateWaitTimeoutError.__str__` | Sub-errors enriched automatically | 2 |
| Backward compat: `.entries` access | `DynamoDBFindItemTimeoutError` still has `.entries` | 3 |

## Code Examples

### `_truncate_value` Function

```python
def _truncate_value(value: Any) -> str:
    """Format *value* for inclusion in timeout error messages.
    
    Applies truncation for large collections and oversized values.
    Never raises — always returns a string.
    """
    if value is None:
        return "None"
    if isinstance(value, (list, tuple)):
        if len(value) <= 50:
            return repr(value)
        shown = repr(value[:50])
        remaining = len(value) - 50
        return f"{shown}\n... ({remaining} more items not shown)"
    s = repr(value)
    if len(s) <= 500:
        return s
    return f"{s[:500]}\n... (value truncated, showing first 500 of {len(s)} chars)"
```

### `_format_timeout_error` Function

```python
def _format_timeout_error(
    resource_desc: str,
    expected: Any,
    actual: Any,
    timeout: float,
) -> str:
    """Produce a structured timeout error message with Expected:/Actual: sections.
    
    Omits sections when expected or actual is None.
    Uses _truncate_value for safe formatting of large values.
    """
    lines = [f"Timed out after {timeout}s waiting for {resource_desc}"]
    if expected is not None or actual is not None:
        lines.append("")  # blank line separator
    if expected is not None:
        lines.append("Expected:")
        lines.append(f"  {_truncate_value(expected)}")
    if actual is not None:
        if expected is not None:
            lines.append("")  # blank line between sections  
        lines.append("Actual:")
        lines.append(f"  {_truncate_value(actual)}")
    return "\n".join(lines)
```

### Updated `S3ContentWaitTimeoutError.__init__`

```python
def __init__(
    self,
    bucket: str,
    key: str,
    expected: dict[str, Any],
    actual: dict[str, Any] | None,
    timeout: float,
) -> None:
    self.bucket = bucket
    self.key = key
    self.expected = expected
    self.actual = actual
    self.timeout = timeout
    WaitTimeoutError.__init__(
        self,
        _format_timeout_error(
            f"s3://{bucket}/{key} to have matching content",
            expected,
            actual,
            timeout,
        ),
    )
```

### Updated `DynamoDBWaitTimeoutError.__init__` (with legacy `message` support)

```python
def __init__(
    self,
    table_name: str,
    key: dict[str, str] | None,
    timeout: float,
    message: str | None = None,
    expected: dict[str, Any] | None = None,
    actual: dict[str, Any] | None = None,
) -> None:
    self.table_name = table_name
    self.key = key
    self.timeout = timeout
    self.expected = expected
    self.actual = actual
    # D-06: legacy message compatibility path
    if message is not None:
        actual_str = repr(actual) if actual is not None else "None"
        msg = f"{message}\n\nActual (last seen):\n  {actual_str}"
    else:
        resource_desc = f"item {key} in table {table_name}" if key else f"table {table_name}"
        msg = _format_timeout_error(resource_desc, expected, actual, timeout)
    super().__init__(msg)
```

## File Modification Map

| File | Changes | Impact |
|------|---------|--------|
| `aws_expect/_utils.py` | Add `_truncate_value` + `_format_timeout_error` | New functions (~50 LOC) |
| `aws_expect/exceptions.py` | Add `expected`/`actual` to `WaitTimeoutError`; update 8 subclasses | ~80 LOC changed |
| `aws_expect/dynamodb.py` | Rename `entries=` → `expected=` in 9 call sites | ~10 LOC changed |
| `aws_expect/sqs.py` | Rename `body=` → `expected=`, `event=` → `expected=` in 3 call sites | ~5 LOC changed |
| `aws_expect/s3.py` | No parameter renames (already uses `expected`/`actual` names) | 0 LOC |
| `aws_expect/lambda_function.py` | No parameter renames (already uses `expected`/`actual` names) | 0 LOC |
| `tests/test_utils_truncate.py` | New — unit tests for `_truncate_value` | ~60 LOC |
| `tests/test_utils_format.py` | New — unit tests for `_format_timeout_error` | ~60 LOC |
| `tests/test_exceptions.py` | Update — verify new `__str__` format | ~80 LOC added |

## Requirement Traceability

| Requirement | How Implemented |
|-------------|----------------|
| ERR-01: `expected`/`actual` fields on all `WaitTimeoutError` subclasses | Base class class-level attributes + subclass field unification |
| ERR-02: Clear `Expected:`/`Actual:` labeling | `_format_timeout_error` produces consistent format across all subclasses |
| ERR-03: Shared helper with truncation guard | `_format_timeout_error` + `_truncate_value` in `_utils.py` |
