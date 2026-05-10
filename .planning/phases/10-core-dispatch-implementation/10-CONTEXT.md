# Phase 10: Core Dispatch Implementation - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase adds tuple-form callable support to `expect_all` and `expect_any` — the runtime dispatch that detects `(fn, args, kwargs)` tuples via `isinstance(e, tuple)`, unpacks them, and invokes `fn(*args, **kwargs)` in the thread pool. Single-file change to `aws_expect/parallel.py` with zero new dependencies.

**In scope:**
- 3-tuple `(Callable[..., T], tuple, dict[str, Any])` dispatch in both `expect_all` and `expect_any`
- `ExpectationItem[T]` type alias defined in `parallel.py` (internal — not exported)
- Private dispatch helper function to avoid `# type: ignore[arg-type]` on `executor.submit`
- Backward compatibility: existing `Callable[[], T]` usage unchanged

**Out of scope:**
- 2-tuple `(fn, args)` support (explicitly rejected — always 3-tuple)
- Mixed sequences of tuples and plain callables (Phase 11)
- `@overload` signatures (Phase 11)
- Docstring updates (Phase 11)
- `ExpectationItem[T]` public export (internal only)
- Friendlier error messages for malformed tuples (Future Requirements)
- Any files other than `parallel.py`
</domain>

<decisions>
## Implementation Decisions

### Tuple Shape
- **D-01:** Always 3-tuple: `(fn, args, kwargs)`. Users pass `({},)` when no kwargs are needed. No 2-tuple `(fn, args)` shorthand. Simpler type, unambiguous, and matches the stated requirement specification exactly.

### Type Alias Visibility
- **D-02:** `ExpectationItem[T]` is internal to `parallel.py` — used in function signatures but NOT exported via `__init__.py` or `__all__`. Users don't annotate with it; overloaded signatures in Phase 11 provide IDE hover info.

### Type Narrowing
- **D-03:** Extract a private dispatch helper function instead of suppressing `ty` with `# type: ignore[arg-type]` on `executor.submit`. The helper takes an `ExpectationItem[T]`, performs `isinstance` narrowing internally, and returns a `Future[T]`. Clean type separation without suppressions.

### Existing Behavior Preservation
- **D-04:** When a received item is NOT a tuple (i.e., it's a plain `Callable[[], T]`), dispatch to `executor.submit(expectation)` exactly as today. Zero change to the plain-callable code path.
- **D-05:** Empty sequence behavior unchanged: `expect_all([])` returns `[]`, `expect_any([])` raises `ValueError`.

### the agent's Discretion
None — all decisions were made by the user.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — PAR-01 (`expect_all` tuple dispatch), PAR-02 (`expect_any` tuple dispatch), PAR-04 (`ExpectationItem[T]` type alias)
- `.planning/REQUIREMENTS.md` §Out of Scope — `functools.partial`, `ParamSpec`, separate functions, error type changes all excluded
- `.planning/REQUIREMENTS.md` §Future — `TypeIs` guard, friendlier malformed-tuple errors, source-distinguished failure messages all deferred

### Phase Definition
- `.planning/ROADMAP.md` — Phase 10 definition, goal: "Users can pass `(callable, args, kwargs)` tuples to both `expect_all` and `expect_any`, with the callable invoked with `*args, **kwargs` in the thread pool", 4 success criteria, depends on nothing

### Project-Level
- `.planning/PROJECT.md` §Constraints — backward compatibility, single-file change, zero new dependencies, full type annotations
- `.planning/PROJECT.md` §Key Decisions — tuple-form support via `ExpectationItem[T]` union type, no `functools.partial`, no separate functions, no `ParamSpec`
- `.planning/STATE.md` — known `ty` false positive on `executor.submit` (resolved via D-03: private dispatch helper)

### Prior Phase Decisions
No prior per-phase decisions apply (Phase 10 is the first phase of milestone v1.4.0, operating on a different module than prior phases).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aws_expect/parallel.py:1-155` — Target file. Two functions (`expect_all`, `expect_any`), both using `ThreadPoolExecutor` + `executor.submit(expectation)`. Type var `T = TypeVar("T")` already defined at module level.
- `aws_expect/exceptions.py` — `AggregateWaitTimeoutError`, `WaitTimeoutError` — no changes needed, just re-imported.

### Established Patterns
- Dispatch: `executor.submit(expectation)` at `parallel.py:62` (`expect_all`) and `parallel.py:139` (`expect_any`)
- Result collection: `expect_all` waits for all futures via `executor.__exit__`, then collects results in order-preserving list
- First-success: `expect_any` uses `as_completed(futures)` and returns on first non-error result
- Type annotations: `Sequence[Callable[[], T]]`, `list[Future[T]]`, `list[T | None]`
- Imports: `from __future__ import annotations`, `TypeVar`, `Callable`, `Sequence` from `collections.abc`

### Integration Points
- `aws_expect/parallel.py:6` — Add `ExpectationItem[T]` type alias after the `T` TypeVar definition (line 9)
- `aws_expect/parallel.py:12` — `expect_all` signature: change `Sequence[Callable[[], T]]` to `Sequence[ExpectationItem[T]]`
- `aws_expect/parallel.py:61-62` — `expect_all` dispatch loop: add `isinstance(expectation, tuple)` branch calling the private helper vs. plain `executor.submit(expectation)`
- `aws_expect/parallel.py:87` — `expect_any` signature: same type change
- `aws_expect/parallel.py:139` — `expect_any` dispatch: same isinstance branching
- `aws_expect/__init__.py:32` — No change (`ExpectationItem` not exported)
- Tests: `tests/test_expect_all.py`, `tests/test_parallel_any.py` — add tuple-form test cases
</code_context>

<specifics>
## Specific Ideas

No specific references beyond the captured decisions. The implementation is a straightforward isinstance-based dispatch in the existing polling loop.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 10-Core Dispatch Implementation*
*Context gathered: 2026-05-10*
