# Roadmap: aws-expect

## Milestones

- ✅ **v1.0.0 Foundation** — Shipped 2026-04-14
- ✅ **v1.1.0 Richer Assertions** — Phases 1–3 (shipped 2026-04-27)
- 🔄 **v1.2.0 DX & Parallel** — Phase 4 shipped, Phase 5 deferred to v1.3.0
- 🔄 **v1.3.0 Smart Polling & Richer Errors** — Phases 6–9 (active)

## Phases

<details>
<summary>✅ v1.0.0 Foundation — SHIPPED 2026-04-14</summary>

Established declarative AWS waiters for S3, DynamoDB, SQS, and Lambda with parallel execution support and a shared `_deep_matches` utility. Tracked externally via release-please.

</details>

<details>
<summary>✅ v1.1.0 Richer Assertions (Phases 1–3) — SHIPPED 2026-04-27</summary>

- [x] Phase 1: S3 Content Matching (2/2 plans) — completed 2026-04-25
- [x] Phase 2: DynamoDB Scan Search (2/2 plans) — completed 2026-04-26
- [x] Phase 3: Lambda Response Improvements (2/2 plans) — completed 2026-04-26

Archive: `.planning/milestones/v1.1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2.0 DX & Parallel (Phase 4) — SHIPPED 2026-04-28</summary>

- [x] **Phase 4: Housekeeping + expect_any** — Version bump, docstring fix, and any-waiter implementation (completed 2026-04-28)

Phase 5 (Richer Timeout Error Messages) deferred to v1.3.0 — ERR requirements folded into v1.3.0.

</details>

### v1.3.0 Smart Polling & Richer Errors

- [ ] **Phase 6: Exception Foundation** — `StopConditionMetError` and `StopConditionError` exception classes
- [ ] **Phase 7: S3 Smart Polling** — `stop_when` predicate on S3 polling methods
- [ ] **Phase 8: DynamoDB Smart Polling** — `stop_when` predicate on DynamoDB polling methods (3 plans)
- [ ] **Phase 9: Richer Timeout Errors** — Structured `expected`/`actual` in all `WaitTimeoutError.__str__` output

## Phase Details

### Phase 6: Exception Foundation
**Goal**: New exception types for smart polling exist, integrate with the hierarchy, and are importable from the public API
**Depends on**: Nothing (first phase of v1.3.0)
**Requirements**: EXN-01, EXN-02
**Success Criteria** (what must be TRUE):
  1. `StopConditionMetError` can be imported from `aws_expect`, raises cleanly with `resource_id` and `stop_reason`, and is NOT caught by `except WaitTimeoutError`
  2. `StopConditionError` can be raised with a cause exception and preserves the original via `__cause__` when printed
  3. No existing public API is broken — all existing 167 integration tests pass with the new exception classes in the hierarchy
**Plans:** 1 plan

Plans:
- [ ] 06-01-PLAN.md — Implement StopConditionMetError and StopConditionError, integrate into public API, add unit tests

### Phase 7: S3 Smart Polling
**Goal**: S3 polling methods support early abort via `stop_when` predicates, with clear error reporting when stop conditions fire
**Depends on**: Phase 6
**Requirements**: S3P-01, S3P-02, S3P-03
**Success Criteria** (what must be TRUE):
  1. Users can pass `stop_when=lambda state: ...` to `to_exist(entries=...)` and polling aborts with `StopConditionMetError` when the predicate returns `True`
  2. Passing `stop_when` to `to_exist()` without `entries` raises `TypeError` immediately, before any polling begins
  3. When the resource already satisfies the success condition, `stop_when` is never checked — the waiter returns success (main-condition-wins ordering)
  4. State dicts passed to predicates are shallow copies — mutations inside the predicate do not affect subsequent poll iterations
  5. Predicate return values are preserved as `stop_reason` in `StopConditionMetError` for debugging context
**Plans**: 2 plans

Plans:
- [ ] 07-01-PLAN.md — Add stop_when parameter, overloads, TypeError guard, and _check_stop_condition helper to S3ObjectExpectation
- [ ] 07-02-PLAN.md — Write comprehensive integration tests for stop_when predicate (12+ test scenarios)

### Phase 8: DynamoDB Smart Polling
**Goal**: DynamoDB polling methods support early abort via `stop_when` predicates, including per-item evaluation during paginated scans
**Depends on**: Phase 7
**Requirements**: DDB-01, DDB-02, DDB-03
**Success Criteria** (what must be TRUE):
  1. Users can pass `stop_when=lambda state: ...` to `to_exist(entries=...)` on DynamoDB items and polling aborts with `StopConditionMetError` when the predicate fires
  2. `to_find_item(entries=...)` with `stop_when` evaluates the predicate per-item during the paginated scan and aborts the entire scan when it returns `True`
  3. Main-condition-wins ordering is preserved across all DynamoDB polling methods — success is checked before `stop_when` on every iteration
  4. Existing DynamoDB waiters without `stop_when` continue to work identically with no behavioral changes
  5. State dicts document what keys each method provides (e.g., item dict for `to_exist`, `{"item_count": int}` for `to_be_empty`)
**Plans**: 3 plans

Plans:
- [ ] 08-01-PLAN.md — Extract _check_stop_condition to _utils.py, update S3 imports
- [ ] 08-02-PLAN.md — Add stop_when to DynamoDBItemExpectation.to_exist and to_find_item
- [ ] 08-03-PLAN.md — Write integration tests for DynamoDB stop_when (18 test scenarios)

### Phase 9: Richer Timeout Errors
**Goal**: Every timeout failure message shows what was expected and what was actually found, making failures self-documenting without a debugger
**Depends on**: Phase 8
**Requirements**: ERR-01, ERR-02, ERR-03
**Success Criteria** (what must be TRUE):
  1. Every `WaitTimeoutError` subclass prints a message with clearly labeled `Expected:` / `Actual:` sections when those fields are present
  2. Error messages for large collections are truncated (max 50 items, max 500 chars per value) and explicitly indicate truncation occurred
  3. The `Expected:` / `Actual:` format is consistent across S3, DynamoDB, SQS, and Lambda timeout errors — same labels, same structure
  4. Exceptions with `expected=None` or `actual=None` gracefully omit those sections rather than printing `None`
  5. Legacy attribute names (e.g., `entries`, `body`, `event`) are preserved for backward compatibility — only `__str__` output improves
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. S3 Content Matching | v1.1.0 | 2/2 | Complete | 2026-04-25 |
| 2. DynamoDB Scan Search | v1.1.0 | 2/2 | Complete | 2026-04-26 |
| 3. Lambda Response Improvements | v1.1.0 | 2/2 | Complete | 2026-04-26 |
| 4. Housekeeping + expect_any | v1.2.0 | 2/2 | Complete | 2026-04-28 |
| 5. Richer Timeout Error Messages | v1.2.0 | 0/3 | Deferred | — |
| 6. Exception Foundation | v1.3.0 | 0/1 | Planned | — |
| 7. S3 Smart Polling | v1.3.0 | 0/2 | Planned | — |
| 8. DynamoDB Smart Polling | v1.3.0 | 0/3 | Planned | — |
| 9. Richer Timeout Errors | v1.3.0 | 0/? | Not started | — |
