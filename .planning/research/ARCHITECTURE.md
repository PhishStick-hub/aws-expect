# Architecture Patterns: expect_all/expect_any Callable-with-Args

**Domain:** Python library enhancement — parallel execution primitives
**Researched:** 2026-05-10

## Recommended Architecture

No architectural changes. The feature is a **signature and dispatch enhancement** within `aws_expect/parallel.py` — a single-file change that adds type-level flexibility without introducing new components, modules, or abstractions.

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `parallel.py` (modified) | `expect_all`, `expect_any` — now accept `ExpectationItem[T]` union type | `concurrent.futures.ThreadPoolExecutor` (stdlib) |
| `__init__.py` (unchanged) | Public API exports | Consumers of `aws_expect` |
| Service modules (unchanged) | S3, DynamoDB, Lambda, SQS expectation classes | `parallel.py` (unchanged — expectations are still callables returning `T`) |

### Data Flow

```
User code
  │
  ├─ expect_all([fn1, (fn2, (arg,), {"kw": v}), fn3])
  │     │
  │     ▼
  │  parallel.expect_all()
  │     │
  │     ├─ isinstance(exp, tuple)? ──Yes──▶ fn, args, kwargs = exp
  │     │                                      executor.submit(fn, *args, **kwargs)
  │     │
  │     └─ isinstance(exp, tuple)? ──No───▶ executor.submit(exp)   # zero-arg callable
  │
  └─ (same flow for expect_any)
```

The dispatch is local to the `executor.submit()` call. Results collection, error aggregation, and return paths are **unchanged** — the modification point is exclusively at the submission boundary.

## Patterns to Follow

### Pattern 1: Type Alias for Heterogeneous Sequence Element

**What:** Use `type ExpectationItem[T]` to define a union of the two valid element types.

**When:** A `Sequence` parameter should accept elements that differ in structure but share a common return type.

**Example:**
```python
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

T = TypeVar("T")

type ExpectationItem[T] = Callable[[], T] | tuple[Callable[..., T], tuple, dict[str, Any]]

def expect_all(
    expectations: Sequence[ExpectationItem[T]],
    *,
    max_workers: int | None = None,
) -> list[T]:
    ...
```

**Why this pattern:** Keeps the function signature readable and single-purpose. The alias name (`ExpectationItem`) is self-documenting. The union enables heterogeneous sequences while maintaining type safety for `T`.

### Pattern 2: isinstance Dispatch in Executor Submit Loop

**What:** Use `isinstance(exp, tuple)` to branch between zero-arg callable and `(callable, args, kwargs)` tuple at the point of submission.

**When:** A function accepts a union type and must dispatch to different code paths based on the concrete type.

**Example:**
```python
futures: list[Future[T]] = []
with ThreadPoolExecutor(max_workers=workers) as executor:
    for exp in expectations:
        if isinstance(exp, tuple):
            fn, args, kwargs = exp
            futures.append(executor.submit(fn, *args, **kwargs))
        else:
            futures.append(executor.submit(exp))
```

**Why this pattern:** `ty` narrows the union type on `isinstance(exp, tuple)` — in the `if` branch, `exp` is `tuple[Callable[..., T], tuple, dict[str, Any]]`; in the `else` branch, `exp` is `Callable[[], T]`. No cast or type:ignore needed.

### Pattern 3: Callable[..., T] for Arbitrary-Parameter Callables

**What:** Use `Callable[..., T]` (with literal ellipsis `...`) when the exact parameter signature is unknown but the return type is known.

**When:** A function accepts callables with arbitrary parameters and forwards them to an executor that unpacks positional/keyword arguments.

**Example:**
```python
# In ExpectationItem type alias:
tuple[Callable[..., T], tuple, dict[str, Any]]
#          ^^^
#   "any callable returning T" — exact params handled at runtime
```

**Why this pattern:** `Callable[..., T]` is the stdlib way to say "any callable returning T." `ParamSpec` would preserve the exact parameter signature, but we don't need type-safe parameter passing — the user provides pre-configured args/kwargs, and `executor.submit` unpacks them at runtime.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Wrapping in functools.partial

**What:** Converting `(fn, args, kwargs)` to `functools.partial(fn, *args, **kwargs)` before submitting to the executor.

**Why bad:** Adds an unnecessary layer of indirection. Makes exception tracebacks harder to read (the partial wrapper appears in stack frames). `executor.submit(fn, *args, **kwargs)` passes args directly — no wrapping needed.

**Instead:** Unpack the tuple directly at the `executor.submit()` call site.

### Anti-Pattern 2: Creating New Modules or Classes

**What:** Adding a `parallel_items.py`, an `ExpectationItem` dataclass/NamedTuple, or a Protocol class for the "expectation item" concept.

**Why bad:** Over-abstraction. The two valid forms are already representable as a simple union type. Adding a class forces users to construct objects instead of passing plain tuples/callables.

**Instead:** `type ExpectationItem[T] = Callable[[], T] | tuple[Callable[..., T], tuple, dict[str, Any]]` — a zero-cost type alias.

### Anti-Pattern 3: Runtime Validation of Tuple Structure

**What:** Checking `len(exp) == 3` and `callable(exp[0])` before unpacking.

**Why bad:** Premature validation adds code and maintenance burden. If a user passes a malformed tuple, `executor.submit` will raise a clear `TypeError` at the point of failure. Adding manual validation duplicates Python's own error handling without improving the user experience.

**Instead:** Let Python raise naturally. The error message from a malformed tuple is clear enough:
- Wrong length: `ValueError: not enough values to unpack (expected 3, got 2)`
- Non-callable first element: `TypeError: ... object is not callable`

## Scalability Considerations

| Concern | At current usage | With more services | Notes |
|---------|-----------------|-------------------|-------|
| Tuple dispatch overhead | Negligible — one `isinstance` per expectation | Same — O(n) in number of expectations, already dwarfed by ThreadPoolExecutor overhead | No scaling concern |
| TypeVar inference | Works for current return types (dict, bool, etc.) | Same — `T` is inferred from `Callable` return type regardless of surrounding union | Generic pattern scales to any return type |
| Adding new expectation item forms | N/A | The union type pattern supports adding more alternatives (e.g., async callable) by extending the alias | Type alias keeps change isolated |
| Error aggregation | `AggregateWaitTimeoutError` collects per-item errors | Same — errors are per-future, dispatch method doesn't affect error collection | No scaling concern |

## Sources

- Python CPython docs (`/python/cpython`): `Callable[..., T]` semantics — confirmed as "any callable returning T"
- Python CPython docs (`/python/cpython`): `concurrent.futures.ThreadPoolExecutor.submit` — confirmed `submit(fn, *args, **kwargs)`
- Existing codebase: `aws_expect/parallel.py` — current ThreadPoolExecutor usage pattern serves as template for dispatch addition
- ty docs (`/websites/astral_sh_ty`): `isinstance` narrowing on union types — confirmed; ty narrows both branches correctly
