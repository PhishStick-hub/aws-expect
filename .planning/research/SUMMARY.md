# Project Research Summary

**Project:** aws-expect — Python AWS waiter library
**Domain:** Declarative AWS waiter library with stop-condition predicates and richer timeout error messages
**Researched:** 2026-05-08
**Confidence:** HIGH

## Executive Summary

`aws-expect` is a Python library providing declarative waiters for AWS services (currently S3 and DynamoDB). This milestone adds **smart polling** — a `stop_when` predicate parameter that aborts polling early when a resource enters a terminal failure state — and **richer timeout error messages** that make failures self-documenting with structured `expected`/`actual` output.

The recommended approach is **additive and backward-compatible**: inject `stop_when` as a keyword-only `Callable[[dict[str, Any]], bool]` parameter into each existing polling loop, raise a new `StopConditionMetError` (which is deliberately NOT a subclass of `WaitTimeoutError`) when the predicate returns `True`, and standardize all `WaitTimeoutError.__str__` implementations around a shared `expected`/`actual` format. No new dependencies are required — the entire feature set uses only Python stdlib constructs (`Callable`, `repr()`, `time`).

The key risks are: (1) the design tension between checking `stop_when` before vs. after the main success condition — resolved here in favor of **main condition wins** (if the resource already meets the success condition, return immediately without checking `stop_when`); (2) exceptions raised inside user predicates being silently swallowed (mitigated by wrapping them in a dedicated `StopConditionError`); and (3) callers catching `WaitTimeoutError` and missing `StopConditionMetError` because it inherits from `Exception` directly — mitigated by prominent documentation and README examples.

## Key Findings

### Recommended Stack

This milestone requires **zero new dependencies**. All features build on the existing Python 3.13+ / boto3 stack with standard library constructs:

**Core technologies:**
- **Python 3.13 stdlib** — `Callable` for type annotations, `repr()` for exception `__str__`, `time.monotonic()`/`sleep()` for polling — no third-party polling libraries needed.
- **boto3 >=1.34** — existing AWS SDK integration; `stop_when` adds custom polling logic, not native waiter features.
- **`StopConditionMetError(Exception)`** — new exception deliberately inheriting from `Exception` directly, NOT `WaitTimeoutError`, per PROJECT.md Key Decisions. This ensures semantic separation between "it timed out" and "it can never succeed."

**What NOT to use:**
- No `tenacity` / `backoff` / `retry` — adds unnecessary dependency weight and obscures polling semantics.
- No `TypedDict` for state dicts (deferred) — plain `dict[str, Any]` with documented keys avoids 10+ TypedDict classes.
- No asyncio — library stays synchronous.
- No JMESPath acceptors — callables are Pythonic and zero-dependency.

### Expected Features

**Must have (table stakes):**
- **`stop_when` on all S3 + DynamoDB polling methods** — callers need to abort early when resources enter terminal failure states (e.g., S3 object marked FAILED, DynamoDB item deleted mid-wait).
- **`StopConditionMetError` distinct from `WaitTimeoutError`** — callers must be able to distinguish "waited and it didn't work" from "it can never work." Already decided in PROJECT.md: not a `WaitTimeoutError` subclass.
- **Structured `expected`/`actual` in ALL `WaitTimeoutError.__str__`** — every timeout error must make the failure self-documenting. Currently some exceptions (e.g., `S3WaitTimeoutError` with no entries) show only the resource path, not *why* it timed out.
- **Stop-condition fired before next sleep, not after** — predicate detection raises immediately; no wasted `time.sleep()` after the terminal state is already known.

**Should have (competitive):**
- **Predicate return value carried in `StopConditionMetError`** — allows predicates to return descriptive reason strings (e.g., `"Order 123 entered FAILED state: invalid format"`).
- **`StopConditionMetError` carries elapsed/total timeout** — debugging context: "fired at 12.3s out of 30s."
- **Error messages align with pytest assertion style** — "Expected:\n  ...\nActual:\n  ..." format reduces cognitive load for Python developers.
- **State dict documentation per method** — each method's docstring documents what keys the `stop_when` predicate receives.

**Defer (v2+):**
- **TypedDict state types** (`S3PollState`, `DynamoDBPollState`) — would require 10+ classes; maintenance burden outweighs benefit at current scale.
- **Composable `stop_when` with `&`/`|` operators** — users can compose conditions in their predicate; library-level composition adds complexity for a niche use case.
- **`stop_when` on native-boto3-waiter methods** (`to_exist` without `entries`, `to_not_exist`) — these delegate to boto3's blocking `wait()`; converting to custom loops solely for `stop_when` adds risk for minimal benefit.

### Architecture Approach

The architecture is **additive injection** into existing patterns. `stop_when` inserts into every custom polling loop at a single well-defined point, `StopConditionMetError` slots into the exception hierarchy as a sibling of `WaitTimeoutError` under `Exception`, and `expected`/`actual` fields are added as optional attributes to existing exception classes. Zero API breakage — all existing call sites remain valid.

**Major components:**
1. **`exceptions.py`** — `StopConditionMetError` (new, inherits `Exception`), `StopConditionError` (new, wraps predicate exceptions), enriched `S3WaitTimeoutError` and `LambdaWaitTimeoutError` (new `expected`/`actual` fields), shared `__str__` formatting helper.
2. **`s3.py`** — `stop_when: Callable[[dict[str, Any]], bool] | None = None` parameter on `_poll_for_entries`, `to_have_content`, `to_exist(entries=...)`. Native-waiter path (`to_exist` without entries) raises `TypeError` if `stop_when` is passed.
3. **`dynamodb.py`** — `stop_when` parameter on all 8 DynamoDBItem + DynamoDBTable polling methods. Per-item evaluation for `to_find_item`. Shallow-copied state dict (`dict(state)`) to prevent predicate mutations.
4. **`__init__.py` + `expect.py`** — Public API exports (no factory changes needed). `StopConditionMetError` added to `__all__`.
5. **Shared utilities** — `_format_error_with_expected_actual()` helper with truncation (50 items / 500 chars), `_safe_repr()` with try/except fallback.

### Critical Pitfalls

1. **Exceptions inside `stop_when` silently swallowed** — Do NOT catch exceptions around the predicate call. Let them propagate (wrapped in `StopConditionError` for context). A predicate that raises means the caller's logic is broken — silently continuing is worse than crashing.

2. **Predicate mutates shared state dict** — Python dicts are passed by reference. The polling loop must pass a shallow copy: `stop_when(dict(state))`. Without this, a predicate doing `state.pop(...)` corrupts subsequent poll iterations.

3. **`StopConditionMetError` not caught by `except WaitTimeoutError`** — By design, `StopConditionMetError` inherits `Exception` directly. Existing code with `except WaitTimeoutError` will miss it. Document prominently and show combined catch patterns: `except (WaitTimeoutError, StopConditionMetError)`.

4. **Predicate checked before main condition** — If the resource already meets the success condition, return success immediately — do NOT check `stop_when`. The ordering must be: fetch → check success → check `stop_when` → check timeout → sleep. **Main condition always wins.**

5. **`__str__` raises on broken `__repr__`** — If `expected` or `actual` contains an object with a broken `__repr__`, Python swallows the formatting error and falls back to `"<unprintable Exception>"`. Wrap `__str__` formatting in try/except with a safe fallback.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Exception Foundation
**Rationale:** Exception classes have zero runtime dependencies and everything else depends on them. Must exist before any `stop_when` integration. Standardizing `expected`/`actual` on S3 + Lambda timeout errors here enables consistent error handling when the polling implementations are modified.

**Delivers:**
- `StopConditionMetError` class (service, resource_id, stop_state, timeout, poll_count, elapsed)
- `StopConditionError` class (wraps predicate exceptions)
- `S3WaitTimeoutError` gains optional `expected`/`actual` fields + enhanced `__str__`
- `LambdaWaitTimeoutError` gains optional `expected`/`actual` fields + enhanced `__str__`
- Updated call sites in `s3.py` and `lambda_function.py` that construct these exceptions

**Addresses:** StopConditionMetError (table stake), structured expected/actual on S3WaitTimeoutError (table stake), predicate exception propagation (pitfall #1)

**Avoids:** Pitfalls #3 (document hierarchy in docstrings), #5 (standardize attribute naming), #6 (safe `__str__` with fallback)

### Phase 2: Smart Polling — `stop_when` Integration
**Rationale:** The headline feature. S3 is simpler (3 methods) and establishes the pattern. DynamoDB follows with 8 methods. This ordering lets the pattern stabilize before the more complex DynamoDB integration.

**Delivers:**
- `stop_when` on `S3ObjectExpectation._poll_for_entries`, `to_have_content`, `to_exist(entries=...)`
- `TypeError` raised when `stop_when` passed to native-waiter `to_exist` without entries
- `stop_when` on all `DynamoDBItemExpectation` polling methods (6 methods)
- `stop_when` on both `DynamoDBTableExpectation` polling methods (2 methods)
- Shallow-copied state dicts passed to predicates
- State dict keys documented in each method's docstring

**Addresses:** `stop_when` on all S3 + DynamoDB methods (table stake), stop before sleep (table stake), state dict design (differentiator)

**Avoids:** Pitfalls #1 (no try/except around predicate), #4 (dict copy), #7 (TypeError on native-waiter), #8 (main condition wins ordering)

### Phase 3: Error Message Enrichment
**Rationale:** After `stop_when` is stable, standardize all timeout error `__str__` formats. The shared formatting helper ensures consistency across S3, DynamoDB, Lambda, and SQS exceptions.

**Delivers:**
- Shared `_format_error_with_expected_actual()` helper with truncation (50 items, 500 chars)
- `_safe_repr()` utility with try/except fallback
- Consistent `__str__` format across ALL `WaitTimeoutError` subclasses
- `AggregateWaitTimeoutError` sub-exception details preserved

**Addresses:** Structured expected/actual in all errors (table stake), pytest-assertion-style format (differentiator)

**Avoids:** Pitfalls #5 (consistent naming), #6 (`__str__` fallback), #9 (truncation)

### Phase 4: Integration, Tests & Polish
**Rationale:** After all features are implemented, integrate exports, write comprehensive tests, update documentation, and run the full quality suite.

**Delivers:**
- `__init__.py` exports updated — `StopConditionMetError` in `__all__` and imports
- Full test suite: predicate success, predicate failure, predicate exception propagation, timeout with `stop_when`, "main condition wins" ordering, `StopConditionMetError` NOT caught by `except WaitTimeoutError`, truncation boundary tests
- Docstring updates with `stop_when` parameter docs and example predicates
- README updated with `stop_when` usage and combined catch patterns
- All quality checks passing (pytest, ty, ruff)

**Addresses:** Integration testing for all feature combinations

**Avoids:** Pitfall #3 (explicit test that `StopConditionMetError` is NOT caught by `except WaitTimeoutError`)

### Phase Ordering Rationale

- **Exceptions before polling** — `StopConditionMetError` must exist before any method raises it (hard dependency). Richer error fields on S3/Lambda exceptions are independent of `stop_when` and can be done in parallel in Phase 1.
- **S3 before DynamoDB** — S3 has 3 polling methods with simple state dicts (body `dict | None`). DynamoDB has 8 methods with more complex state shapes (items, counts, scan results). Pattern stabilizes in S3 first.
- **Error enrichment after `stop_when`** — The shared `__str__` helper should be designed after the full exception hierarchy is understood. Building it too early risks redesign when `stop_when` integration reveals new error-reporting needs.
- **Tests and exports last** — Integration tests validate the full feature set. Exports (`__all__`) shouldn't be finalized until all modules are complete.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Error Message Enrichment):** `AggregateWaitTimeoutError` has a fundamentally different structure (list of errors), making format standardization non-trivial. Needs design discussion on whether aggregate errors show per-error expected/actual or a summary format.
- **Phase 4 (Integration & Tests):** `to_find_item` with `stop_when` is the most complex case — per-item predicate evaluation in a paginated scan. Test scenarios need careful design for correctness vs. test speed.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Exception Foundation):** Well-documented existing patterns — new exception classes follow the exact template of existing ones. Adding optional fields is a straightforward Python pattern.
- **Phase 2 (Smart Polling):** All polling loops follow identical structure. The pattern is fully specified by research. Implementation is mechanical injection of 2 lines per loop.

## Cross-Cutting Concerns

### Conflict: Polling Loop Ordering (ARCHITECTURE vs. PITFALLS)

**Resolution: Main condition wins.** PITFALLS.md correctly identifies that `stop_when` is a secondary abort mechanism — if the resource already meets the success condition, the caller's primary goal is achieved. Checking `stop_when` before the success condition would cause spurious `StopConditionMetError` raises when the resource simultaneously meets both the success condition and the stop condition.

The correct ordering in every polling loop is:
```
fetch state → check success → check stop_when → check timeout → sleep
```

This is the opposite of what ARCHITECTURE.md currently shows (which has `stop_when` before the success check). The planning phase should reconcile ARCHITECTURE.md with this resolution.

### Scope Boundary: No `stop_when` on Native Waiter Methods

Methods using boto3's built-in `get_waiter().wait()` (`to_exist` without entries, `to_not_exist`) do NOT get `stop_when`. Converting them to custom loops solely for this feature would duplicate what boto3 already does well. Instead, raise `TypeError` when `stop_when` is passed with `entries=None` to catch the mistake early. This is a deliberate API asymmetry documented in method signatures.

### Attribute Naming: Keep Legacy Names As-Is

EXISTING public attributes like `entries` (DynamoDBWaitTimeoutError), `body` (SQSWaitTimeoutError), and `event` (SQSEventWaitTimeoutError) are NOT renamed. They remain as-is for backward compatibility. New exceptions or newly-added attributes use the standardized `expected`/`actual` naming. The `__str__` format is consistent regardless of the underlying attribute names.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Based on existing codebase — no new technologies introduced. All constructs verified against live code. |
| Features | HIGH | Competitor analysis (tenacity, polling2, boto3) validates feature gap. Use cases confirmed from real-world async-resource patterns. |
| Architecture | HIGH | Integration points verified against every polling loop in `s3.py` (226 lines) and `dynamodb.py` (470 lines). Exception hierarchy verified against `exceptions.py` (452 lines). |
| Pitfalls | HIGH | Six of nine pitfalls derived from direct analysis of existing codebase patterns. Remaining three from tenacity/boto3 behavior analysis. All prevention strategies concrete and testable. |

**Overall confidence:** HIGH — all research grounded in the actual codebase. No speculation or gaps in understanding the existing system.

### Gaps to Address

- **`AggregateWaitTimeoutError` format for richer errors:** The aggregate error wraps multiple `WaitTimeoutError` instances. Whether to display per-error expected/actual in its `__str__` (potentially verbose) or keep a summary format is undecided. Resolve during Phase 3 planning.
- **`to_find_item` per-item `stop_when` semantics:** When scanning a DynamoDB table with `to_find_item`, `stop_when` fires per-item. If the predicate fires for item 47 out of 500, should the scan continue or abort? Current design aborts — validate this during Phase 2 with concrete test scenarios.
- **`to_be_empty` / `to_be_not_empty` state dict shape:** These methods pass `{"item_count": int}` — no resource-level state. When `stop_when` fires for count methods, the error message must be meaningful despite the minimal state. Design this in Phase 2.
- **ARBITRAGE: ARCHITECTURE.md ordering conflict** — The architecture document shows `stop_when` before the success check, but this SUMMARY and PITFALLS resolve it the other way. Plan should update ARCHITECTURE.md to reflect the "main condition wins" ordering.

## Sources

### Primary (HIGH confidence)
- **Existing codebase** — `aws_expect/exceptions.py`, `aws_expect/s3.py`, `aws_expect/dynamodb.py`, `aws_expect/_utils.py` — verified polling loop patterns, exception hierarchy, attribute naming, and `repr()` usage in `__str__` methods.
- **`.planning/PROJECT.md`** — Key Decisions table confirming `StopConditionMetError` inherits `Exception`, not `WaitTimeoutError`. Project scope (S3 + DynamoDB only this milestone).
- **Python 3.13 stdlib** — `typing.Callable`, `collections.abc.Callable`, `repr()`, exception hierarchy behavior.

### Secondary (MEDIUM confidence)
- **[tenacity](https://github.com/jd/tenacity)** — `stop` callback pattern, exception propagation from predicates, `RetryCallState` for structured context. Validates design decisions (separate `stop` from `retry`, propagate predicate exceptions).
- **[polling2](https://github.com/ddmee/polling2)** — `check_success` callback pattern, `TimeoutException`/`MaxCallException` with `.values`/`.last`. Confirms that competitor libraries also lack stop-condition predicates (differentiator gap validated).

### Tertiary (LOW confidence — deferred scope)
- **boto3 waiter model JSON** — 3-state acceptors (success/failure/retry) via JMESPath. Confirms that native waiters cannot support per-iteration callbacks, justifying the scope boundary excluding native-waiter methods from `stop_when`.

---

*Research completed: 2026-05-08*
*Ready for roadmap: yes*
