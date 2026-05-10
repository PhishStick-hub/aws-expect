# aws-expect

## What This Is

`aws-expect` is a Python library providing declarative, Pythonic waiters for AWS services (S3, DynamoDB, SQS, Lambda) using boto3. It lets integration tests wait for resource state changes with configurable timeouts, content matching, stop-condition predicates (`stop_when`), and structured `Expected:`/`Actual:` error messages — replacing hand-rolled polling loops.

As of v1.3.0, the library supports smart polling with early abort and richer timeout errors.

## Core Value

Every assertion must give a clear error explaining _what was expected and what was found_ when it times out.

## Current Milestone: v1.3.0 Smart Polling & Richer Errors ✅ SHIPPED 2026-05-10

**Delivered:**
- `stop_when` callable parameter on S3 `to_exist(entries=)`, DynamoDB `to_exist(entries=)`, and DynamoDB `to_find_item(entries=)` — receives shallow-copied resource state dict, returns `True` or a string reason to abort early
- `StopConditionMetError` — new exception type, separate from `WaitTimeoutError`, raised when predicate fires before timeout
- `StopConditionError` — wraps exceptions raised inside `stop_when` predicates, preserves original via `__cause__`
- Richer timeout error messages — all `WaitTimeoutError` subclasses include structured `Expected:`/`Actual:` in `__str__`, with 50-item/500-char truncation guards
- `_check_stop_condition` shared utility in `_utils.py` — used by both S3 and DynamoDB

## Current State

**Shipped version:** v1.3.0 Smart Polling & Richer Errors (2026-05-10)

**Public API surface:**
- S3: `to_exist(entries=, stop_when=)`, `to_not_exist`, `to_have_content`, `to_not_have_content`
- DynamoDB item: `to_exist(entries=, stop_when=)`, `to_not_exist`, `to_be_empty`, `to_be_not_empty`, `to_have_numeric_value_close_to`, `to_find_item(entries=, stop_when=)`, `to_not_find_item`
- DynamoDB table: `to_exist`, `to_not_exist`
- SQS: `to_have_message`, `to_consume_message`, `to_not_have_message`, `to_have_event`, `to_consume_event`, `to_not_have_event`
- Lambda: `to_exist`, `to_not_exist`, `to_be_active`, `to_be_updated`, `to_be_invocable`, `to_respond_with`
- Parallel: `expect_all([callables])`, `expect_any([callables])`
- Exceptions: `StopConditionMetError`, `StopConditionError` (new in v1.3.0)

**Test suite:** 238 integration tests against LocalStack (↑ 71 from v1.2.0)
**Version:** `1.1.0` in `__init__.py` (needs bump for v1.3.0 release)

## Requirements

### Validated

<!-- Shipped in v1.0.0 -->
- ✓ `expect_s3(obj).to_exist()` / `to_not_exist()` with metadata entry matching — v1.0.0
- ✓ `expect_dynamodb_item(table).to_exist(key, entries)` / `to_not_exist()` — v1.0.0
- ✓ `expect_dynamodb_item(table).to_be_empty()` / `to_be_not_empty()` — v1.0.0
- ✓ `expect_dynamodb_item(table).to_have_numeric_value_close_to()` — v1.0.0
- ✓ `expect_dynamodb_table(dynamodb, name).to_exist()` / `to_not_exist()` — v1.0.0
- ✓ `expect_sqs(queue).to_have_message()` / `to_consume_message()` / `to_not_have_message()` — v1.0.0
- ✓ `expect_sqs(queue).to_have_event()` / `to_consume_event()` / `to_not_have_event()` (JSON deep match) — v1.0.0
- ✓ `expect_lambda(client).to_exist()` / `to_not_exist()` / `to_be_active()` / `to_be_updated()` — v1.0.0
- ✓ `expect_lambda(client).to_be_invocable(payload, entries)` — v1.0.0
- ✓ `expect_lambda(client).to_respond_with(status_code, body)` — v1.0.0
- ✓ `expect_all([callables])` — parallel concurrent waiting — v1.0.0
- ✓ Exception hierarchy rooted at `WaitTimeoutError` with service-specific subclasses — v1.0.0

<!-- Shipped in v1.1.0 -->
- ✓ S3: `to_have_content(entries: dict)` — wait until object body is valid JSON that deep-matches given dict — v1.1.0
- ✓ S3: `to_not_have_content(entries: dict, delay)` — assert object body does not match after delay — v1.1.0
- ✓ DynamoDB: `to_find_item(entries: dict)` — scan table and wait until at least one item subset-matches — v1.1.0
- ✓ DynamoDB: `to_not_find_item(entries: dict, delay)` — assert no item matches after delay — v1.1.0
- ✓ Lambda: status-code-only shorthand in `to_respond_with` (body optional) — v1.1.0
- ✓ Lambda: deep nested body matching in `to_respond_with` via `_deep_matches` — v1.1.0

<!-- Shipped in v1.2.0 -->
- ✓ `expect_any([callables])` — parallel any-waiter with `AggregateWaitTimeoutError` — v1.2.0
- ✓ Version bumped to `1.1.0` in `__init__.py` and `pyproject.toml` — v1.2.0
- ✓ `to_exist(entries)` docstring documents shallow matching and cross-references `to_have_content` — v1.2.0

<!-- Shipped in v1.3.0 -->
- ✓ `StopConditionMetError` and `StopConditionError` exception classes, exported from `aws_expect` — v1.3.0
- ✓ `stop_when` callable parameter on S3 `to_exist(entries=)` — early abort with `StopConditionMetError` — v1.3.0
- ✓ `stop_when` callable parameter on DynamoDB `to_exist(entries=)` and `to_find_item(entries=)` — per-item scan evaluation — v1.3.0
- ✓ `StopConditionMetError` is NOT caught by `except WaitTimeoutError` — proper hierarchy isolation — v1.3.0
- ✓ `StopConditionError` wraps predicate crashes via `__cause__` (raise-from pattern) — v1.3.0
- ✓ All `WaitTimeoutError` subclasses output structured `Expected:`/`Actual:` in `__str__` — v1.3.0
- ✓ `_truncate_value` and `_format_timeout_error` shared helpers with truncation guards (50 items, 500 chars) — v1.3.0
- ✓ Main-condition-wins ordering: success checked before `stop_when` on every iteration — v1.3.0

### Active

(None — all v1.3.0 requirements shipped. Start `/gsd-new-milestone` for next milestone requirements.)

### Out of Scope

- Raw string / CSV body matching for S3 — JSON subset is the primary testing use case; raw text matching is low value
- DynamoDB item count waiter — deferred; scan-based match covers the main test scenario
- New AWS services (EventBridge, SNS, Step Functions) — separate milestone
- Lambda and SQS stop conditions — deferred to follow-up milestone; S3 + DynamoDB first
- `stop_when` on S3 `to_not_exist`/`to_have_content`/`to_not_have_content` — deferred, not existence-style waiters
- `stop_when` on native-boto3-waiter methods — would require rewriting as custom polling loops with minimal benefit
- `stop_when` on DynamoDB `to_be_empty`/`to_be_not_empty`/`to_have_numeric_value_close_to`/`to_not_exist` — deferred to future milestone

## Context

- Python 3.13+, uv, ruff, ty
- All custom waiters use the same `deadline = monotonic() + timeout` polling pattern
- `_deep_matches`, `_check_stop_condition`, `_truncate_value`, `_format_timeout_error` are shared module-level functions in `aws_expect/_utils.py`
- Tests use `testcontainers[localstack]` — session-scoped container, function-scoped resources with UUID names
- Lambda: no boto3 resource API — uses client directly
- 238 tests (up from 167 in v1.2.0) — 71 new tests for stop_when, truncation, formatting, and exceptions

## Constraints

- **Compatibility**: Must not break any existing public API — new methods/parameters only
- **Tech stack**: boto3, Python 3.13+, uv toolchain
- **Testing**: All new methods must have LocalStack integration tests

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use boto3 resource API where available | Cleaner interface; resource objects carry context | ✓ Good |
| Custom polling over boto3 waiters for content checks | Native waiters don't support content matching | ✓ Good |
| `_deep_matches` extracted to shared `_utils.py` | Reused by SQS, S3, DynamoDB, and Lambda | ✓ Good |
| `DynamoDBNonNumericFieldError` → Exception (not WaitTimeoutError) | Semantic correctness; aligns with LambdaResponseMismatchError | ✓ Good |
| WaitTimeoutError.__init__ direct call for subclasses that diverge from parent signature | Bypass signature mismatch without losing error message | ✓ Good |
| Exception-direct inheritance for unexpected-presence errors | Consistent pattern: SQSUnexpectedMessageError, S3UnexpectedContentError, DynamoDBUnexpectedItemError | ✓ Good |
| `LambdaResponseMismatchError` attribute rename: `payload` → `actual` | Clearer semantics — `actual` is the response that came back, not the input payload | ✓ Good |
| `StopConditionMetError` is NOT a `WaitTimeoutError` subclass | Stop-condition triggers are distinct from timeout — callers must catch them explicitly | ✓ Good |
| `_check_stop_condition` extracted to `_utils.py` as module-level function | Shared by S3 and DynamoDB; service-specific resource_id construction stays in each caller | ✓ Good |
| `stop_when` is keyword-only on entries polling methods | Prevents positional confusion; TypeError guard fires before any API call | ✓ Good |
| Main-condition-wins ordering | Success checked before stop_when on every iteration — intuitive behavior | ✓ Good |
| Shallow-copied state dicts (`dict(state)`) for predicates | Prevents mutation corruption across poll iterations | ✓ Good |
| `_format_timeout_error` + `_truncate_value` as shared helpers | Consistent `Expected:`/`Actual:` format across all 8 `WaitTimeoutError` subclasses | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-10 after v1.3.0 milestone*
