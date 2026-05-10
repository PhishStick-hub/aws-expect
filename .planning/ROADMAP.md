# Roadmap: aws-expect

## Overview

Milestone v1.4.0 enhances `expect_all` and `expect_any` to accept `(callable, args, kwargs)` tuples alongside plain `Callable[[], T]` — removing `lambda:` boilerplate from call sites. The change is a surgical single-file enhancement to `aws_expect/parallel.py` with zero new dependencies and full backward compatibility.

## Milestones

- 📋 **v1.4.0 Lambda Args** — Phases 10-11 (in progress)

## Phases

- [ ] **Phase 10: Core Dispatch Implementation** — Tuple acceptance, type alias, and basic success-path behavior
- [ ] **Phase 11: Type Polish, Edge Testing, Docs** — Mixed sequences, @overload signatures, and docstring examples

## Phase Details

### Phase 10: Core Dispatch Implementation
**Goal**: Users can pass `(callable, args, kwargs)` tuples to both `expect_all` and `expect_any`, with the callable invoked with `*args, **kwargs` in the thread pool.
**Depends on**: Nothing (first phase of v1.4.0 milestone)
**Requirements**: PAR-01, PAR-02, PAR-04
**Success Criteria** (what must be TRUE):
  1. User can pass `(fn, args, kwargs)` tuples to `expect_all` — the callable is invoked with `*args, **kwargs` and results are returned in input order
  2. User can pass `(fn, args, kwargs)` tuples to `expect_any` — the first success is returned; all-failure raises `AggregateWaitTimeoutError` with `results` list containing `None` for failures
  3. Empty sequences behave identically to current behavior: `expect_all([])` returns `[]`, `expect_any([])` raises `ValueError`
  4. `ExpectationItem[T]` type alias is defined in `parallel.py` and used in `expect_all` / `expect_any` function signatures
**Plans**: 2 plans

Plans:
- [ ] 10-01-PLAN.md — Add `ExpectationItem[T]` type alias, `_submit_expectation` helper, and update `expect_all`/`expect_any` dispatch
- [ ] 10-02-PLAN.md — Tuple-form tests for `expect_all` and `expect_any`, full suite verification

### Phase 11: Type Polish, Edge Testing, Docs
**Goal**: Users get clean IDE hover information, mixed sequences of tuples and callables work seamlessly, and docstrings show tuple-form usage examples.
**Depends on**: Phase 10
**Requirements**: PAR-03, PAR-05, PAR-06
**Success Criteria** (what must be TRUE):
  1. User can mix plain `Callable[[], T]` and `(fn, args, kwargs)` tuples in the same `expect_all` / `expect_any` call — both forms work correctly together in any order
  2. IDE hover shows separate, readable overloaded signatures for all-callable and all-tuple sequences via `@overload` decorators
  3. Docstrings for both `expect_all` and `expect_any` include tuple-form usage examples alongside existing lambda-form examples
  4. Timeout and error handling behave identically for tuple-form and lambda-form expectations — same `AggregateWaitTimeoutError` structure and exception propagation
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 10 → 11

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 10. Core Dispatch | v1.4.0 | 0/2 | Planned | - |
| 11. Type Polish & Docs | v1.4.0 | 0/TBD | Not started | - |
