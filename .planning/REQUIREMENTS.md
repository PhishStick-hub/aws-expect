# Requirements: aws-expect

**Defined:** 2026-05-10
**Core Value:** Correct, declarative AWS waiters with good error messages

## v1.4.0 Requirements

Requirements for parallel execution enhancement. Each maps to roadmap phases.

### Parallel — Callable Args

- [ ] **PAR-01**: User can pass `(callable, args, kwargs)` tuples to `expect_all` — the callable is invoked with `*args, **kwargs` in the thread pool
- [ ] **PAR-02**: User can pass `(callable, args, kwargs)` tuples to `expect_any` — same semantics as `expect_all` but returns first success
- [ ] **PAR-03**: Existing `Callable[[], T]` expectations continue working unchanged — tuple and plain callable forms can be mixed in the same sequence
- [ ] **PAR-04**: `ExpectationItem[T]` type alias (`Callable[[], T] | tuple[Callable[..., T], tuple, dict[str, Any]]`) defined in `parallel.py` and used in function signatures
- [ ] **PAR-05**: `@overload` signatures for `expect_all` and `expect_any` providing clean IDE hover info for pure-callable and pure-tuple sequences
- [ ] **PAR-06**: Docstring examples showing tuple-form usage for both `expect_all` and `expect_any`

## Future Requirements

Deferred to future milestones. Tracked but not in current roadmap.

- `TypeIs` guard function — `isinstance(exp, tuple)` already provides narrowing; add only if checker behavior proves insufficient
- Friendlier error messages for malformed tuples — Python's built-in ValueError is clear enough for v1
- `AggregateWaitTimeoutError` distinguishing tuple vs callable source in failure messages
- `functools.partial` auto-detection — type checker compatibility concerns, defer

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| New dependencies or packages | Zero external dependencies needed — all via stdlib |
| Changes to exceptions.py, __init__.py, or service modules | Change is isolated to parallel.py only |
| Separate `expect_all_with_args` function | Would fragment the API — tuple form in existing functions is cleaner |
| `functools.partial` integration | Adds indirection, obscures tracebacks — `executor.submit` accepts args directly |
| Changes to error types or AggregateWaitTimeoutError | Same error handling as current behavior |
| `ParamSpec` for precise callable typing | Over-constrains — `Callable[..., T]` correctly expresses "any callable returning T" |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PAR-01 | Phase 10 | Pending |
| PAR-02 | Phase 10 | Pending |
| PAR-03 | Phase 11 | Pending |
| PAR-04 | Phase 10 | Pending |
| PAR-05 | Phase 11 | Pending |
| PAR-06 | Phase 11 | Pending |

**Coverage:**
- v1.4.0 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-10*
*Last updated: 2026-05-10 after roadmap creation*
