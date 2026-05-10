---
phase: 09-richer-timeout-errors
plan: 02
subsystem: exceptions
tags: [python, pytest, boto3, error-formatting]

# Dependency graph
requires:
  - phase: 09-01
    provides: "_format_timeout_error and _truncate_value in _utils.py; expected/actual class-level attrs on WaitTimeoutError"
provides:
  - "All 8 WaitTimeoutError subclasses produce structured Expected:/Actual: sections via shared helper"
  - "Unified field names: entries→expected, body→expected, event→expected with backward-compat aliases"
  - "Legacy DynamoDBWaitTimeoutError.message path preserved (D-06)"
  - "26 unit-level exception tests + 238 integration tests pass"
affects: [future error enrichment phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_format_timeout_error called from each subclass __init__"
    - "Direct WaitTimeoutError.__init__ bypass pattern for multi-level subclasses"
    - "Lazy imports in _check_stop_condition to break circular dependency with exceptions.py"

key-files:
  created: ["tests/test_exceptions.py"]
  modified:
    - "aws_expect/exceptions.py (8 subclasses wired + import)"
    - "aws_expect/_utils.py (circular import fix: lazy StopConditionError/StopConditionMetError)"
    - "aws_expect/dynamodb.py (entries=→expected= call site rename)"
    - "aws_expect/sqs.py (event→expected= keyword rename in SQSEventWaitTimeoutError calls)"
    - "tests/test_dynamodb_item.py (assertion format updates)"
    - "tests/test_lambda_invoke.py (assertion format updates)"
    - "tests/test_sqs.py (assertion format updates)"
    - "tests/test_sqs_event.py (assertion format updates)"

key-decisions:
  - "Lazy imports for StopConditionError/StopConditionMetError in _check_stop_condition to avoid circular import (actual risk found; RESEARCH.md incorrectly predicted no cycle)"
  - "Positional args in sqs.py _receive_batches still pass error_hint which maps correctly to new expected parameter"

patterns-established:
  - "Multi-level subclass pattern: DynamoDBFindItemTimeoutError calls WaitTimeoutError.__init__ directly with _format_timeout_error to bypass DynamoDBWaitTimeoutError.__init__ signature"
  - "Backward-compat alias pattern: self.entries = expected, self.body = expected, self.event = expected with deprecation comments"
  - "Legacy message path: DynamoDBWaitTimeoutError.__init__ branches on 'message is not None' for D-06 compatibility"

requirements-completed:
  - ERR-01
  - ERR-02

# Metrics
duration: 27min
completed: 2026-05-10
---

# Phase 9 Plan 2: Wire WaitTimeoutError Subclasses Summary

**All 8 WaitTimeoutError subclasses produce structured Expected:/Actual: error messages via shared _format_timeout_error helper, with unified field names and backward-compat aliases**

## Performance

- **Duration:** 27 min
- **Started:** 2026-05-10T14:16:17Z
- **Completed:** 2026-05-10T14:43:38Z
- **Tasks:** 4
- **Files modified:** 9

## Accomplishments
- All 8 WaitTimeoutError subclasses wired to _format_timeout_error with consistent Expected:/Actual: output
- Field names unified: entries→expected, body→expected, event→expected with deprecation aliases (.entries, .body, .event)
- D-06 legacy message path preserved for DynamoDBWaitTimeoutError
- 238 integration tests pass with zero regressions (all 10 pre-existing assertion failures updated)
- Circular import between exceptions.py and _utils.py resolved via lazy imports in _check_stop_condition

## Task Commits

1. **Task 1: Update all 8 WaitTimeoutError subclasses** - `9bc02eb` (feat(09-02))
2. **Task 2: Rename call site parameters** - `e7f9ad4` (feat(09-02))
3. **Task 3: Extend exception tests** - `92a69db` (test(09-02))
4. **Task 4: Full test suite verification** - `913722c` (test(09-02))

## Files Created/Modified

- `aws_expect/exceptions.py` - 8 subclasses wired to _format_timeout_error; import added; field renames with backward-compat
- `aws_expect/_utils.py` - Lazy imports of StopConditionError/StopConditionMetError to break circular dependency
- `aws_expect/dynamodb.py` - entries=→expected= call site rename in to_exist
- `aws_expect/sqs.py` - SQSEventWaitTimeoutError calls use expected=event keyword
- `tests/test_exceptions.py` - 16 new test methods across 8 test classes (created)
- `tests/test_dynamodb_item.py` - Assertion format updates for new error output
- `tests/test_lambda_invoke.py` - Assertion format updates for new error output
- `tests/test_sqs.py` - Assertion format updates for new error output
- `tests/test_sqs_event.py` - Assertion format updates for new error output

## Decisions Made
- Lazy imports in _utils.py for StopConditionError/StopConditionMetError — RESEARCH.md predicted no circular import risk, but actual runtime revealed a cycle when exceptions.py imported _format_timeout_error from _utils.py
- Pre-existing integration test assertions updated from old format ("Expected entries:", "Expected body:", "Expected event:", "Actual (last seen):") to new format ("Expected:", "Actual:") — 10 tests updated

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Circular import between exceptions.py and _utils.py**
- **Found during:** Task 1 (verification script)
- **Issue:** `exceptions.py` importing `_format_timeout_error` from `_utils.py` at module level while `_utils.py` imported `StopConditionError, StopConditionMetError` from `exceptions.py` at module level created a circular import
- **Fix:** Moved StopConditionError/StopConditionMetError imports into _check_stop_condition as lazy imports. RESEARCH.md incorrectly predicted no circular import risk.
- **Files modified:** `aws_expect/_utils.py`
- **Committed in:** `9bc02eb`

**2. [Rule 1 - Bug] Pre-existing integration test assertions broke after format change**
- **Found during:** Task 4 (full test suite run)
- **Issue:** 10 integration tests asserted on old error message format strings ("Expected entries:", "Expected body:", "Expected event:", "Actual (last seen):") that no longer appear after switching to _format_timeout_error
- **Fix:** Updated all 10 test assertions to match new format. When actual is None (empty queue), assert "Actual:" not in message (section omitted by design).
- **Files modified:** `tests/test_dynamodb_item.py`, `tests/test_lambda_invoke.py`, `tests/test_sqs.py`, `tests/test_sqs_event.py`
- **Committed in:** `913722c`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep. The circular import fix was a genuine discovery missed in research.

## Issues Encountered
- None beyond the auto-fixed deviations.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Phase 09 complete — all WaitTimeoutError subclasses produce enriched error messages
- Ready for UAT verification (verify-work)

---
*Phase: 09-richer-timeout-errors*
*Completed: 2026-05-10*
