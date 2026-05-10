# Feature Landscape: expect_all/expect_any Callable-with-Args

**Domain:** Python library enhancement — parallel execution primitives
**Researched:** 2026-05-10

## Table Stakes

Features users expect. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Accept `(callable, args, kwargs)` tuples in `expect_all` | Removes `lambda:` boilerplate — users can pass `(fn, (arg1,), {})` instead of `lambda: fn(arg1)` | Low | Runtime: `executor.submit(fn, *args, **kwargs)` |
| Accept `(callable, args, kwargs)` tuples in `expect_any` | Same motivation — consistency across both parallel primitives | Low | Mirror of `expect_all` dispatch |
| Backward compatibility with `Callable[[], T]` | Existing call sites must continue to work without modification | Low | Union type ensures both forms are valid |
| Same error types and messages | `AggregateWaitTimeoutError` with `results` list must work identically | Low | Unchanged error paths |
| Same return types (`list[T]` / `T`) | `T` must be inferred correctly from tuple-form callable's return type | Low | TypeVar flows through `Callable[..., T]` in tuple |

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Type narrowing with `TypeIs` for tuple detection | Better IDE experience — type checker knows which branch is which | Low | Optional; `isinstance(exp, tuple)` already narrows with ty |
| `@overload` for pure-form signatures | IDE shows separate signatures for `list[Callable]` vs `list[tuple[...]]` usage | Low | Optional; the union type alone is correct and complete |
| Type alias `ExpectationItem[T]` | Makes function signatures readable; reusable if other parallel functions are added later | Low | `type ExpectationItem[T] = Callable[[], T] \| tuple[Callable[..., T], tuple, dict[str, Any]]` |
| `py.typed` marker compatibility | The library already ships type information — type alias is transparent to consumers | Low | No change to build/packaging |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| `functools.partial` wrapping inside `parallel.py` | Adds indirection, obscures tracebacks, and the callable is already fully parameterized by the user | Pass `(fn, args, kwargs)` directly to `executor.submit()` |
| Separate `expect_all_with_args` function | Fragments the API; users must remember which function to call | Single `expect_all` with union type |
| Signature-preserving type checking via `ParamSpec` | `ParamSpec` is designed for decorators that transform callable signatures, not for "call any callable with any args" | `Callable[..., T]` correctly expresses the constraint |
| `Protocol` class for expectation items | Over-engineering — a simple union type handles the two cases | Union type alias |
| Validation of tuple structure at call time | Pythonic to let `executor.submit` raise naturally; premature validation adds code without value | Let Python's runtime error on malformed tuples |
| Support for `*args, **kwargs` as separate list elements (not tuple) | Would require a different calling convention and break backward compatibility | User wraps args/kwargs in a 3-tuple: `(fn, args, kwargs)` |

## Feature Dependencies

```
Tuple dispatch in submit loop → Union type in function signature → Type alias ExpectationItem[T]
         (all in parallel.py — no cross-module dependencies)
```

No feature depends on changes to S3, DynamoDB, Lambda, SQS, exceptions, or any other module.

## MVP Recommendation

Prioritize:
1. **Type alias `ExpectationItem[T]`** — foundation for all other typing
2. **Runtime dispatch in `expect_all`** — core feature; `isinstance(exp, tuple)` with unpack
3. **Runtime dispatch in `expect_any`** — mirror of expect_all
4. **Docstring update** — document new usage pattern with example
5. **Test: tuple-form success in expect_all** — table stakes validation
6. **Test: tuple-form success in expect_any** — mirror

Defer:
- `TypeIs` guard function: Use plain `isinstance(exp, tuple)` first; add `TypeIs` if ty can't narrow without it (but docs confirm it can)
- `@overload` signatures: Add if IDE experience proves confusing without them

## Sources

- Python CPython docs (`/python/cpython`): `concurrent.futures.ThreadPoolExecutor.submit` — confirmed `submit(fn, *args, **kwargs)` since Python 3.2
- Existing codebase: `aws_expect/parallel.py` — current implementation, test patterns in `tests/test_parallel_any.py`
- ty docs (`/websites/astral_sh_ty`): `TypeIs`, `isinstance` narrowing, `@overload` — all confirmed supported in 0.0.20
