# Phase 10: Core Dispatch Implementation — RESEARCH

**Research date:** 2026-05-11
**Phase:** 10 — Core Dispatch Implementation
**Scope:** Tuple-form callable support in `expect_all` / `expect_any`

---

## 1. Existing Codebase Analysis

### 1.1 Target File: `aws_expect/parallel.py` (155 lines)

Two public functions, both accepting `Sequence[Callable[[], T]]`:

| Function | Lines | Dispatch Point | Error Handling |
|----------|-------|---------------|----------------|
| `expect_all` | 12–84 | Line 62: `executor.submit(expectation)` | Collects results, raises `AggregateWaitTimeoutError` with `results` list |
| `expect_any` | 87–155 | Line 139: `executor.submit(exp)` | Returns first success, raises `AggregateWaitTimeoutError` on all-fail |

Both use `ThreadPoolExecutor`, share `T = TypeVar("T")` at module level (line 9), and import `from __future__ import annotations`.

### 1.2 Type Narrowing Concern

The existing code does:
```python
futures.append(executor.submit(expectation))
```
where `expectation: Callable[[], T]`. If we change the signature to `ExpectationItem[T]` (union), then `executor.submit(expectation)` where `expectation` could be a tuple will trigger a `ty` false positive because `ty` doesn't narrow unions through `isinstance()` checks automatically.

**Resolved by D-03:** Extract a private `_dispatch_expectation()` helper that performs `isinstance` narrowing internally and returns `Future[T]`. This keeps type suppressions out of the main function bodies.

### 1.3 `executor.submit` API

`ThreadPoolExecutor.submit(fn, *args, **kwargs)` accepts positional and keyword args directly. After isinstance detection of a 3-tuple `(fn, args, kwargs)`, dispatch is:
```python
executor.submit(fn, *args, **kwargs)
```

This is the standard Python stdlib API — no surprises, no version-specific behavior.

---

## 2. Implementation Strategy

### 2.1 Type Alias Location

Add after line 9 (`T = TypeVar("T")`) in `parallel.py`:
```python
ExpectationItem: TypeAlias = Callable[[], T] | tuple[Callable[..., T], tuple, dict[str, Any]]
```
Using `TypeAlias` (Python 3.12+) for explicit alias semantics. Inline definition (not exported via `__init__.py`).

### 2.2 Private Dispatch Helper

```python
def _submit_expectation(
    executor: ThreadPoolExecutor,
    expectation: ExpectationItem[T],
) -> Future[T]:
    if isinstance(expectation, tuple):
        fn, args, kwargs = expectation
        return executor.submit(fn, *args, **kwargs)
    return executor.submit(expectation)
```

The `isinstance(expectation, tuple)` check narrows the type within the `if` branch — `ty` correctly handles this in function-local scope. The helper returns `Future[T]` in both branches, keeping the caller type-clean.

### 2.3 Function Signature Changes

**`expect_all` (line 13):**
```python
# Before:
def expect_all(expectations: Sequence[Callable[[], T]], ...) -> list[T]:
# After:
def expect_all(expectations: Sequence[ExpectationItem[T]], ...) -> list[T]:
```

**`expect_any` (line 88):**
```python
# Before:
def expect_any(expectations: Sequence[Callable[[], T]], ...) -> T:
# After:
def expect_any(expectations: Sequence[ExpectationItem[T]], ...) -> T:
```

### 2.4 Dispatch Loop Change

In both functions, replace:
```python
futures.append(executor.submit(expectation))
```
with:
```python
futures.append(_submit_expectation(executor, expectation))
```

Same change at line 62 (expect_all) and line 139 (expect_any).

---

## 3. Test Strategy

### 3.1 Existing Test Patterns

Tests use:
- `dynamodb_tables` fixture (list of 3 tables)
- `dynamodb_table` fixture (single table)
- `put_item()` to seed data
- `lambda:` closures wrapping expectation calls
- `threading.Timer` for delayed creation (parallelism tests)
- `pytest.raises` for error paths
- Short timeouts (2-10s)

### 3.2 New Test Cases Needed

**For `expect_all`:**
1. Single tuple with args succeeds (PK + value from arg)
2. Multiple tuples succeed in parallel (order preserved)
3. Tuple mixed with plain callable (backward compat)
4. Empty tuple args `(fn, (), {})` works
5. Tuple with kwargs `(fn, (), {"key": "pk"})` works
6. Tuple timeouts → `AggregateWaitTimeoutError` with `None` at that index

**For `expect_any`:**
1. Single tuple succeeds (returns first's result)
2. Multiple tuples, first succeeds
3. Empty tuple args works
4. Tuple with kwargs works
5. All tuples timeout → `AggregateWaitTimeoutError`

**Edge cases (deferred to Phase 11 or future):**
- Malformed 2-tuple — Python `ValueError` on unpack (acceptable per Future Requirements)
- `(fn, "not-a-tuple", {})` — `*args` on string iterates characters (user error, acceptable)

---

## 4. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `ty` false positive on tuple unpack | Low | Low | Private helper isolates narrowing; if `ty` still complains, `# type: ignore[arg-type]` on helper's tuple branch |
| `executor.submit(fn, *args, **kwargs)` type error | Low | Low | `fn: Callable[..., T]` is intentionally wide — any callable returning T is valid |
| Backward compat break | None | — | Plain callables still dispatch to same `executor.submit(callable)` path |
| Empty sequence break | None | — | Early-return for empty lists happens before dispatch loop |

---

## 5. Verification Strategy

**Dimension 8 (Nyquist-aligned):**

1. **Unit-level:** `_submit_expectation` returns `Future[T]` for both tuple and callable inputs
2. **Integration:** `expect_all` with tuples returns results in input order
3. **Integration:** `expect_any` with tuples returns first success
4. **Error:** Tuple timeouts produce `AggregateWaitTimeoutError` with correct `results` list
5. **Type:** `ty check` passes without suppressions on `parallel.py`
6. **Backward compat:** All existing tests pass unchanged (no lambda-form tests modified)

---

## 6. Validation Architecture

### Nyquist Sampling Plan (Dimension 8)

| Gap ID | What is sampled | How verified |
|--------|----------------|--------------|
| V-10-01 | `_submit_expectation` returns correct `Future[T]` for both branches | Unit test: submit plain callable and tuple, verify `.result()` |
| V-10-02 | `expect_all` tuple results preserve input order | Integration test: 3 tuples with distinct args, verify result order |
| V-10-03 | `expect_any` returns first tuple result | Integration test: 1 fast + 2 slow tuples, verify fast result wins |
| V-10-04 | Tuple timeout → `AggregateWaitTimeoutError` with `None` at correct index | Integration test: timeout tuples, verify `err.results[i] is None` |
| V-10-05 | `ty check` passes on `parallel.py` | `uv run ty check` exit code 0 |
| V-10-06 | All existing tests pass with zero modifications | `uv run pytest tests/test_expect_all.py tests/test_parallel_any.py -v` exit code 0 |

### Success Gates

| Gate | Condition | Command |
|------|-----------|---------|
| G1 | `ExpectationItem[T]` defined in `parallel.py` | `grep -c "ExpectationItem" aws_expect/parallel.py` ≥ 1 |
| G2 | `_submit_expectation` helper exists | `grep -c "_submit_expectation" aws_expect/parallel.py` ≥ 1 |
| G3 | Both functions use helper | `grep -c "_submit_expectation" aws_expect/parallel.py` ≥ 3 (def + 2 calls) |
| G4 | `expect_all` returns tuple results in order | pytest test |
| G5 | `expect_any` returns first tuple success | pytest test |
| G6 | `ty check` clean | `uv run ty check` exit 0 |
| G7 | `ruff check` clean | `uv run ruff check aws_expect/parallel.py` exit 0 |
