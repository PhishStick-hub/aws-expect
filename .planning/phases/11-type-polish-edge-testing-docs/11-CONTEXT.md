# Phase 11: Type Polish, Edge Testing, Docs - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

After Phase 10 delivers tuple dispatch in `_submit_expectation`, Phase 11 ensures a clean developer experience — mixed sequences of tuples and callables work seamlessly, IDE hover info shows readable overloaded signatures, and docstrings include tuple-form usage examples.

**In scope:**
- `@overload` decorators on `expect_all` and `expect_any` for clean IDE hover (pure-callable + pure-tuple signatures)
- `ExpectationTuple[T]` type alias for readable overload signatures (internal — not exported)
- Mixed-sequence tests proving `Callable[[], T]` and `(fn, args, kwargs)` tuples interoperate in the same sequence
- Docstring updates adding tuple-form `Example::` blocks alongside existing lambda examples
- Full quality gate: `pytest`, `ty check`, `ruff check`, `ruff format`

**Out of scope:**
- Changes to `_submit_expectation` dispatch logic (Phase 10)
- New parallel.py logic for mixed sequences (assumed to work via per-item dispatch)
- `ExpectationItem[T]` or `ExpectationTuple[T]` public export (both internal)
- `TypeIs` guard, friendlier malformed-tuple errors, source-distinguished failure messages (Future Requirements)
- Any files other than `parallel.py` and test files
</domain>

<decisions>
## Implementation Decisions

### Overload Strategy
- **D-01:** Two `@overload` decorators per function — one for `Sequence[Callable[[], T]]` (pure-callable), one for `Sequence[ExpectationTuple[T]]` (pure-tuple). The undecorated implementation signature uses `Sequence[ExpectationItem[T]]`. Mixed sequences fall through to the implementation signature — still type-correct, just less specific hover. Matches ROADMAP's "all-callable and all-tuple sequences" language. Standard Python idiom.
- **D-02:** Define `ExpectationTuple[T] = tuple[Callable[..., T], tuple, dict[str, Any]]` type alias in `parallel.py` — placed alongside `ExpectationItem[T]` after `T = TypeVar("T")`. Used in overload signatures for clean 1-line hover. Internal only — not added to `__all__` in `__init__.py`.

### Mixed-Sequence Testing
- **D-03:** New test classes `TestExpectAllMixed` in `tests/test_expect_all.py` and `TestExpectAnyMixed` in `tests/test_parallel_any.py` — separate from Phase 10's `TestExpectAllTupleForm`/`TestExpectAnyTupleForm` classes. Clear phase boundary for test ownership.
- **D-04:** Five test scenarios per class (10 test methods total):
  1. Tuple-first ordering — sequence `[(fn, args, kwargs), callable]` — prove dispatch handles tuple at position 0
  2. Callable-first ordering — sequence `[callable, (fn, args, kwargs)]` — prove plain-callable path (D-04 from Phase 10) works when followed by tuple
  3. Interleaved — sequence `[tuple, callable, tuple]` — prove repeated type switching in dispatch loop
  4. Mixed with one failure — one item times out, others succeed — prove `AggregateWaitTimeoutError.results` has `None` at correct index regardless of item type
  5. All mixed all-failures — every item times out — prove error aggregation path handles mixed uniformly
- **D-05:** Assume mixed sequences work out of the box — `_submit_expectation` handles per-item dispatch via `isinstance` independently. No parallel.py logic changes for mixed dispatch. Verification comes from tests. If tests reveal a bug, the fix is minimal (in the iteration loop, not `_submit_expectation`).

### Docstring Updates
- **D-06:** Add one tuple-form `Example::` block to each function's docstring (`expect_all` and `expect_any`), placed after the existing lambda-form examples. Both forms visible — users see the upgrade path.
- **D-07:** One tuple example per function — the most common usage pattern. `expect_all` example shows `(fn, args, kwargs)` with both positional and keyword args. `expect_any` example shows simpler tuple usage. Users can infer variations.

### the agent's Discretion
None — all decisions were made by the user.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — PAR-03 (mixed sequences), PAR-05 (overload signatures), PAR-06 (docstring examples)
- `.planning/REQUIREMENTS.md` §Out of Scope — no new dependencies, no changes to exceptions.py/__init__.py/service modules, no `functools.partial`, no `ParamSpec`, no error type changes
- `.planning/REQUIREMENTS.md` §Future — `TypeIs` guard, friendlier malformed-tuple errors, source-distinguished failure messages all deferred

### Phase Definition
- `.planning/ROADMAP.md` — Phase 11 definition, goal: "Users get clean IDE hover information, mixed sequences of tuples and callables work seamlessly, and docstrings show tuple-form usage examples", 4 success criteria, depends on Phase 10

### Prior Phase Decisions
- `.planning/phases/10-core-dispatch-implementation/10-CONTEXT.md` — D-01 (always 3-tuple), D-02 (ExpectationItem internal only), D-03 (private dispatch helper `_submit_expectation`), D-04 (plain-callable path unchanged), D-05 (empty sequence behavior unchanged)
- `.planning/phases/10-core-dispatch-implementation/10-RESEARCH.md` — Implementation strategy, type narrowing approach, `executor.submit` API verification

### Project-Level
- `.planning/PROJECT.md` §Constraints — backward compatibility, full type annotations, LocalStack integration tests only, Python 3.13+
- `.planning/PROJECT.md` §Key Decisions — tuple-form support via `ExpectationItem[T]` union type, no separate functions
- `.planning/STATE.md` — known `ty` false positive on `executor.submit` (resolved by Phase 10 D-03 via `_submit_expectation`)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aws_expect/parallel.py` — Target file. `ExpectationItem[T]` type alias (line 11), `_submit_expectation` private helper (lines 16-25), both `expect_all` and `expect_any` already accept `Sequence[ExpectationItem[T]]` and dispatch via `_submit_expectation`.
- `aws_expect/__init__.py` — Imports `expect_all`, `expect_any` from `parallel` (line 32). No changes needed — `ExpectationItem` and `ExpectationTuple` are not exported.
- `tests/test_expect_all.py` — Phase 10 adds `TestExpectAllTupleForm` class. Phase 11 adds `TestExpectAllMixed`.
- `tests/test_parallel_any.py` — Phase 10 adds `TestExpectAnyTupleForm` class. Phase 11 adds `TestExpectAnyMixed`.
- `tests/conftest.py` — `dynamodb_tables` fixture (3 tables) available for parallel tests. Reusable for mixed-sequence tests.

### Established Patterns
- `@overload` pattern (Python stdlib `typing`): decorated overloads define specific call signatures, undecorated implementation uses broadest type. Modules using `from __future__ import annotations` need no special handling.
- TypeVar `T = TypeVar("T")` at module level in `parallel.py` — shared by both functions.
- Docstring format: Google-style with `Args:`, `Returns:`, `Raises:` sections, `Example::` blocks at end. Existing lambda examples use concrete DynamoDB item lookups.
- Test class pattern: `class TestExpectAll{Scenario}:` per scenario group, methods named `test_{what_it_proves}`, using `dynamodb_tables` fixture, `threading.Timer` for delayed creation.

### Integration Points
- `aws_expect/parallel.py:9` — After `T = TypeVar("T")` and `ExpectationItem[T]` (line 11): add `ExpectationTuple[T]` alias at line ~13 (D-02)
- `aws_expect/parallel.py:28` — Before `def expect_all`: add 2 `@overload` decorated signatures, then the existing undecorated `def expect_all` becomes the implementation (D-01)
- `aws_expect/parallel.py:103` — Before `def expect_any`: same overload pattern (D-01)
- `aws_expect/parallel.py:57-69` — `expect_all` docstring Example:: block: add tuple-form example after lambda example (D-06, D-07)
- `aws_expect/parallel.py:133-145` — `expect_any` docstring Example:: block: add tuple-form example after lambda example (D-06, D-07)
- `tests/test_expect_all.py` — Add `class TestExpectAllMixed:` after Phase 10's `TestExpectAllTupleForm` (D-03, D-04)
- `tests/test_parallel_any.py` — Add `class TestExpectAnyMixed:` after Phase 10's `TestExpectAnyTupleForm` (D-03, D-04)
- Imports in `parallel.py` — Add `overload` to `from typing import ...` (line 5)
</code_context>

<specifics>
## Specific Ideas

No specific references beyond the captured decisions. The implementation is straightforward:
1. Add `ExpectationTuple[T]` alias and `@overload` decorators to `parallel.py`
2. Update docstrings with tuple-form examples
3. Write mixed-sequence tests using existing DynamoDB fixtures
4. Run quality gates

`_submit_expectation` handles per-item dispatch — mixed sequences need zero additional logic in parallel.py.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 11-Type Polish, Edge Testing, Docs*
*Context gathered: 2026-05-11*
