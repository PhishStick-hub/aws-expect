# Roadmap: aws-expect

## Milestones

- ✅ **v1.0.0 Foundation** — Shipped 2026-04-14
- ✅ **v1.1.0 Richer Assertions** — Phases 1–3 (shipped 2026-04-27)
- ✅ **v1.2.0 DX & Parallel** — Phase 4 shipped, Phase 5 deferred to v1.3.0 (shipped 2026-04-28)
- ✅ **v1.3.0 Smart Polling & Richer Errors** — Phases 6–9 (shipped 2026-05-10)

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

<details>
<summary>✅ v1.3.0 Smart Polling & Richer Errors (Phases 6–9) — SHIPPED 2026-05-10</summary>

- [x] **Phase 6: Exception Foundation** — `StopConditionMetError` and `StopConditionError` exception classes (completed 2026-05-10)
- [x] **Phase 7: S3 Smart Polling** — `stop_when` predicate on S3 polling methods (completed 2026-05-10)
- [x] **Phase 8: DynamoDB Smart Polling** — `stop_when` predicate on DynamoDB polling methods, 3 plans (completed 2026-05-10)
- [x] **Phase 9: Richer Timeout Errors** — Structured `expected`/`actual` in all `WaitTimeoutError.__str__` output, 2 plans (completed 2026-05-10)

Archive: `.planning/milestones/v1.3.0-ROADMAP.md`
Requirements archive: `.planning/milestones/v1.3.0-REQUIREMENTS.md`

</details>

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. S3 Content Matching | v1.1.0 | 2/2 | Complete | 2026-04-25 |
| 2. DynamoDB Scan Search | v1.1.0 | 2/2 | Complete | 2026-04-26 |
| 3. Lambda Response Improvements | v1.1.0 | 2/2 | Complete | 2026-04-26 |
| 4. Housekeeping + expect_any | v1.2.0 | 2/2 | Complete | 2026-04-28 |
| 5. Richer Timeout Error Messages | v1.2.0 | 0/3 | Deferred | — |
| 6. Exception Foundation | v1.3.0 | 1/1 | Complete | 2026-05-10 |
| 7. S3 Smart Polling | v1.3.0 | 2/2 | Complete | 2026-05-10 |
| 8. DynamoDB Smart Polling | v1.3.0 | 3/3 | Complete | 2026-05-10 |
| 9. Richer Timeout Errors | v1.3.0 | 2/2 | Complete | 2026-05-10 |
