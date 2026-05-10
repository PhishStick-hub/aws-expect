# Domain Pitfalls: expect_all/expect_any Callable-with-Args

**Domain:** Python library enhancement — parallel execution primitives
**Researched:** 2026-05-10

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: TypeVar Confusion with Heterogeneous Return Types

**What goes wrong:** When `expect_all` receives a mix of expectations whose callables return different types (e.g., `dict[str, Any]` from DynamoDB and `HeadObjectOutputTypeDef` from S3), the TypeVar `T` resolves to the common supertype (`object` or `dict[str, Any] | HeadObjectOutputTypeDef`). Users expecting per-element type inference get a less specific type than anticipated.

**Why it happens:** Python's type system resolves a single TypeVar across all elements of a homogeneous sequence. The union element type (`ExpectationItem[T]`) shares one `T` across all elements.

**Consequences:** The return type `list[T]` becomes `list[object]` instead of per-element types. Users who rely on precise return type inference for individual results will need explicit type assertions or separate calls.

**Prevention:** Document that all expectations in a single `expect_all` call should share a meaningful common return type. Users with truly heterogeneous types should either:
1. Accept `list[object]` and cast individual results, or
2. Split into multiple `expect_all` calls grouped by return type.

**Detection:** This is a type-level concern, not a runtime bug. `ty` will flag if downstream code tries to access type-specific attributes on results without narrowing. The type checker output is the detection mechanism.

### Pitfall 2: Unpacking Non-3-Tuples

**What goes wrong:** A user passes `(fn, args)` (2-tuple, missing kwargs) or `(fn,)` (1-tuple) thinking it will work.

**Why it happens:** The type annotation `tuple[Callable[..., T], tuple, dict[str, Any]]` says "exactly 3 elements," but Python type checkers don't enforce tuple length at call sites for dynamically-constructed tuples.

**Consequences:** `ValueError: not enough values to unpack (expected 3, got 2)` at runtime. Only happens when the tuple is actually iterated/unpacked in the dispatch loop.

**Prevention:** Two options:
1. **Don't validate (recommended):** Let Python's unpacking raise naturally. The error message is clear.
2. **Validate in dispatch loop:** Check `len(exp) == 3` before unpacking and raise a friendlier `TypeError`. Adds code but improves error message.

**Detection:** Runtime error with clear traceback pointing to the `fn, args, kwargs = exp` line in `parallel.py`. No silent failure possible.

### Pitfall 3: Mutable Default `kwargs` in Shared Tuples

**What goes wrong:** A user constructs a tuple with a shared `dict` for kwargs, then modifies it between `expect_all` calls:
```python
shared_kwargs = {"timeout": 30}
expect_all([(fn1, (), shared_kwargs), (fn2, (), shared_kwargs)])
shared_kwargs["timeout"] = 60  # Mutates the dict inside the tuple!
```

**Why it happens:** `dict` is mutable. If the user reuses the same dict object across expectations or across calls, later mutations affect earlier-constructed tuples.

**Consequences:** Unexpected behavior if the kwargs dict is modified after submission but before the executor processes it (though in practice, `executor.submit` doesn't hold a reference to the dict after callable invocation).

**Prevention:** Document that args/kwargs are consumed at submission time. The actual risk is low because `executor.submit` unpacks immediately — the callable is invoked with the args/kwargs as they exist at submission time. However, for async expectations (lambda wrapping), the lambda captures the reference, which could be stale.

**Detection:** Hard to detect without explicit testing. Mitigation: tests should verify that kwargs are captured at submission time, not at callable invocation time.

## Moderate Pitfalls

### Pitfall 1: IDE Confusion with Union Type Hover Information

**What goes wrong:** When hovering over `expect_all` in an IDE, the type hint shows `Sequence[ExpectationItem[T]]` which expands to the full union — less readable than the simple `Sequence[Callable[[], T]]`.

**Prevention:** Add `@overload` signatures that present the two pure-form signatures first, with the implementation signature as the fallback. This gives IDEs cleaner hover information for the common case (all-callable or all-tuple sequences).

### Pitfall 2: `ty` False Positive on `executor.submit` with Unpacked Args

**What goes wrong:** After `isinstance(exp, tuple)` narrowing, `ty` might report `invalid-argument-type` on `executor.submit(fn, *args, **kwargs)` because `fn` is `Callable[..., T]` and `executor.submit` expects a specific callable type.

**Prevention:** `executor.submit`'s type stub accepts `Callable[..., Any]` with `*args: Any, **kwargs: Any`. This should pass. If `ty` complains, verify the stub definition or use `# type: ignore[arg-type]` with a comment.

### Pitfall 3: Test Fixture Reuse for Tuple-Form Tests

**What goes wrong:** Copying lambda-based test patterns directly without verifying that tuple-form expectations behave identically in edge cases (timeout ordering, exception propagation, result ordering).

**Prevention:** Add explicit tests that compare tuple-form vs lambda-form behavior for the same expectation — they should produce identical results, errors, and timing behavior.

## Minor Pitfalls

### Pitfall 1: Forgetting to Update `__all__` for Exported Types

**What goes wrong:** Adding `ExpectationItem` as a public type alias but forgetting to export it.

**Prevention:** `ExpectationItem` is an implementation detail of `parallel.py` — it does NOT need to be exported from `__init__.py` or `__all__`. Users should reference it via `aws_expect.parallel.ExpectationItem` if needed, but the primary API is `expect_all`/`expect_any` which accept the union type implicitly.

### Pitfall 2: Docstring Example Becoming Stale

**What goes wrong:** The current docstring shows only lambda examples. After adding tuple support, users who read the docstring may not discover the new capability.

**Prevention:** Add a tuple-form example alongside the existing lambda example in both `expect_all` and `expect_any` docstrings.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Type alias definition | Choosing `TypeAlias` over `type` statement | Use `type ExpectationItem[T] = ...` (Python 3.12+ syntax, available on target 3.13+) |
| Runtime dispatch | Over-validating tuple structure | Let Python unpack naturally; add validation only if error messages prove confusing |
| Test coverage | Not testing mixed sequences (some tuples, some callables) | Include at least one test with `[fn1, (fn2, args, kwargs), fn3]` |
| Type checker integration | `ty` rejecting `executor.submit(fn, *args, **kwargs)` after `isinstance` narrowing | Test with `ty check` before committing; if false positive, suppress with comment |
| Backward compat | Accidentally changing behavior for empty `expectations` sequence | Empty sequence should still return `[]` (expect_all) or raise `ValueError` (expect_any) |
| Error message quality | `AggregateWaitTimeoutError` not distinguishing tuple vs callable timeout source | Acceptable for v1 — the user knows what they passed; improve in later iteration if needed |

## Sources

- Python CPython docs (`/python/cpython`): `Callable[..., T]` semantics, TypeVar resolution in unions
- ty docs (`/websites/astral_sh_ty`): `isinstance` narrowing behavior, `invalid-argument-type` rule
- Existing codebase: `tests/test_parallel_any.py` — current test patterns, `AggregateWaitTimeoutError` usage
- Python typing spec: TypeVar resolution across union elements — common supertype inference
