---
phase: 08-dynamodb-smart-polling
plan: 01
subsystem: refactor
tags: [stop-condition, shared-utils, s3, extraction]

# Dependency graph
requires:
  - phase: 07-s3-smart-polling
    provides: S3ObjectExpectation._check_stop_condition static method implementation
provides:
  - Shared `_check_stop_condition` function in `_utils.py` usable by both S3 and DynamoDB modules
affects: [dynamodb, s3, stop-condition]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Stop-condition evaluation is now a shared module-level function in `_utils.py` (not a static method)

key-files:
  created: []
  modified:
    - aws_expect/_utils.py (added imports, _check_stop_condition function)
    - aws_expect/s3.py (import from _utils, remove static method, update call site)

key-decisions:
  - "_check_stop_condition lives in _utils.py as a module-level function, not a static method — pure extraction, zero behavioral change"
  - "S3 resource_id construction (`f\"s3://{bucket}/{key}\"`) stays in the caller; the shared function receives it as a parameter"

patterns-established:
  - "Shared polling utilities go in `_utils.py` with service-specific resource_id construction in each caller"

requirements-completed:
  - DDB-01
  - DDB-02

# Metrics
duration: 4min
completed: 2026-05-10
---

# Phase 8 Plan 1: Extract Shared Stop-Condition Summary

**Shared `_check_stop_condition` function extracted from S3ObjectExpectation to `_utils.py` for reuse by both S3 and DynamoDB modules, with zero behavioral change.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-10T11:32:10Z
- **Completed:** 2026-05-10T11:36:26Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Extracted `_check_stop_condition` from `S3ObjectExpectation` static method to `aws_expect/_utils.py` as a module-level function
- Added `time`, `Callable`, `StopConditionError`, and `StopConditionMetError` imports to `_utils.py`
- Updated `S3ObjectExpectation` to import and call the shared function, removing the static method
- All 38 existing S3 tests pass — backward-compatible refactor with no regression

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _check_stop_condition to _utils.py with required imports** - `df2463d` (refactor)
2. **Task 2: Update s3.py to import and use shared _check_stop_condition, remove static method** - `b8fcb9a` (refactor)

**Plan metadata:** To be committed below.

## Files Modified
- `aws_expect/_utils.py` — Added `time`, `Callable`, `StopConditionError`, `StopConditionMetError` imports; added `_check_stop_condition()` module-level function preserving D-04 (shallow copy), D-05 (bool|str return), D-07 (non-StopConditionMetError wrapping), D-08 (StopConditionMetError re-raise)
- `aws_expect/s3.py` — Added `_check_stop_condition` to import from `_utils.py`; removed `@staticmethod _check_stop_condition` from `S3ObjectExpectation`; updated call site in `_poll_for_entries` to use module-level function (no `self.` prefix); removed unused `StopConditionError`/`StopConditionMetError` imports

## Decisions Made
- None — followed plan as specified. The extraction is a pure refactor with no design decisions needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed unused exception imports from s3.py**
- **Found during:** Task 2 (Update s3.py)
- **Issue:** After removing the static method, `StopConditionError` and `StopConditionMetError` imports became unused in s3.py. Ruff flagged `F401` errors, blocking verification.
- **Fix:** Ran `ruff check --fix` to auto-remove the two unused imports. The exceptions are now only imported by `_utils.py` where they're actually used.
- **Files modified:** `aws_expect/s3.py` (removed 2 import lines)
- **Verification:** `ruff check` passes with zero errors; `ty check` passes; all 38 S3 tests pass
- **Committed in:** `b8fcb9a` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minimal — removed dead imports that became dead as a direct result of the planned extraction. No scope creep.

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- `_check_stop_condition` is now available in `_utils.py` for `dynamodb.py` to import in Plan 08-02
- The function has zero S3-specific dependencies — ready for DynamoDB reuse
- No blockers

## Verification Results

```
=== Type Check ===
uv run ty check aws_expect/_utils.py aws_expect/s3.py
All checks passed!

=== Lint ===
uv run ruff check aws_expect/_utils.py aws_expect/s3.py
All checks passed!

=== Format ===
uv run ruff format --check aws_expect/_utils.py aws_expect/s3.py
2 files already formatted

=== S3 Regression Tests ===
uv run pytest tests/test_s3_exist.py tests/test_s3_content.py \
  tests/test_s3_not_exist.py tests/test_s3_stop_when.py -v
38 passed in 38.37s
```

---

*Phase: 08-dynamodb-smart-polling*
*Completed: 2026-05-10*
