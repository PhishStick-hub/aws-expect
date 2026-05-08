# Phase 6: Exception Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 6-Exception Foundation
**Areas discussed:** StopConditionMetError fields, StopConditionError design, __str__ formatting, Module placement + integration

---

## StopConditionMetError Fields

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: resource_id + stop_reason only | Matches EXN-01 exactly. Keeps focus. | |
| Extended: add elapsed + timeout | Adds elapsed/timeout for debugging context. | ✓ |
| Full: service + resource_id + stop_state + timeout + poll_count + elapsed | As RESEARCH.md draft. Comprehensive but overkill. | |

**User's choice:** Extended — resource_id, stop_reason, elapsed, timeout.

---

### resource_id type

| Option | Description | Selected |
|--------|-------------|----------|
| str | Simple string like `s3://bucket/key` | ✓ |
| Any | Flexible but less predictable | |

**User's choice:** str — consistent with existing exception patterns.

---

### stop_reason type

| Option | Description | Selected |
|--------|-------------|----------|
| Require predicate to return str | `Callable[[dict[str, Any]], bool \| str]`. str = descriptive reason, True = generic fallback | ✓ |
| Keep predicate returning bool | Exact signature match, stop_reason = True | |

**User's choice:** Predicate returns `bool | str`. Strings become descriptive stop reasons.

---

### Constructor style

| Option | Description | Selected |
|--------|-------------|----------|
| Positional args | Matches `S3WaitTimeoutError(bucket, key, timeout)` pattern | ✓ |
| Positional required + keyword-only optional | More explicit but different from existing | |

**User's choice:** Positional — `StopConditionMetError(resource_id, stop_reason, elapsed, timeout)`.

---

## StopConditionError Design

| Option | Description | Selected |
|--------|-------------|----------|
| resource_id + __cause__ only | Identifies resource + preserves original via __cause__ | ✓ |
| resource_id + predicate_exception field + __cause__ | Redundant — __cause__ already holds it | |
| resource_id + state_at_failure + __cause__ | Useful but may store large dicts in exceptions | |

**User's choice:** resource_id + __cause__ only. Minimal, focused.

---

### Constructor style

| Option | Description | Selected |
|--------|-------------|----------|
| Accept via raise...from only | `raise StopConditionError(id) from orig` — Python convention | ✓ |
| Accept original_exc as parameter | Explicit but redundant with __cause__ | |

**User's choice:** `raise...from` only. `StopConditionError(resource_id)`.

---

## __str__ Formatting

| Option | Description | Selected |
|--------|-------------|----------|
| Pytest-assertion style | Labeled format with elapsed/total + reason | ✓ |
| One-liner | Compact but hard to scan | |
| Debug-style with repr | Machine-parseable, less human-friendly | |

**User's choice:** Pytest-assertion style — matches existing `DynamoDBWaitTimeoutError` pattern.

---

### StopConditionError __str__

| Option | Description | Selected |
|--------|-------------|----------|
| Include original exception text | `Error in stop_when predicate for {id}: {original}` | ✓ |
| Resource-only with cause note | Keep short — see __cause__ for details | |

**User's choice:** Include original exception text inline.

---

### Shared __str__ helper

| Option | Description | Selected |
|--------|-------------|----------|
| Inline formatting | Each class formats own __str__ — KISS for 2 classes | ✓ |
| Extract a small helper | Start convention early, but may be premature | |

**User's choice:** Inline — no shared helper yet. Phase 9's concern.

---

## Module Placement + Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Same exceptions.py | All exceptions in one file, ~40 lines added to 450-line file | ✓ |
| New _stop_errors.py | Separate module — overkill for 2 classes | |

**User's choice:** Same `exceptions.py`.

---

### Placement order

| Option | Description | Selected |
|--------|-------------|----------|
| After WaitTimeoutError, before service subclasses | Foundational types near base, visible position | ✓ |
| At bottom of file | Simpler edit, less prominent | |
| Dedicated section between unexpected-error and timeout classes | Most organized but restructures file | |

**User's choice:** After `WaitTimeoutError` (~line 18), before `S3WaitTimeoutError` (~line 21).

---

## the Agent's Discretion

No areas were deferred to the agent — user selected all options.

## Deferred Ideas

None — discussion stayed within phase scope.
