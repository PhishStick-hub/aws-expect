---
plan: 04-02
phase: 04-housekeeping-expect-any
status: complete
self_check: PASSED
subsystem: parallel
tags: [tdd, expect_any, concurrent.futures, as_completed]
dependency_graph:
  requires: [04-01]
  provides: [expect_any-implementation]
  affects: [aws_expect/parallel.py, tests/test_parallel_any.py]
tech_stack:
  added: []
  patterns: [as_completed-pattern, threadpoolexecutor, tdd-red-green]
key_files:
  created:
    - tests/test_parallel_any.py
  modified:
    - aws_expect/parallel.py
decisions:
  - "Used concurrent.futures.as_completed to iterate futures as they complete, returning on first success"
  - "Early return from within the ThreadPoolExecutor context manager causes __exit__ to wait for remaining threads, but their results are discarded — acceptable for expect_any semantics"
  - "ValueError raised for empty expectations list (not WaitTimeoutError) — consistent with plan spec"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-28"
  tasks_completed: 2
  files_modified: 2
---

# Phase 4 Plan 02: expect_any — TDD RED/GREEN Implementation Summary

Implemented `expect_any` using `concurrent.futures.as_completed` to return the first
succeeding callable from a ThreadPoolExecutor pool, with full LocalStack integration test coverage.

## Tasks Completed

1. **Task 1 (RED) — Write failing tests for expect_any** — Created `tests/test_parallel_any.py`
   with 9 test methods across two classes. All tests failed with `NotImplementedError` at RED phase,
   confirming the stub was in place. Committed as `test(parallel): add failing tests for expect_any`.

2. **Task 2 (GREEN) — Implement expect_any** — Replaced the `NotImplementedError` stub in
   `aws_expect/parallel.py` with a full implementation using `as_completed`. Added `as_completed`
   to the `concurrent.futures` import. All 9 new tests pass; full suite of 167 tests green.
   Committed as `feat(parallel): implement expect_any — return first succeeding callable`.

## Test Methods Written

### TestExpectAnySuccess
- `test_returns_first_result_when_one_succeeds_immediately` — all three tables seeded; result is one of the known values
- `test_returns_first_result_when_only_one_can_succeed` — only tables[0] seeded; others time out; result["val"] == "winner"
- `test_runs_callables_in_parallel` — threading.Timer delays insertion by 2s; wall-clock < 5s proves concurrency
- `test_single_expectation_returns_its_result` — single-element list returns the item directly
- `test_returns_result_type_not_wrapped` — asserts `type(result) is dict` (not a list)

### TestExpectAnyFailure
- `test_raises_aggregate_error_when_all_fail` — no items seeded; AggregateWaitTimeoutError with 3 errors
- `test_aggregate_error_is_catchable_as_wait_timeout_error` — AggregateWaitTimeoutError is-a WaitTimeoutError
- `test_non_wait_timeout_error_propagates_immediately` — RuntimeError from callable propagates directly
- `test_empty_list_raises_value_error` — `expect_any([])` raises ValueError

## Implementation Approach

Used `concurrent.futures.as_completed` to iterate over futures as they complete:

1. Raise `ValueError` for empty input immediately.
2. Submit all callables to a `ThreadPoolExecutor` (default: `len(expectations)` workers).
3. Iterate with `as_completed(future_to_idx)`:
   - First future with no exception: return `future.result()` immediately.
   - `WaitTimeoutError`: record in `errors` list; continue.
   - Any other exception: re-raise immediately.
4. After all futures complete with `WaitTimeoutError`: raise `AggregateWaitTimeoutError`.

## Commits

- `6c846b6` — test(parallel): add failing tests for expect_any (RED)
- `cb4fcda` — feat(parallel): implement expect_any — return first succeeding callable (GREEN)

## Deviations from Plan

One minor deviation: ruff formatter required a reformat of `tests/test_parallel_any.py` before
the GREEN commit (trailing whitespace / line-length normalization). The reformatted file was
included in the GREEN commit alongside `aws_expect/parallel.py`. No behavioral changes.

## TDD Gate Compliance

- RED gate commit exists: `6c846b6` — `test(parallel): add failing tests for expect_any`
- GREEN gate commit exists: `cb4fcda` — `feat(parallel): implement expect_any — return first succeeding callable`
- Both gates satisfied. No REFACTOR commit needed.

## Self-Check

- [x] `tests/test_parallel_any.py` has 9 test methods across 2 classes (min 9 required)
- [x] `uv run pytest tests/test_parallel_any.py -v` — all 9 pass
- [x] `uv run pytest tests/ -v` — 167 passed, 0 failures
- [x] `uv run ruff check .` exits 0
- [x] `uv run ruff format --check .` exits 0
- [x] `uv run ty check` exits 0
- [x] `aws_expect/parallel.py` contains no `NotImplementedError` for `expect_any`
- [x] RED commit exists: `6c846b6`
- [x] GREEN commit exists: `cb4fcda`
- [x] No modifications to STATE.md or ROADMAP.md
