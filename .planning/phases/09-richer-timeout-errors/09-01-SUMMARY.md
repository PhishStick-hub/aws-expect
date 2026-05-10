---
phase: 09-richer-timeout-errors
plan: 01
subsystem: exceptions
tags: [truncation, formatting, error-messages, wait-timeout, expected-actual]

# Dependency graph
requires: []
provides:
  - Shared _truncate_value helper with 50-item / 500-char truncation guards
  - Shared _format_timeout_error helper producing Expected:/Actual: sections
  - WaitTimeoutError base class with expected/actual class-level defaults
affects: [09-02, all WaitTimeoutError subclasses]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Private module-level helper functions in _utils.py for shared formatting logic"
    - "Class-level attributes with Any = None defaults for inherited error context"

key-files:
  created:
    - tests/test_utils_truncate.py — 8 unit tests for _truncate_value
    - tests/test_utils_format.py — 7 unit tests for _format_timeout_error
  modified:
    - aws_expect/_utils.py — added _truncate_value and _format_timeout_error
    - aws_expect/exceptions.py — added expected/actual to WaitTimeoutError

key-decisions:
  - "_truncate_value uses repr() for both threshold check and output (per D-09)"
  - "_format_timeout_error is a module-level function in _utils.py (per D-13), not a method on WaitTimeoutError"
  - "expected/actual are class-level attributes on WaitTimeoutError (per D-01), inherited by subclasses automatically"

patterns-established:
  - "Truncation pattern: 50 items for lists/tuples, 500 chars for repr output"
  - "Error message format: single-line header + optional Expected:/Actual: sections"

requirements-completed:
  - ERR-03

# Metrics
duration: 9 min
completed: 2026-05-10
---

# Phase 9 Plan 1: Shared truncation and formatting helpers + WaitTimeoutError base class Summary

**Shared `_truncate_value` and `_format_timeout_error` helpers in `_utils.py`, plus `expected`/`actual` class-level defaults on `WaitTimeoutError`, with 15 unit tests — foundation for richer timeout errors across all service modules.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-10T13:58:39Z
- **Completed:** 2026-05-10T14:07:40Z
- **Tasks:** 3
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- `_truncate_value(value)` — truncation helper with 50-item list/tuple limit and 500-char repr limit, never raises
- `_format_timeout_error(resource_desc, expected, actual, timeout)` — structured error message producer with `Expected:`/`Actual:` sections
- `WaitTimeoutError.expected` and `WaitTimeoutError.actual` — class-level defaults (`None`) inherited by all subclasses
- 15 unit tests pass; all 222 existing integration tests pass (zero regression)

## Task Commits

Each task was committed atomically (TDD RED→GREEN for Tasks 1–2):

1. **Task 1: RED — `_truncate_value` tests** — `351e195` (test)
2. **Task 1: GREEN — `_truncate_value` impl** — `ff07b09` (feat)
3. **Task 2: RED — `_format_timeout_error` tests** — `a821e39` (test)
4. **Task 2: GREEN — `_format_timeout_error` impl** — `badbc4c` (feat)
5. **Task 3: `WaitTimeoutError` expected/actual** — `e03070e` (feat)

## Files Created/Modified

- `tests/test_utils_truncate.py` — 8 unit tests covering None, small/large lists, short/long values, tuples, ints, dicts
- `tests/test_utils_format.py` — 7 unit tests covering both-None, one-None, both-present, truncation, timeout, resource_desc
- `aws_expect/_utils.py` — Added `_truncate_value` (34 lines) and `_format_timeout_error` (44 lines)
- `aws_expect/exceptions.py` — Added `expected: Any = None` and `actual: Any = None` to `WaitTimeoutError` with docstrings

## Decisions Made

- `_truncate_value` uses `repr()` exclusively for both threshold check and output content (per D-09)
- `_format_timeout_error` is a module-level function in `_utils.py` (per D-13), not a method on `WaitTimeoutError` — avoids circular imports when service modules import it
- `expected`/`actual` are class-level attributes on `WaitTimeoutError` (per D-01), so subclasses inherit `None` without declaring them

## Deviations from Plan

None — plan executed exactly as written. All TDD gates passed cleanly.

## Issues Encountered

None.

## Next Phase Readiness

- `_truncate_value` and `_format_timeout_error` are ready for Plan 02, where all `WaitTimeoutError` subclasses will wire the helper in their `__init__` methods
- `WaitTimeoutError.expected`/`actual` defaults are ready for subclass field unification (D-02)

---
*Phase: 09-richer-timeout-errors*
*Completed: 2026-05-10*
