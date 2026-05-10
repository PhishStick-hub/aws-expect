# Project Research Summary

**Project:** aws-expect — `expect_all` / `expect_any` callable-with-args support
**Domain:** Python library enhancement — parallel execution primitives
**Researched:** 2026-05-10
**Confidence:** HIGH

## Executive Summary

This is a **surgical API enhancement** to an existing Python library — adding tuple-form callables `(fn, args, kwargs)` to `expect_all` and `expect_any` without changing architecture, dependencies, or error behavior. The feature removes `lambda:` boilerplate from call sites while preserving full backward compatibility.

The recommended approach is unanimous across all four researchers: define a `type ExpectationItem[T]` union alias in `aws_expect/parallel.py`, dispatch on `isinstance(exp, tuple)` at the `executor.submit()` call, and pass `(fn, *args, **kwargs)` directly to the thread pool. This requires **zero new dependencies**, **zero new modules**, and **zero changes** to S3, DynamoDB, Lambda, SQS, or exceptions code. The change is a single-file modification affecting only the submission boundary in `parallel.py`.

Key risks are minor and well-understood: users might pass malformed tuples (Python's unpacking raises clear errors), heterogeneous return types weaken `T` inference (document the constraint), and `ty` might produce a false positive on `executor.submit(fn, *args, **kwargs)` after type narrowing (suppress with a comment if needed). All three are documented, non-breaking, and detectable at development time. Overall execution risk is **low** — the feature follows well-established stdlib patterns (`concurrent.futures.submit`, `isinstance` narrowing, `Callable[..., T]`) with no novel abstractions.

## Key Findings

### Recommended Stack

No new dependencies. The implementation uses only Python standard library features already present in the codebase and target Python version (3.13+).

**Core technologies:**
- `concurrent.futures.ThreadPoolExecutor.submit(fn, *args, **kwargs)`: Existing integration point — already used in `parallel.py` for zero-arg callables; tuple form passes args/kwargs through this same call
- `isinstance(exp, tuple)`: Standard Python dispatch pattern for union types — `ty` narrows union branches correctly with zero casts or type:ignore needed
- `collections.abc.Callable[..., T]`: Expresses "any callable returning T" — correct constraint for tuple-form callables whose exact parameter signature is unknown at type-check time
- `typing.overload` (optional): Provides cleaner IDE hover info for pure-form sequences — not required for correctness but improves developer experience

**Explicitly NOT used:**
- `ParamSpec`: Designed for decorators that transform callable signatures, not for "call any callable with any args" — would add complexity without benefit
- `functools.partial`: Adds unnecessary indirection and obscures exception tracebacks — `executor.submit` accepts args directly
- New external libraries: Feature adds zero packages to `pyproject.toml`

### Expected Features

**Must have (table stakes):**
- Accept `(callable, args, kwargs)` tuples in `expect_all` — core feature; removes `lambda:` boilerplate
- Accept `(callable, args, kwargs)` tuples in `expect_any` — consistency across both parallel primitives
- Backward compatibility with `Callable[[], T]` — existing call sites must work unchanged
- Same error types and messages — `AggregateWaitTimeoutError` with `results` list identical to current
- Same return types (`list[T]` / `T`) — `T` inferred correctly from tuple-form callable return type
- `kwarg`s defaults to `{}` when tuple is `(fn, args)` — common zero-kwargs case shouldn't require explicit `{}`

**Should have (competitive):**
- `type ExpectationItem[T]` alias — makes function signatures readable; reusable if other parallel functions are added
- `@overload` signatures for `expect_all`/`expect_any` — cleaner IDE hover info for pure-form sequences (all-callable or all-tuple)
- Tuple-form example in docstrings — users need to discover the new capability

**Defer (v2+):**
- `TypeIs` guard function — plain `isinstance(exp, tuple)` already provides narrowing with `ty`; add `TypeIs` only if checker behavior proves insufficient
- Friendlier error messages for malformed tuples — Python's built-in unpack errors (`ValueError: not enough values to unpack`) are clear enough; revisit if user feedback says otherwise
- `AggregateWaitTimeoutError` distinguishing tuple vs callable source in failure messages — acceptable for v1; user knows what they passed

### Architecture Approach

No architectural change. The feature is a **signature and dispatch enhancement** within `aws_expect/parallel.py` — a single-file change. The modification point is exclusively at the `executor.submit()` call where futures are created; result collection, error aggregation, timeout handling, and return paths are completely unchanged.

**Major components (only one file modified):**
1. `parallel.py` (modified): Adds `ExpectationItem[T]` type alias, modifies `expect_all` and `expect_any` signatures to accept `Sequence[ExpectationItem[T]]`, adds `isinstance(exp, tuple)` dispatch in executor submission loop
2. `__init__.py` (unchanged): Public API exports remain identical — `expect_all` and `expect_any` are the same function names with widened signatures
3. All service modules (unchanged): S3, DynamoDB, Lambda, SQS expectation classes are still callables returning `T` — no changes needed

**Data flow:**
```
User code → expect_all/expect_any → for each exp:
  isinstance(exp, tuple)? 
    Yes → fn, args, kwargs = exp → executor.submit(fn, *args, **kwargs)
    No  → executor.submit(exp)    # zero-arg callable
→ Future collection → result/error aggregation (unchanged)
```

**Key patterns:**
- **Type alias for heterogeneous sequences**: `type ExpectationItem[T] = Callable[[], T] | tuple[Callable[..., T], tuple, dict[str, Any]]` — zero-cost, self-documenting, type-safe
- **isinstance dispatch**: Branches at submission time with full `ty` narrowing on both branches
- **Callable[..., T]**: Correctly expresses "any callable returning T" without over-constraining parameters

**Anti-patterns explicitly rejected:**
- `functools.partial` wrapping — adds indirection and obscures tracebacks
- New modules or classes — over-abstraction for a two-case union
- Runtime tuple structure validation — Python's built-in unpack errors are clear enough
- Separate `expect_all_with_args` function — fragments the API unnecessarily

### Critical Pitfalls

1. **TypeVar confusion with heterogeneous return types** — When `expect_all` contains expectations returning different types (e.g., DynamoDB dict and S3 metadata), `T` resolves to the common supertype (`object`), weakening inference. **Prevention:** Document that all expectations in one call should share a meaningful common return type. Users with truly heterogeneous types should split into separate `expect_all` calls grouped by return type. This is a type-level concern, not a runtime bug.

2. **Unpacking non-3-tuples** — Users may pass `(fn, args)` (2-tuple, missing kwargs) thinking it works. `ValueError: not enough values to unpack` is raised at runtime with a clear traceback. **Prevention:** Do NOT add explicit len() validation — Python's built-in error is clear enough. Accept as a declarative footgun; the traceback pinpoints `fn, args, kwargs = exp` in `parallel.py`.

3. **Mutable default kwargs in shared tuples** — A user reusing the same `dict` across multiple expectation tuples risks stale values if the dict is mutated. **Prevention:** Document that args/kwargs are consumed at submission time. In practice, `executor.submit` unpacks immediately so risk is low, but `lambda`-wrapped async scenarios could capture stale references.

4. **`ty` false positive on `executor.submit` with unpacked args** — After `isinstance` narrowing, `ty` might report `invalid-argument-type` on `executor.submit(fn, *args, **kwargs)` because `fn` is `Callable[..., T]`. **Prevention:** Test with `ty check` before committing. If false positive occurs, `executor.submit`'s type stubs accept `Callable[..., Any]` with `*args: Any, **kwargs: Any` — suppress with `# type: ignore[arg-type]` and a comment if needed.

5. **IDE hover confusion with union type** — `Sequence[ExpectationItem[T]]` expands to the full union in tooltips, less readable than the simple `Sequence[Callable[[], T]]`. **Prevention:** Add `@overload` signatures presenting pure-form signatures first (all-callable, all-tuple) with the union as the implementation fallback.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Core Dispatch Implementation
**Rationale:** The runtime dispatch is the foundational change — everything else (type narrowing, tests, docs) depends on having the dispatch loop working first. This is a direct, minimal change with immediate user value. All researchers agree `isinstance(exp, tuple)` with `executor.submit(fn, *args, **kwargs)` is the correct pattern.

**Delivers:**
- `type ExpectationItem[T]` alias in `parallel.py`
- Modified `expect_all` signature accepting `Sequence[ExpectationItem[T]]`
- Modified `expect_any` signature accepting `Sequence[ExpectationItem[T]]`
- Runtime dispatch in both submit loops
- Basic success-path tests for both functions with tuple-form expectations
- Empty sequence tests (should still return `[]` for `expect_all`, raise `ValueError` for `expect_any`)

**Addresses:** All table-stakes features (tuple acceptance, backward compat, same return types, same error handling)

**Avoids:** All three critical pitfalls — no `functools.partial`, no runtime validation, no new modules

### Phase 2: Type Polish, Edge Testing, and Docs
**Rationale:** The core feature works after Phase 1. Phase 2 improves the developer experience (IDE hover, docstring examples) and validates edge cases (mixed sequences, timeout behavior parity, error propagation) without blocking the MVP.

**Delivers:**
- `@overload` signatures for `expect_all` and `expect_any` (cleaner IDE hovers)
- Tests for mixed sequences: `[fn1, (fn2, args, kwargs), fn3]` in the same call
- Tests comparing tuple-form vs lambda-form behavior parity (identical results, errors, timing)
- Edge-case tests: timeout ordering with tuple-form entries, exception propagation, type checker verification (`ty check`)
- Docstring updates with tuple-form usage examples
- `# type: ignore[arg-type]` suppression if `ty` false-positives on `executor.submit`

**Addresses:** All should-have features (`@overload`, docstring examples, mixed-sequence testing)

**Avoids:** Pitfall #4 (ty false positive handled), Pitfall #5 (IDE hover improved), Pitfall #2 from moderate list (backward compat for empty sequences verified)

### Phase Ordering Rationale

- **Phase 1 first** because the runtime dispatch is the minimal viable change — it delivers user value immediately and is a dependency for all subsequent work
- **Phase 2 second** because polish items depend on Phase 1 implementation being stable — no benefit to `@overload` or edge-case testing before the baseline works
- This two-phase split also maps to "MVP then polish" — Phase 1 can ship independently, Phase 2 improves quality without risk of regressions
- Grouping by dependency, not by component: the change is so localized that splitting by "component" would produce artificial phase boundaries

### Research Flags

Phases needing deeper research during planning: **None — all phases use well-documented stdlib patterns.** The feature is well-understood, with all four researchers converging on the same approach using official Python/ty docs. No specialized domain knowledge or external API research is required.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Core Dispatch):** `isinstance` dispatch, `executor.submit` with args — all standard Python patterns with official docs and existing codebase examples
- **Phase 2 (Type Polish & Tests):** `@overload` decorators, pytest parametrization — well-established patterns with existing codebase conventions

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies; all stdlib features confirmed against Python CPython docs and existing codebase usage |
| Features | HIGH | Table stakes (tuple acceptance, backward compat) clearly defined; anti-features (no `functools.partial`, no separate function) agreed by all researchers; differentiators (type alias, @overload) are optional polish |
| Architecture | HIGH | No architectural change — single-file, single-function-boundary modification; all researchers agree on `isinstance` dispatch at `executor.submit()`; component boundaries clearly mapped and unchanged |
| Pitfalls | HIGH | Risks are minor (type inference edge case, unpack errors, possible `ty` false positive); all are detectable at development time; no rewriting or restructure risks identified |
| Integration | HIGH | No cross-module dependencies; error paths, return types, and test fixtures are unchanged; only `parallel.py` modified |

**Overall confidence:** HIGH — the feature is a surgical enhancement using well-established patterns with complete alignment across all four researchers. No novel abstractions, no new dependencies, no architectural changes.

### Gaps to Address

- **ty behavior with `executor.submit(fn, *args, **kwargs)` after isinstance narrowing**: Not verifiable without writing and type-checking the actual code. Handle during Phase 1 implementation — test with `ty check` and suppress with `# type: ignore[arg-type]` if false positive occurs
- **kwargs default behavior**: Whether to support `(fn, args)` 2-tuples (with kwargs defaulting to `{}`) or require 3-tuples. STACK.md recommends default-`{}` for ergonomics; validate during Phase 1 implementation that the unpacking handles this cleanly
- **IDE hover quality with union type**: Whether `@overload` is needed for acceptable IDE experience can only be validated by inspecting hover output in an actual editor. Defer decision to Phase 2

## Sources

### Primary (HIGH confidence)
- Python CPython docs (`/python/cpython`): `concurrent.futures.ThreadPoolExecutor.submit` API — confirmed `submit(fn, *args, **kwargs)` since Python 3.2; `Callable[..., T]` semantics confirmed as "any callable returning T"
- ty docs (`/websites/astral_sh_ty`): `isinstance` narrowing on union types confirmed; `@overload` support confirmed in 0.0.20; `TypeIs` guard available but not required
- Existing codebase (`aws_expect/parallel.py`, `tests/test_parallel_any.py`): Current `ThreadPoolExecutor` usage pattern, test fixtures, and error aggregation serve as implementation template

### Secondary (MEDIUM confidence)
- Python typing spec: TypeVar resolution across union elements — common supertype inference behavior documented (relevant to Pitfall #1)
- Python `isinstance` and `callable` builtins: dispatch patterns well-documented in official Python docs

### Tertiary (LOW confidence)
- None — all sources are official docs or existing codebase with high confidence

---
*Research completed: 2026-05-10*
*Ready for roadmap: yes*
