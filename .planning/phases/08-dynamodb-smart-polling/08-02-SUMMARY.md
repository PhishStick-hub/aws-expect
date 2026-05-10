---
phase: 08-dynamodb-smart-polling
plan: 02
subsystem: aws
tags: [dynamodb, stop_when, polling, boto3, predicates]
requires:
  - phase: 08-01
    provides: "_check_stop_condition shared helper in _utils.py, StopConditionMetError/StopConditionError in exceptions.py"
provides:
  - "stop_when keyword-only parameter on DynamoDBItemExpectation.to_exist(entries=..., stop_when=...)"
  - "stop_when keyword-only parameter on DynamoDBItemExpectation.to_find_item(entries=..., stop_when=...)"
  - "_make_resource_id helper producing dynamodb:// URLs per D-12/D-13"
  - "TypeError guard on to_exist when stop_when provided without entries"
affects: [dynamodb, polling, stop-condition]

tech-stack:
  added: []
  patterns:
    - "stop_when predicate integration in DynamoDB polling loops following S3 pattern from Phase 7"
    - "per-item stop_when evaluation during paginated scans with immediate entire-scan abort"
    - "main-condition-wins ordering: entries/deep_matches checked before stop_when"
    - "sorted key items for deterministic resource ID formatting"

key-files:
  created: []
  modified:
    - aws_expect/dynamodb.py

key-decisions:
  - "_check_stop_condition is shared from _utils.py (extracted in Plan 08-01) — zero duplication"
  - "_make_resource_id uses sorted(key.items()) for deterministic dynamodb:// URL formatting"
  - "Main-condition-wins ordering preserved: entries/deep_matches succeed without calling stop_when"
  - "stop_when is keyword-only in both to_exist and to_find_item signatures"
  - "TypeError guard raises immediately before any polling when stop_when given without entries on to_exist"

patterns-established:
  - "to_exist polling loop: get_item → item exists? → entries match? → stop_when? → deadline → sleep"
  - "to_find_item scan loop: for each item → deadline? → deep_matches? → stop_when? → append → next page"
  - "Resource ID: dynamodb://{table}?pk=val for keyed, dynamodb://{table} for table scans"

requirements-completed: [DDB-01, DDB-02, DDB-03]

duration: 10 min
completed: 2026-05-10
---

# Phase 8 Plan 2: DynamoDB Smart Polling Summary

**Added `stop_when` predicate support to `DynamoDBItemExpectation.to_exist` and `to_find_item` — with per-item scan evaluation, entire-scan abort, and sorted-key resource IDs.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-10T11:43:06Z
- **Completed:** 2026-05-10T11:53:27Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- `to_exist(entries={...}, stop_when=lambda s: ...)` accepts keyword-only predicate with TypeError guard when entries missing
- `to_find_item(entries={...}, stop_when=lambda s: ...)` evaluates predicate per-item during paginated scan, aborts entire scan on fire
- Main-condition-wins ordering: entries/deep_matches checked before stop_when in both methods
- `_make_resource_id` produces deterministic `dynamodb://` URLs with sorted key items per D-12/D-13
- All 51 existing DynamoDB tests pass — zero regressions (D-18 backward compatibility confirmed)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add stop_when to to_exist** - `2e23bac` (feat)
2. **Task 2: Add stop_when to to_find_item** - `cca20e6` (feat)

## Files Modified
- `aws_expect/dynamodb.py` — Added `stop_when` to `to_exist` and `to_find_item` (new imports, `_make_resource_id` helper, TypeError guard, polling/scan loop integration, docstring updates)

## Decisions Made
- Used `sorted(key.items())` in `_make_resource_id` for deterministic key ordering (D-12)
- `stop_when is not None` guard before each `_check_stop_condition` call ensures no overhead when not used (D-18)
- `_check_stop_condition` shared helper from `_utils.py` reused without modification
- `StopConditionError` and `StopConditionMetError` imports marked `# noqa: F401` — referenced in docstrings, raised indirectly via `_check_stop_condition`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff F401 unused import warning for StopConditionError/StopConditionMetError**
- **Found during:** Task 1 (ruff check verification)
- **Issue:** `StopConditionError` and `StopConditionMetError` flagged as unused imports — they are used indirectly via `_check_stop_condition` and referenced in docstrings but not in code body
- **Fix:** Added `# noqa: F401` comments with justification per project convention
- **Files modified:** aws_expect/dynamodb.py
- **Verification:** `uv run ruff check aws_expect/dynamodb.py` passes with zero errors
- **Committed in:** 2e23bac (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Cosmetic — imports explicitly required by plan and acceptance criteria. No behavioral impact.

## Issues Encountered
- `pytest --timeout=60` flag not available (no `pytest-timeout` plugin) — ran without flag; all 51 tests passed in 73s

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- DynamoDB `stop_when` implementation complete — ready for Plan 08-03 (tests/verification) or phase verification
- All acceptance criteria met; type checker and linter pass
- Threat mitigations from plan applied: shallow copy via `_check_stop_condition` (T-08-04/05), exception wrapping on predicate crash (T-08-06), fail-fast scan abort (T-08-07)

---
*Phase: 08-dynamodb-smart-polling*
*Completed: 2026-05-10*
