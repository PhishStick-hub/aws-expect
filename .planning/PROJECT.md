# aws-expect

## What This Is

A Python library providing declarative waiters for AWS services (S3, DynamoDB, Lambda, SQS) using boto3. Users express *intent* ("wait for object to exist") rather than writing imperative polling loops. Includes parallel execution primitives (`expect_all`, `expect_any`) and recursive content matching via `_deep_matches`.

## Core Value

Correct, declarative AWS waiters with good error messages — users write *what* they expect, not *how* to poll for it.

## Requirements

### Validated

- ✓ S3 object existence/absence waiters — v1.0
- ✓ S3 JSON content matching (`to_have_content`, `to_not_have_content`) — v1.1.0
- ✓ DynamoDB item existence with entry matching — v1.0
- ✓ DynamoDB scan-based search (`to_find_item`, `to_not_find_item`) — v1.1.0
- ✓ DynamoDB table existence/deletion waiters — v1.0
- ✓ Lambda active/invokable/respond with waiters — v1.0
- ✓ Lambda optional body + deep matching in `to_respond_with` — v1.1.0
- ✓ SQS message presence/consumption waiters — v1.0
- ✓ `_deep_matches` shared utility across all services — v1.1.0
- ✓ `expect_all` / `expect_any` parallel execution — v1.0
- ✓ `stop_when` condition on `to_exist` / `to_find_item` — v1.3.0
- ✓ Richer timeout error formatting with Expected:/Actual: sections — v1.3.0

### Active

- [ ] `expect_all` / `expect_any` accept `(callable, args, kwargs)` tuples alongside plain `Callable[[], T]`

### Out of Scope

- S3 raw text/CSV body matching — JSON subset covers primary testing use case
- DynamoDB `to_have_item_count(n)` — scan-based match covers main scenario
- New AWS services (EventBridge, SNS, Step Functions) — separate milestone
- DynamoDB smart polling (Phase 08) — in-progress, separate milestone

## Context

**Codebase:** Python 3.13+, uv package manager, hatchling build, pytest with LocalStack/testcontainers for integration tests. Static typing via ty, lint/format via ruff.

**Services covered:** S3 (object expectations), DynamoDB (item + table expectations), Lambda (function expectations), SQS (queue expectations).

**Patterns:** Expectation classes accept boto3 client/resource, provide declarative methods (`to_exist`, `to_not_exist`, etc.). Polling uses `time.monotonic()` with guaranteed at-least-one check. Shared utilities in `_utils.py`.

**Current state:** `expect_all` / `expect_any` in `aws_expect/parallel.py` accept `Sequence[Callable[[], T]]` — zero-argument callables only. Users must wrap expectations in `lambda:` closures.

## Constraints

- **Backward compatibility**: Existing zero-arg callable usage must continue working
- **Type hints**: All new code fully type-annotated
- **Testing**: LocalStack integration tests only — no mocks for boto3
- **Python**: 3.13+

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| `_deep_matches` as shared utility | All four services need recursive subset matching | ✓ Good |
| `WaitTimeoutError.__init__` direct call pattern | Exception subclasses with different data models | ✓ Good |
| Exception-direct inheritance for unexpected-presence | Signals unexpected presence, not timeout | ✓ Good |
| `expect_all` / `expect_any` via thread pool | Simple, reliable parallel execution | ✓ Good |

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

## Current Milestone: v1.4.0 Lambda Args for expect_all / expect_any

**Goal:** Allow `expect_all` and `expect_any` to accept callables with positional args and keyword args alongside existing zero-argument callables.

**Target features:**
- Accept `(callable, args: tuple, kwargs: dict)` tuples mixed with plain `Callable[[], T]`
- Same return types (list[T] for expect_all, T for expect_any)
- Same error handling (AggregateWaitTimeoutError with None for failures)
- Full backward compatibility

---
*Last updated: 2026-05-10 after milestone v1.4.0 start*
