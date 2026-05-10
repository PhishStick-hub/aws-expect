# Milestones

## v1.3.0 Smart Polling & Richer Errors (Shipped: 2026-05-10)

**Phases completed:** 4 phases, 8 plans, 19 tasks

**Key accomplishments:**

- Implemented StopConditionMetError and StopConditionError in aws_expect/exceptions.py, integrated into public API via __init__.py, and added 8 unit tests.
- Added stop_when predicate support to S3ObjectExpectation.to_exist(entries=...) — the custom-entry polling path — with keyword-only enforcement, TypeError guard, and early abort via StopConditionMetError.
- Wrote 12+ integration tests in tests/test_s3_stop_when.py covering truthy returns, string reasons, TypeError guard, main-condition-wins ordering, shallow copy isolation, predicate crash handling, and backward compatibility.
- Shared `_check_stop_condition` function extracted from S3ObjectExpectation to `_utils.py` for reuse by both S3 and DynamoDB modules, with zero behavioral change.
- Added `stop_when` predicate support to `DynamoDBItemExpectation.to_exist` and `to_find_item` — with per-item scan evaluation, entire-scan abort, and sorted-key resource IDs.
- 18 integration tests covering all stop_when behavior on to_exist (10 tests) and to_find_item (8 tests) — verifying D-02 through D-18 locked decisions with zero regressions.
- Shared `_truncate_value` and `_format_timeout_error` helpers in `_utils.py`, plus `expected`/`actual` class-level defaults on `WaitTimeoutError`, with 15 unit tests — foundation for richer timeout errors across all service modules.
- All 8 WaitTimeoutError subclasses produce structured Expected:/Actual: error messages via shared _format_timeout_error helper, with unified field names and backward-compat aliases

---

## v1.0.0 — Foundation (Shipped 2026-04-14)

**Goal:** Establish declarative AWS waiters for S3, DynamoDB, SQS, and Lambda with parallel execution support.

**Shipped:**

- S3: `to_exist` / `to_not_exist` with metadata entry matching
- DynamoDB item: `to_exist`, `to_not_exist`, `to_be_empty`, `to_be_not_empty`, `to_have_numeric_value_close_to`
- DynamoDB table: `to_exist` / `to_not_exist`
- SQS: string-body triplet (`to_have_message`, `to_consume_message`, `to_not_have_message`)
- SQS: JSON event triplet (`to_have_event`, `to_consume_event`, `to_not_have_event`) with deep subset matching
- Lambda: `to_exist`, `to_not_exist`, `to_be_active`, `to_be_updated`, `to_be_invocable`, `to_respond_with`
- `expect_all()` concurrent parallel waiting
- Exception hierarchy rooted at `WaitTimeoutError`
- Shared utils extracted (`_deep_matches`)

**Phases:** 1–N (tracked externally via release-please)

---

## v1.1.0 — Richer Assertions (Shipped 2026-04-27)

**Goal:** Extend existing service expectations with deeper content and body matching across S3, DynamoDB, and Lambda.

**Stats:** 3 phases · 6 plans · 30 new integration tests (170 total) · 49 files changed · 2 days

**Shipped:**

- S3: `to_have_content(entries)` / `to_not_have_content(entries)` — JSON recursive deep-match on object body
- DynamoDB: `to_find_item(entries)` / `to_not_find_item(entries)` — paginated scan-based item search with `_deep_matches`
- Lambda: status-code-only + deep nested body matching in `to_respond_with`; `LambdaResponseMismatchError` attributes enriched (`actual`, `expected_status`, `expected_body`)
- Shared utility: `_deep_matches` extracted from SQS to `aws_expect/_utils.py` — now used by all four services

**Archive:** `.planning/milestones/v1.1.0-ROADMAP.md`
