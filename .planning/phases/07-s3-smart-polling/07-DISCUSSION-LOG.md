# Phase 7: S3 Smart Polling - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 07-s3-smart-polling
**Areas discussed:** State dict shape, Predicate crash handling, stop_reason default, TypeError guard message

---

## State Dict Shape

### What should stop_when(state) receive?

| Option | Description | Selected |
|--------|-------------|----------|
| Just the parsed body | Pass raw JSON body as-is — simplest, predictable. Callers already know bucket/key. | ✓ |
| Body + metadata keys | Merge _bucket, _key, _elapsed into the state dict. Risk of key collisions. | |

**User's choice:** Just the parsed body (Recommended)

### Should stop_when be called when body is None (NoSuchKey)?

| Option | Description | Selected |
|--------|-------------|----------|
| No — skip stop_when | Predicate only fires when body exists. Avoids None checks in every predicate. | ✓ |
| Yes — call with None | Callers can check for None to create time-based predicates. | |

**User's choice:** No — skip stop_when when body isn't available

---

## Predicate Crash Handling

### When stop_when raises, abort or retry?

| Option | Description | Selected |
|--------|-------------|----------|
| Abort immediately | Raise StopConditionError from original_exc — fail-fast. Matches existing patterns. | ✓ |
| Retry on next poll | Log the error, continue polling. More resilient but hides bugs. | |

**User's choice:** Abort immediately (Recommended)

### If predicate raises StopConditionMetError?

| Option | Description | Selected |
|--------|-------------|----------|
| Re-raise as-is | Treat user's StopConditionMetError as authoritative — full control. | ✓ |
| Wrap in StopConditionError | Treat like any other exception — wrap it. Loses user's error context. | |

**User's choice:** Re-raise as-is — predicate can craft its own error

---

## stop_reason Default

### What default when predicate returns True (not a string)?

| Option | Description | Selected |
|--------|-------------|----------|
| "stop condition met" | Simple, clear, user-facing. | ✓ |
| "predicate returned True" | Technical and precise. | |
| A sentinel constant | Module-level constant. Adds public API surface for internal detail. | |

**User's choice:** "stop condition met" (Recommended)

---

## TypeError Guard Message

### What message when stop_when used without entries?

| Option | Description | Selected |
|--------|-------------|----------|
| Suggest the fix | "stop_when requires entries to be provided. Use to_exist(entries={...}, stop_when=...)" | ✓ |
| State the requirement | "stop_when requires entries to be provided" | |
| Explain why | "stop_when is not supported on the native waiter path..." | |

**User's choice:** Suggest the fix — show the user exactly how to correct it

---

## Agent's Discretion

None — user made all decisions explicitly.

## Deferred Ideas

None — discussion stayed within phase scope.
