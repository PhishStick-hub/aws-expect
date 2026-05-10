---
gsd_state_version: 1.0
milestone: v1.3.0
milestone_name: Smart Polling & Richer Errors
status: executing
stopped_at: Phase 09 context gathered
last_updated: "2026-05-10T15:13:02.832Z"
last_activity: 2026-05-10
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 8
  completed_plans: 8
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-08)

**Core value:** Every assertion must give a clear error explaining what was expected and what was found when it times out.
**Current focus:** Phase 09 — richer-timeout-errors

## Current Position

Phase: 09 (richer-timeout-errors) — EXECUTING
Plan: 1 of 2
Status: Executing Phase 09
Last activity: 2026-05-10

## Performance Metrics

**Velocity (v1.1.0 reference):**

- Total plans completed: 9
- Timeline: 2 days (2026-04-25 → 2026-04-26)

**Velocity (v1.2.0 reference):**

- Phase 4: 2 plans in 1 day (2026-04-28)
- Phase 5: deferred

**By Phase (v1.1.0):**

| Phase | Plans | Completed |
|-------|-------|-----------|
| 01 — S3 Content Matching | 2 | 2026-04-25 |
| 02 — DynamoDB Scan Search | 2 | 2026-04-26 |
| 03 — Lambda Response Improvements | 2 | 2026-04-26 |

**By Phase (v1.2.0):**

| Phase | Plans | Completed |
|-------|-------|-----------|
| 04 — Housekeeping + expect_any | 2 | 2026-04-28 |
| 05 — Richer Timeout Error Messages | 0/3 | Deferred |

**By Phase (v1.3.0 — planned):**

| Phase | Requirements | Est. Plans |
|-------|-------------|------------|
| 06 — Exception Foundation | EXN-01, EXN-02 | 1–2 |
| 07 — S3 Smart Polling | S3P-01, S3P-02, S3P-03 | 1–2 |
| 08 — DynamoDB Smart Polling | DDB-01, DDB-02, DDB-03 | 2–3 |
| 09 — Richer Timeout Errors | ERR-01, ERR-02, ERR-03 | 2–3 |

## Accumulated Context

### Decisions

Key decisions from v1.1.0–v1.2.0 (full log in PROJECT.md Key Decisions):

- `_deep_matches` extracted to `aws_expect/_utils.py` — shared by SQS, S3, DynamoDB, Lambda
- `WaitTimeoutError.__init__` direct call pattern for subclasses diverging from parent signature
- Exception-direct inheritance for unexpected-presence errors (not `WaitTimeoutError`)
- `LambdaResponseMismatchError`: `payload` renamed to `actual`
- `StopConditionMetError` is NOT a `WaitTimeoutError` subclass — stop-condition triggers are distinct from timeout
- `expect_any` implemented — returns first successful callable, raises `AggregateWaitTimeoutError`

### Research Findings (v1.3.0)

From `.planning/research/SUMMARY.md` (confidence: HIGH):

- **Main-condition-wins ordering**: success check before `stop_when` check in every polling loop
- **Shallow-copied state dicts**: `dict(state)` passed to predicates to prevent mutation corruption
- **StopConditionMetError(Exception)** — deliberate sibling of `WaitTimeoutError`, not subclass
- **Shared `__str__` helper** with truncation guard: max 50 items, max 500 chars per value
- **S3 before DynamoDB**: S3 has 3 simpler methods; pattern stabilizes before DynamoDB's 8 methods

### Blockers/Concerns

None.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| S3 | Raw string/CSV body matching | Deferred to future milestone | v1.1.0 planning |
| DynamoDB | `to_have_item_count(n)` waiter | Deferred to future milestone | v1.1.0 planning |
| S3 | `stop_when` on `to_not_exist`/`to_have_content`/`to_not_have_content` | Deferred to future milestone | v1.3.0 requirements |
| Native waiters | `stop_when` on boto3 native-waiter methods | Out of scope — requires converting to custom loops | v1.3.0 requirements |
| Lambda | `stop_when` on Lambda waiters | Deferred to follow-up milestone | v1.3.0 requirements |
| SQS | `stop_when` on SQS waiters | Deferred to follow-up milestone | v1.3.0 requirements |

## Session Continuity

Last session: 2026-05-10T13:25:22.643Z
Stopped at: Phase 09 context gathered
Next: User approval → `/gsd-plan-phase 6`
