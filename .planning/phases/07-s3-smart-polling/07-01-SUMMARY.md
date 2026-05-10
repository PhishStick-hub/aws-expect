---
phase: 07-s3-smart-polling
plan: 01
subsystem: s3
tags: [stop_when, predicate, polling, s3, early-abort]

# Dependency graph
requires:
  - phase: 06-exception-foundation
    provides: StopConditionMetError and StopConditionError exception classes
provides:
  - S3ObjectExpectation.to_exist(entries=, stop_when=) with early abort support
  - _check_stop_condition helper (originally S3 static method, later extracted to _utils.py in Phase 8-01)
affects: [08-dynamodb-smart-polling, s3]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Keyword-only stop_when parameter on polling methods — enforced via TypeError guard when entries is None"
    - "Main-condition-wins ordering: check success → check stop_when → check timeout"
    - "Shallow-copied state dicts (dict(state)) prevent predicate mutation corruption"

key-files:
  created: []
  modified:
    - aws_expect/s3.py — added stop_when parameter, overloads, TypeError guard, polling loop integration

key-decisions:
  - "stop_when is keyword-only on to_exist entries path — prevents positional confusion"
  - "stop_when without entries raises TypeError immediately, before any polling"
  - "Main-condition-wins: success checked before stop_when on every iteration"
  - "State dicts are shallow-copied before passing to predicates"
  - "Predicate return values (str or True) preserved as stop_reason in StopConditionMetError"

patterns-established:
  - "Keyword-only callable parameter on polling methods for early abort"
  - "Resource ID construction (f's3://{bucket}/{key}') stays in caller, passed to shared helper"

requirements-completed:
  - S3P-01
  - S3P-02
  - S3P-03

# Metrics
duration: ~20 min (implemented alongside Phase 8-01 refactor)
completed: 2026-05-10
---

# Phase 7 Plan 1: S3 Smart Polling Implementation Summary

**Added stop_when predicate support to S3ObjectExpectation.to_exist(entries=...) — the custom-entry polling path — with keyword-only enforcement, TypeError guard, and early abort via StopConditionMetError.**

## Performance

- **Duration:** Implemented as part of Phase 8-01 extraction work
- **Committed:** 2026-05-10 (refactored in `b8fcb9a`, extracted to `_utils.py` in `df2463d`)
- **Tasks:** 2 (add stop_when + overloads, implement _check_stop_condition)
- **Files modified:** 1 (s3.py)

## Accomplishments

- `stop_when` keyword-only parameter added to `S3ObjectExpectation.to_exist(entries=...)` — callable receives shallow-copied state dict
- Third `@overload` signature discriminates the stop_when variant from the no-entries variant
- `TypeError` raised immediately when `stop_when` is provided without `entries` — no polling started
- `_check_stop_condition` helper (originally static method on S3ObjectExpectation) evaluates predicates with shallow copy, string-return support, and crash wrapping
- Main-condition-wins ordering: entry match checked first, then stop_when, then timeout deadline
- All 38 existing S3 tests pass with zero regression

## Task Commits

Implementation was folded into Phase 8-01 extraction:

1. **`df2463d`** — refactor(08-01): extracted _check_stop_condition to shared _utils.py (originally implemented as S3 static method)
2. **`b8fcb9a`** — refactor(08-01): migrated S3ObjectExpectation to use shared _check_stop_condition, removed static method, cleaned imports

## Files Modified

- `aws_expect/s3.py` — Added 3rd `@overload` for stop_when variant (lines 51-59), `stop_when` keyword-only parameter (line 67), TypeError guard (lines 107-111), _poll_for_entries signature update (line 149), main-condition-wins check ordering (lines 167-169)

## Decisions Made

- `stop_when` is keyword-only on the entries path — prevents accidental positional use
- TypeError guard fires before any API calls — fail-fast behavior
- Shallow copy via `state.copy()` prevents predicate side-effects from corrupting subsequent iterations
- Predicate returns `bool | str` — strings become descriptive `stop_reason` in the error
- `_check_stop_condition` lazily imports exception classes to avoid circular dependency with exceptions.py

## Deviations from Plan

### Structural change: _check_stop_condition extracted to _utils.py

- **Planned:** Static method `S3ObjectExpectation._check_stop_condition`
- **Actual:** Module-level function `_check_stop_condition` in `aws_expect/_utils.py` (extracted in Phase 8-01)
- **Reason:** Needed by DynamoDB in Phase 8 — made sense to extract immediately rather than duplicate
- **Impact:** Zero behavioral change — same function, same call pattern, different module

## Issues Encountered

None — implementation went smoothly.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `stop_when` on S3 `to_exist` is fully functional and tested
- Pattern ready for DynamoDB replication in Phase 8
- `_check_stop_condition` available in `_utils.py` for DynamoDB import

---
*Phase: 07-s3-smart-polling*
*Completed: 2026-05-10*
