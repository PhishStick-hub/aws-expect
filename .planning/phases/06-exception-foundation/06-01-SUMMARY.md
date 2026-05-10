---
phase: 06-exception-foundation
plan: 01
subsystem: exceptions
tags: [stop-condition, exception-hierarchy, public-api]

# Dependency graph
requires: []
provides:
  - StopConditionMetError exception class (inherits Exception, NOT WaitTimeoutError)
  - StopConditionError exception class (wraps predicate crashes via __cause__)
  - Public API exports in __init__.py
affects: [07-s3-smart-polling, 08-dynamodb-smart-polling, all stop_when call sites]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Exception-direct inheritance for non-timeout failures (StopConditionMetError, StopConditionError)"
    - "raise-from pattern for wrapping predicate exceptions in StopConditionError"

key-files:
  created:
    - tests/test_exceptions.py — 8 unit tests (243 lines)
  modified:
    - aws_expect/exceptions.py — added StopConditionMetError and StopConditionError classes
    - aws_expect/__init__.py — added public API exports + __all__ entries

key-decisions:
  - "StopConditionMetError inherits Exception (not WaitTimeoutError) — stop-condition triggers are distinct from timeout"
  - "StopConditionError wraps predicate exceptions via __cause__ (raise-from), constructor takes only resource_id"
  - "__str__ format for StopConditionMetError includes resource_id, stop_reason, elapsed, and timeout"
  - "__str__ format for StopConditionError reads cause_text from self.__cause__ at init time"

patterns-established:
  - "Non-timeout errors inherit Exception directly — callers must catch them explicitly rather than having them swallowed by except WaitTimeoutError"

requirements-completed:
  - EXN-01
  - EXN-02

# Metrics
duration: ~30 min (spread across Phase 8-01 and Phase 9-01 implementation bursts)
completed: 2026-05-10
---

# Phase 6 Plan 1: Exception Foundation Summary

**Implemented StopConditionMetError and StopConditionError in aws_expect/exceptions.py, integrated into public API via __init__.py, and added 8 unit tests.**

## Performance

- **Duration:** Implemented alongside Phase 8-01 and Phase 9-01 work
- **Committed:** 2026-05-10 (exceptions in `e03070e`, exports pending commit)
- **Tasks:** 3 (tests → implementation → public API)
- **Files:** 3 (2 modified, 1 created)

## Accomplishments

- `StopConditionMetError(Exception)` — stop-condition trigger exception with `resource_id`, `stop_reason`, `elapsed`, `timeout` attributes, NOT caught by `except WaitTimeoutError`
- `StopConditionError(Exception)` — wraps predicate crashes, preserves original via `__cause__` (raise-from pattern)
- Both classes follow existing exception patterns (docstrings, attribute documentation, super().__init__ message format)
- 8 unit tests in `tests/test_exceptions.py` covering construction, __str__ format, hierarchy isolation, cause chain, and public API importability
- All existing 167 integration tests pass unchanged

## Task Commits

Implemented across two execution bursts:

1. **Base implementation** — `e03070e` (feat(09-01)): Added both exception classes alongside expected/actual on WaitTimeoutError
2. **Tests** — `92a69db` (test(09-02)): 8 unit tests for StopConditionMetError and StopConditionError
3. **Public API exports** — Pending commit: __init__.py import tuple and __all__ entries

## Files Created/Modified

- `aws_expect/exceptions.py` — Added `StopConditionMetError` (lines 32-61, 4 attribute constructor with f-string __str__) and `StopConditionError` (lines 64-81, cause-preserving wrapper)
- `aws_expect/__init__.py` — Added `StopConditionError` and `StopConditionMetError` to import tuple and `__all__`
- `tests/test_exceptions.py` — 8 tests: construction, __str__, hierarchy isolation (not caught by except WaitTimeoutError), cause chain, public API import

## Decisions Made

- Followed D-01: `StopConditionMetError(Exception)` — deliberate sibling of WaitTimeoutError, not subclass
- Followed D-03: Constructor takes (resource_id, stop_reason, elapsed, timeout)
- Followed D-04/D-05: `StopConditionError.__init__(resource_id)` with __cause__ set via raise-from
- Followed D-06/D-07: __str__ formats match CONTEXT.md specifications exactly

## Deviations from Plan

None — implemented exactly as specified in 06-01-PLAN.md.

## Issues Encountered

- Public API exports (__init__.py) remain uncommitted — exported in working tree but not yet in git HEAD

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `StopConditionMetError` and `StopConditionError` are available for S3 and DynamoDB `_check_stop_condition` usage
- `_check_stop_condition` in `_utils.py` lazily imports both classes (lazy import pattern avoids circular dependencies)
- No blockers for Phase 7 (S3 Smart Polling)

---
*Phase: 06-exception-foundation*
*Completed: 2026-05-10*
