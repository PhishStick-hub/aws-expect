# Phase 11: Type Polish, Edge Testing, Docs - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 11-type-polish-edge-testing-docs
**Areas discussed:** Overload strategy, Mixed-sequence edge testing, Docstring scope & depth, Does mixed work out of the box?

---

## Overload Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Two overloads: pure-callable + pure-tuple | 2 decorated overloads per function (all-callable and all-tuple), plus undecorated implementation with `Sequence[ExpectationItem[T]]`. Mixed sequences fall through to implementation signature. | ✓ |
| Three overloads: pure-callable + pure-tuple + mixed | Also adds explicit mixed-sequence overload. Longer overload list, marginal UX gain. | |
| Single overload: union-only | One overload with union type. Cleaner file but IDE hover shows union instead of specific form. | |

**User's choice:** Two overloads: pure-callable + pure-tuple (Recommended)
**Notes:** Standard Python idiom. Matches ROADMAP's "all-callable and all-tuple sequences" language.

### Overload Shape Follow-up

| Option | Description | Selected |
|--------|-------------|----------|
| Define ExpectationTuple[T] alias, use in overloads | Add `ExpectationTuple[T] = tuple[Callable[..., T], tuple, dict[str, Any]]` alongside `ExpectationItem[T]`. Clean 1-line hover. | ✓ |
| Inline the full tuple type | Overload shows `Sequence[tuple[Callable[..., T], tuple, dict[str, Any]]]` — correct but noisy. | |
| Reuse ExpectationItem[T] for overload | Defeats purpose of PAR-05 since IDE shows same union type. | |

**User's choice:** Define ExpectationTuple[T] type alias, use in overloads (Recommended)
**Notes:** Both aliases stay internal (not in `__all__`).

---

## Mixed-Sequence Edge Testing

### Test Class Placement

| Option | Description | Selected |
|--------|-------------|----------|
| New test classes: TestExpectAllMixed + TestExpectAnyMixed | Add new classes to each test file. Clear phase boundaries. | ✓ |
| Add to Phase 10's tuple-form classes | Extend existing classes. Muddies phase boundary. | |
| Add to existing success/failure classes | Sprinkle across file. Scatters verification. | |

**User's choice:** New test classes: TestExpectAllMixed + TestExpectAnyMixed (Recommended)

### Test Scenarios (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| Tuple-first ordering | Sequence starts with tuple, ends with plain callable. | ✓ |
| Callable-first ordering | Sequence starts with plain callable, ends with tuple. | ✓ |
| Interleaved: tuple, callable, tuple | Three items alternating forms. | ✓ |
| Mixed with one failure | One item times out, others succeed. Verifies `None` at correct index. | ✓ |
| All mixed with all failures | Every item times out. Verifies error aggregation uniformity. | ✓ |

**User's choice:** All five scenarios selected
**Notes:** 10 test methods total (5 per class × 2 classes).

---

## Docstring Scope & Depth

### Example Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Add tuple examples alongside lambdas | Keep both forms visible. Shows upgrade path. | ✓ |
| Replace lambdas with tuples only | Only new form. Existing users lose reference. | |
| Add to expect_all only (not expect_any) | Doesn't satisfy PAR-06 requirement. | |

**User's choice:** Add tuple examples alongside lambdas (Recommended)

### Example Count

| Option | Description | Selected |
|--------|-------------|----------|
| One tuple example per function | Mirror the lambda example structure. Compact. | ✓ |
| Two per function: with-args and with-kwargs | More illustrative but verbose. | |
| One per function + module-level note | Prose note explaining structure. | |

**User's choice:** One tuple example per function (Recommended)
**Notes:** `expect_all` shows args+kwargs usage, `expect_any` shows simpler tuple usage.

---

## Does Mixed Work Out of the Box?

| Option | Description | Selected |
|--------|-------------|----------|
| Plan assumes mixed works, verify with tests | No parallel.py logic changes for mixed dispatch. Verify via tests. | ✓ |
| Defensive isinstance guard in iteration loop | Redundant since _submit_expectation handles it. Adds code without value. | |
| Spike first — verify before committing | Slower delivery for low-risk assumption. | |

**User's choice:** Plan assumes mixed works, verify with tests (Recommended)
**Notes:** `_submit_expectation` handles per-item dispatch independently. If tests reveal a bug, fix is minimal.

---

## the agent's Discretion

None — all decisions were made by the user.

## Deferred Ideas

None — discussion stayed within phase scope.
