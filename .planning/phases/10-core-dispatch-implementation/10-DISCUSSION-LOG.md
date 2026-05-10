# Phase 10: Core Dispatch Implementation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 10-core-dispatch-implementation
**Areas discussed:** Tuple shape, ExpectationItem visibility, Type narrowing

---

## Tuple Shape

| Option | Description | Selected |
|--------|-------------|----------|
| 3-tuple only | Always `(fn, args, kwargs)`. Users pass `({},)` when no kwargs. Simpler type, clearer intent. | ✓ |
| Both 2- and 3-tuple | `(fn, args)` as shorthand for `(fn, args, {})`. Less boilerplate for the common no-kwargs case. | |

**User's choice:** 3-tuple only — matches the stated REQ specification exactly.
**Notes:** None.

---

## ExpectationItem Visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Internal only | Keep `ExpectationItem[T]` private to `parallel.py`. Overloaded signatures in Phase 11 handle IDE hover. | ✓ |
| Public API | Export from `__init__.py` and add to `__all__` for user type annotations. | |

**User's choice:** Internal only — not part of the public API.
**Notes:** None.

---

## Type Narrowing for executor.submit

| Option | Description | Selected |
|--------|-------------|----------|
| ignore[arg-type] | Localised suppression on the `executor.submit(fn, *args, **kwargs)` line. | |
| Extract dispatch function | Private helper function with isinstance narrowing inside, clean type separation without suppressions. | ✓ |

**User's choice:** Extract a private dispatch helper to avoid type suppression.
**Notes:** None.

---

## the agent's Discretion

None — all decisions were made by the user.

## Deferred Ideas

None — discussion stayed within phase scope.
