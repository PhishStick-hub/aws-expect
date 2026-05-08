# Stack Research

**Domain:** Python AWS waiter library — predicate-based early termination & structured error messages
**Researched:** 2026-05-08
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.13+ | Runtime | Already mandated by project; `typing.Callable`, `repr()`, and exception hierarchies need only stdlib |
| boto3 | >=1.34 | AWS SDK (S3 resource, DynamoDB resource + client) | Already in tree; no new boto3 constructs needed — `stop_when` is custom polling logic, not a native waiter feature |

### New Standard Library Constructs (this milestone)

| Construct | Module | Purpose | When to Use |
|-----------|--------|---------|-------------|
| `Callable` | `typing` (or `collections.abc`) | Type annotation for `stop_when` parameter | Every `stop_when` signature — `Callable[[dict[str, Any]], bool]` |
| `TypeAlias` | `typing` | Optional readability alias: `StopPredicate = Callable[[dict[str, Any]], bool]` | Module-level type alias for self-documenting code; optional but recommended for S3 + DynamoDB modules |
| `repr()` | builtins | Render `expected`/`actual` dicts in exception `__str__` | Already used in existing timeout errors (e.g., `DynamoDBWaitTimeoutError`); standardize the pattern |
| `Exception` | builtins | Base class for `StopConditionMetError` | `StopConditionMetError` does NOT inherit `WaitTimeoutError` — it's a semantically distinct early-abort signal |

### Existing Shared Utilities (carried forward)

| Module | Function | Purpose | This Milestone Impact |
|--------|----------|---------|----------------------|
| `aws_expect._utils` | `_compute_delay(poll_interval)` | Clamp to min 1s, round up | No change — `stop_when` checks happen inside existing polling loops |
| `aws_expect._utils` | `_matches_entries()` | Shallow subset match | No change — `stop_when` predicate is independent of match logic |
| `aws_expect._utils` | `_deep_matches()` | Recursive subset match | No change |
| `time` | `monotonic()`, `sleep()` | Deadline-based polling | No change — `stop_when` checked per iteration before/after normal condition check |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Package manager | No new packages to add |
| ruff | Linter + formatter | No config changes needed |
| ty | Type checker | New `Callable` annotations must satisfy ty |
| pytest | Test runner | New test classes for `stop_when` predicates and `StopConditionMetError` |
| testcontainers[localstack] | Integration test AWS backend | Same `session`-scoped LocalStack container, `function`-scoped resources |

## Installation

```bash
# No new packages needed — this milestone is internal refactoring + extension.
# Existing dependencies are sufficient:
uv sync --all-groups
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `Callable[[dict[str, Any]], bool]` | `typing.Protocol` with `__call__` | If predicates need methods beyond `__call__` (not the case here — Protocol is overkill for a single-method callable) |
| Custom `StopConditionMetError(Exception)` | Inherit from `WaitTimeoutError` | Only if treating stop-condition as a timeout subtype makes semantic sense — **PROJECT.md Key Decisions explicitly reject this**: "Stop-condition triggers are distinct from timeout" |
| `repr()` in `__str__` | `pprint.pformat()` for multi-line output | If dicts are deeply nested and need pretty-printing — `repr()` is adequate for test-failure debugging; `pformat()` adds unnecessary complexity for this library's scope |
| Manual `__str__` building | `dataclasses` for auto-generated `__repr__` | `dataclasses` work well for data-carrier exceptions but change exception inheritance behavior (`__init__` generation) — manual `__str__` keeps control and consistency with existing pattern |
| `tenacity` / `backoff` libraries | Manual `time.sleep(min(delay, remaining))` | Retry libraries add dependency weight and hide polling semantics; manual `time` loop is transparent, testable, and already used throughout the codebase |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `tenacity` / `backoff` / `retry` | Adds dependency; obscures polling semantics; encourages "set and forget" that hides deadline checks | Existing `time.monotonic()` + `time.sleep()` pattern is explicit, testable, and sufficient |
| `inspect` module for predicate introspection | Over-engineering — `stop_when` callable is opaque by design; callers don't need runtime source inspection | Store the predicate callable on the exception as `.stop_condition` attribute for caller debugging |
| `contextvars` / `asyncio` | This library is synchronous (threading not asyncio); introducing async would require full rewrite | Stay synchronous — boto3 is synchronous, and the library targets integration tests that need simple `time.sleep` |
| `functools.partial` for predicate binding | Adds indirection; callers can use lambda/closures for the same effect | Let callers decide — the library accepts any `Callable[[dict], bool]` |
| `pprint.pformat()` for exception messages | Adds line noise in test output; `repr()` is compact and sufficient for dicts | `repr()` — consistent with existing `S3ContentWaitTimeoutError` and `DynamoDBWaitTimeoutError` patterns |

## Stack Patterns by Variant

**All polling methods in S3 + DynamoDB:**
- Add `stop_when: Callable[[dict[str, Any]], bool] | None = None` parameter
- Check predicate after fetching state but before checking the primary condition
- If predicate returns `True`, raise `StopConditionMetError(resource_context, last_state)` immediately (don't wait for deadline)
- Predicate receives the same state dict that the method would normally return on success

**StopConditionMetError shape:**
```python
class StopConditionMetError(Exception):
    """Raised when a stop_when predicate returns True during polling."""

    def __init__(
        self,
        service: str,             # "s3" or "dynamodb"
        resource_id: str,         # e.g. "s3://bucket/key" or "table:item_key"
        state: dict[str, Any],    # the state dict that triggered the predicate
        stop_condition: callable, # the predicate itself (for debugging)
    ) -> None: ...
```

**Richer timeout __str__ pattern (standardized):**
```python
def __str__(self) -> str:
    return (
        f"Timed out after {self.timeout}s waiting for {resource_id}\n\n"
        f"Expected:\n  {self.expected!r}\n\n"
        f"Actual (last seen):\n  {self.actual!r}"
    )
```
Already partially adopted in `DynamoDBWaitTimeoutError`, `S3ContentWaitTimeoutError`, `SQSWaitTimeoutError`.
This milestone standardizes it across ALL `WaitTimeoutError` subclasses.

**Service scope (this milestone):**
- S3: `S3ObjectExpectation.to_exist(entries=)`, `to_have_content` — both have polling loops
- DynamoDB: `DynamoDBItemExpectation.to_exist(entries=)`, `to_have_numeric_value_close_to` — polling loops
- Lambda + SQS: deferred to follow-up milestone (out of scope per PROJECT.md)

## Version Compatibility

| Component | Compatible With | Notes |
|-----------|-----------------|-------|
| Python 3.13 `Callable` | `collections.abc.Callable` (stdlib) | `typing.Callable` is deprecated in favor of `collections.abc.Callable` since 3.9, but both work; prefer whichever the project already uses |
| `from __future__ import annotations` | All modules | Already used throughout; continues to work for forward references |
| Existing exception hierarchy | `StopConditionMetError(Exception)` | No conflict — `StopConditionMetError` is a sibling of `WaitTimeoutError` under `Exception`, not a subclass |
| `AggregateWaitTimeoutError` | `expect_any` parallel waiter | No change — `stop_when` is per-callable, `AggregateWaitTimeoutError` aggregates `WaitTimeoutError` instances (which `StopConditionMetError` is NOT) |

## Sources

- Existing codebase (`aws_expect/exceptions.py`, `aws_expect/s3.py`, `aws_expect/dynamodb.py`) — verified polling loop patterns, exception hierarchy, `repr()` usage in `__str__` — HIGH confidence
- `.planning/PROJECT.md` Key Decisions — confirms `StopConditionMetError` is NOT a `WaitTimeoutError` subclass — HIGH confidence
- Python 3.13 stdlib docs (`typing.Callable`, `collections.abc.Callable`) — standard library only, no third-party deps needed — HIGH confidence

---
*Stack research for: v1.3.0 Smart Polling & Richer Errors*
*Researched: 2026-05-08*
