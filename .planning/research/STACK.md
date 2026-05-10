# Technology Stack

**Project:** aws-expect — `expect_all` / `expect_any` callable-with-args support
**Researched:** 2026-05-10

## Recommended Stack

### Core Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.13+ | Runtime | Already required by project; no new language features needed beyond what's already used |

### Standard Library (No New Dependencies)
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `concurrent.futures` | stdlib | Thread pool execution | Already used; `executor.submit(fn, *args, **kwargs)` is the existing integration point |
| `collections.abc.Callable` | stdlib | Type annotations | Already imported; `Callable[[], T]` and `Callable[..., T]` for type hints |
| `typing.overload` | stdlib | Type narrowing | Multiple signatures for type checker; no runtime impact |
| `isinstance` | builtin | Tuple detection | Standard Python pattern for union-type dispatch |

### Infrastructure
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pytest | existing | Integration tests | Already configured; LocalStack fixtures available |
| testcontainers[localstack] | existing | AWS service emulation | Already used for all integration tests |

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| None new | — | — | This feature adds no new dependencies |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Dispatch mechanism | `isinstance(entry, tuple)` check | `callable(entry)` check (treat non-callable as tuple) | Loses early error detection; `callable()` returns `True` for classes, methods, etc.; can't distinguish "plain callable" from "tuple" reliably |
| Tuple validation | Pre-submit validation with `TypeError` | Defer to `future.exception()` (stdlib pattern) | Loses entry index info; contradicts library's "good error messages" philosophy |
| Type narrowing | `@overload` with `Callable[..., T]` | `ParamSpec` for precise arg tracking | `ParamSpec` can't describe pre-packed tuples in generic context; adds complexity without practical benefit |
| kwargs handling | `kwargs` defaults to `{}` when omitted | Always require 3-tuple `(fn, args, kwargs)` | More boilerplate for common zero-kwargs case; users forced to write `(fn, (arg1,), {})` |
| API surface | Same `expect_all`/`expect_any` functions | New functions `expect_all_with_args` | API bloat; users must remember two function names; migration burden |

## Installation

```bash
# No new dependencies to install
# Existing project dependencies unchanged:
uv sync --all-groups
```

## Sources

- Python `concurrent.futures` docs — `ThreadPoolExecutor.submit(fn, /, *args, **kwargs)` (HIGH confidence)
- Python `typing` docs — `@overload`, `Callable`, `ParamSpec` (HIGH confidence)
- Python `isinstance` and `callable` builtins — dispatch patterns (HIGH confidence)
- Existing `pyproject.toml` — confirmed no new dependencies needed (HIGH confidence)
