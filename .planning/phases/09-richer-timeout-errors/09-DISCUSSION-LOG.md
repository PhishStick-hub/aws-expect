# Phase 9: Richer Timeout Errors - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 09-richer-timeout-errors
**Areas discussed:** Base class expected/actual fields, Message format and field naming, Truncation behavior for large collections, AggregateWaitTimeoutError format

---

## Base class expected/actual fields

| Option | Description | Selected |
|--------|-------------|----------|
| Base class attrs, rename subclasses | Define expected/actual=None on WaitTimeoutError base. Rename entries→expected, body→expected, event→expected. Slight break for direct .entries access. | ✓ |
| Base class attrs, aliases in subclasses | Define expected/actual on base, but keep backward-compat field names as aliases. | |
| No base class change, shared helper takes params | Don't touch base class. Helper receives (expected, actual) as params. Subclasses keep own field names. | |

**User's choice:** Base class attrs, rename subclasses
**Notes:** Breaking change accepted — `.entries` → `.expected` on DynamoDBWaitTimeoutError is intentional for consistency.

---

## Message format and field naming

| Option | Description | Selected |
|--------|-------------|----------|
| Full message from shared helper | Single _format_timeout_error(resource_desc, expected, actual, timeout) produces the entire message. All errors look identical. | ✓ |
| Shared helper for Expected:/Actual: block only | Helper produces only the section block. Each class keeps its own first-line context. | |
| Mix — full message but resource_desc is freeform | Helper produces full message, resource_desc is a freeform string. | |

**User's choice:** Full message from shared helper
**Notes:** When both expected and actual are None, the Expected:/Actual: block is omitted. This handles S3WaitTimeoutError and LambdaWaitTimeoutError naturally.

---

## Truncation behavior for large collections

| Option | Description | Selected |
|--------|-------------|----------|
| Count annotation | Show first N, then `... (N more items not shown)`. Clear and useful for debugging. | ✓ |
| Ellipsis suffix only | Show truncated content ending with `...`. Minimal. | |
| Header summary first | Prepend count header, then show truncated list. Most verbose. | |

**User's choice:** Count annotation
**Notes:** Max 50 items for lists, max 500 chars per value. Truncation applied to repr() output. Separate handling for lists vs. oversized individual values.

---

## AggregateWaitTimeoutError format

| Option | Description | Selected |
|--------|-------------|----------|
| Show each sub-error __str__ in full | Current format but each sub-error now includes Expected:/Actual: naturally. No special handling needed. | ✓ |
| Summary only | Suppress Expected:/Actual: from sub-errors. Compact but loses debugging info. | |
| Separator-delimited per-error blocks | Clear visual separation with `---` dividers. Cleanest but most verbose. | |

**User's choice:** Show each sub-error __str__ in full
**Notes:** No changes to AggregateWaitTimeoutError itself — sub-error enrichment happens automatically via their own __str__.

---

## the agent's Discretion

None — all decisions were made by the user.

## Deferred Ideas

None — discussion stayed within phase scope.
