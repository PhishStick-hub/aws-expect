# Phase 6 Research: Exception Foundation

**Phase:** 06 — exception-foundation
**Researched:** 2026-05-09
**Confidence:** HIGH

## Executive Summary

Phase 6 adds two new exception classes to `aws_expect/exceptions.py`: `StopConditionMetError` (raised when a `stop_when` predicate fires during smart polling) and `StopConditionError` (wraps exceptions raised inside `stop_when` predicates). Both inherit from `Exception` directly — not `WaitTimeoutError` — per the project-level decision that stop-condition triggers are semantically distinct from timeouts.

This is the simplest phase in v1.3.0: no new dependencies, no AWS integration, no polling logic changes. Pure Python exception class construction following established patterns already present in the codebase.

## Implementation Patterns (from Codebase)

### Pattern A: Exception-direct inheritance (non-timeout errors)

Used by: `DynamoDBUnexpectedItemError`, `S3UnexpectedContentError`, `SQSUnexpectedMessageError`, `SQSUnexpectedEventError`, `LambdaResponseMismatchError`, `DynamoDBNonNumericFieldError`.

Template:
```python
class XxxError(Exception):
    """Docstring with Attributes: block."""

    def __init__(self, positional: args) -> None:
        self.attr = positional
        super().__init__(f"Formatted message with {attr!r}")
```

Key observations:
- Positional constructor args only (no keyword args)
- `super().__init__(message)` called with a formatted string
- `__str__` is NOT overridden — the message passed to `super().__init__` IS the `__str__` output
- `Attributes:` block in docstring documents each attribute

**This is the pattern for both `StopConditionMetError` and `StopConditionError`.**

### Pattern B: WaitTimeoutError inheritance (timeout errors)

Used by: `S3WaitTimeoutError`, `DynamoDBWaitTimeoutError`, `LambdaWaitTimeoutError`, `SQSWaitTimeoutError`, etc.

Template:
```python
class XxxWaitTimeoutError(WaitTimeoutError):
    timeout: float  # class annotation

    def __init__(self, positional: args) -> None:
        self.timeout = positional
        WaitTimeoutError.__init__(self, f"Formatted message")
```

Key observation: `WaitTimeoutError.__init__(self, message)` is called directly (not `super().__init__`) when the subclass diverges from the parent's signature.

### Pattern C: Rich `__str__` with labelled sections

Used by: `DynamoDBWaitTimeoutError`, `LambdaInvocableTimeoutError`, `SQSWaitTimeoutError`, `SQSEventWaitTimeoutError`.

These format `__str__` via the message passed to the parent constructor, using:
```
Expected entries:
  {entries!r}

Actual (last seen):
  {actual_str}
```

The CONTEXT.md D-06 specifies a similar pytest-assertion style for `StopConditionMetError.__str__`.

### Pattern D: Public API export (__init__.py)

The `from aws_expect.exceptions import (...)` tuple and `__all__` list are both alphabetically ordered. New entries are inserted at their alphabetical position.

## Decision-to-Implementation Mapping

| Decision | Implementation Detail |
|----------|----------------------|
| D-01 (Fields) | `resource_id: str`, `stop_reason: str`, `elapsed: float`, `timeout: float` as positional args → `self.*` attrs |
| D-02 (Predicate return type) | Not implemented here — consumed by Phases 7-8. Type annotation: `Callable[[dict[str, Any]], bool \| str]` |
| D-03 (Constructor) | `StopConditionMetError(resource_id, stop_reason, elapsed, timeout)` — follows Pattern A |
| D-04 (Attributes) | `StopConditionError(resource_id)` — `resource_id: str`, original exception via `__cause__` |
| D-05 (Constructor) | `StopConditionError(resource_id)` — used as `raise StopConditionError(id) from original_exc` |
| D-06 (StopConditionMetError __str__) | Multi-line format via `super().__init__(message)`: "Stop condition met for {resource_id} after {elapsed}s (timeout={timeout}s)\nStop reason: {stop_reason}" |
| D-07 (StopConditionError __str__) | Format via `super().__init__(message)`: "Error in stop_when predicate for {resource_id}: {original_exception_text}" where original_exception_text is `str(original_exc)` |
| D-08 (No shared helper) | Each class formats `__str__` inline. Shared helper deferred to Phase 9. |
| D-09 (Same file) | Both classes go in `aws_expect/exceptions.py` (~40 lines added) |
| D-10 (Placement) | Insert after `WaitTimeoutError` class definition (line ~18), before `S3WaitTimeoutError` (line ~21) |
| D-11 (__init__.py) | Add both to import tuple and `__all__` alphabetically. `StopConditionError` before `StopConditionMetError`. Insert after `S3UnexpectedContentError` and before `S3WaitTimeoutError` in imports; similar position in `__all__`. |

## Edge Cases to Handle

1. **`__cause__` propagation for StopConditionError**: When raised as `raise StopConditionError(id) from original_exc`, Python's standard exception printing includes the chain. The `__str__` should mention the cause but not duplicate the full traceback. Per D-07: include `str(original_exc)` in the message.

2. **Formatting with `elapsed` precision**: The `__str__` should not show excessive decimal places. The existing pattern uses `{timeout}s` without explicit formatting — Python's default float-to-str handles this reasonably (typically 1 decimal for small floats). Follow existing convention.

3. **`__repr__` not overridden**: No existing exception in the codebase overrides `__repr__`. Python's default `__repr__` is sufficient. Don't add custom `__repr__`.

4. **Import ordering precision**: Alphabetical within the import tuple. `StopConditionError` (S-t-o-p-C-o...) comes before `StopConditionMetError` (S-t-o-p-C-o...n-d-i-t-i-o-n-M...) — "StopConditionError" < "StopConditionMetError" alphabetically.

## Verification Approach

Tests needed (test file: `tests/test_exceptions.py` or extend existing):

1. **StopConditionMetError construction**: Verify all 4 attributes are stored correctly
2. **StopConditionMetError.__str__**: Verify the multi-line format matches D-06 exactly
3. **StopConditionMetError hierarchy**: Verify `isinstance(exc, Exception)` is True AND `isinstance(exc, WaitTimeoutError)` is False
4. **StopConditionMetError NOT caught by except WaitTimeoutError**: Explicitly assert that `except WaitTimeoutError` does not catch `StopConditionMetError`
5. **StopConditionError construction**: Verify `resource_id` is stored and `__cause__` is set
6. **StopConditionError.__str__**: Verify message format matches D-07, including the original exception text
7. **Public API imports**: Verify `from aws_expect import StopConditionMetError, StopConditionError` works
8. **Existing test suite**: All 167 existing integration tests must pass

## Files to Modify

| File | Change Type | Lines Added |
|------|-------------|-------------|
| `aws_expect/exceptions.py` | Insert 2 new classes | ~40 |
| `aws_expect/__init__.py` | Add 2 imports + 2 __all__ entries | +4 |
| `tests/test_exceptions.py` (new or existing) | New test class(es) | ~60 |

**Total:** ~100 lines, 3 files, no new dependencies.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Exception hierarchy | HIGH | Pattern A exists 6 times in codebase; exact template available |
| __str__ formatting | HIGH | Pattern C provides exact format precedent (DynamoDBWaitTimeoutError) |
| Public API export | HIGH | Pattern D is mechanical alpha insertion |
| Test approach | HIGH | Existing tests in `tests/` provide exact patterns for exception testing |

**Overall confidence:** HIGH — all implementation patterns exist in the codebase with direct precedents. Zero ambiguity.

## Key Constraints from PROJECT.md

- `StopConditionMetError` inherits `Exception`, NOT `WaitTimeoutError` (locked decision in PROJECT.md Key Decisions)
- `Exception`-direct inheritance for non-timeout errors is the established pattern
- `WaitTimeoutError.__init__` direct call pattern for subclasses diverging from parent signature (not applicable here — both new classes use `super().__init__`)

---

*Research completed: 2026-05-09*
*Ready for planning: yes*
