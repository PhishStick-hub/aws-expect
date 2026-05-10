# Phase 9: Richer Timeout Errors - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase makes every `WaitTimeoutError.__str__` show structured `Expected:` / `Actual:` sections via a shared formatting helper with truncation guards. The base class `WaitTimeoutError` gains `expected`/`actual` fields, subclass field names are unified (`entries`/`body`/`event` → `expected`), and a single `_format_timeout_error()` function in `_utils.py` produces all timeout error messages.

**In scope:**
- `expected`/`actual` fields on `WaitTimeoutError` base class (defaulting to `None`)
- Rename subclass fields: `entries`→`expected`, `body`→`expected`, `event`→`expected`
- Shared `_format_timeout_error(resource_desc, expected, actual, timeout)` helper in `_utils.py`
- Shared `_truncate_value(value)` helper with 50-item / 500-char safeguards
- Unified `Expected:` / `Actual:` labeling across all timeout error messages
- Truncation count annotation: `... (N more items not shown)`
- `AggregateWaitTimeoutError` delegates to sub-errors' `__str__` (naturally enriched)

**Out of scope:**
- `StopConditionMetError` and `StopConditionError` — NOT `WaitTimeoutError` subclasses (Phase 6 decisions lock their format)
- Non-timeout errors (`S3UnexpectedContentError`, `DynamoDBUnexpectedItemError`, `DynamoDBNonNumericFieldError`, `SQSUnexpectedEventError`, `SQSUnexpectedMessageError`, `LambdaResponseMismatchError`) — inherit `Exception` directly, not affected
- `AggregateWaitTimeoutError` per-callable error detail enrichment — deferred to future milestone
- `TypedDict` for state dict shapes — deferred to future milestone
</domain>

<decisions>
## Implementation Decisions

### Base Class expected/actual Fields
- **D-01:** `WaitTimeoutError` defines `expected: Any = None` and `actual: Any = None` as class-level attributes. All subclasses inherit these — no explicit declaration needed in subclasses.
- **D-02:** Subclass field names are unified to `expected`/`actual`:
  - `DynamoDBWaitTimeoutError.entries` → `.expected`
  - `SQSWaitTimeoutError.body` → `.expected`
  - `SQSEventWaitTimeoutError.event` → `.expected`
  - Classes that already use `expected`/`actual` (`S3ContentWaitTimeoutError`, `DynamoDBFindItemTimeoutError`, `LambdaInvocableTimeoutError`) need no field rename — only the helper wiring changes.
- **D-03:** Classes without expected/actual (`S3WaitTimeoutError`, `LambdaWaitTimeoutError`) inherit `expected=None, actual=None` from the base — no changes to their constructors.

### Message Format
- **D-04:** A single shared function `_format_timeout_error(resource_desc: str, expected: Any, actual: Any, timeout: float) -> str` in `aws_expect/_utils.py` produces the full error message:
  ```
  Timed out after {timeout}s waiting for {resource_desc}

  Expected:
    {expected_formatted}

  Actual:
    {actual_formatted}
  ```
  When both `expected` and `actual` are `None`, the `Expected:`/`Actual:` block is omitted entirely — the message is just the first line. When only one is `None`, only that section is omitted.
- **D-05:** Each subclass calls the shared helper in `__init__`:
  1. Set `self.expected` and `self.actual` (and subclass-specific fields)
  2. `super().__init__(_format_timeout_error(resource_desc, self.expected, self.actual, self.timeout))`
  Subclasses that currently call `WaitTimeoutError.__init__(self, msg)` directly (e.g., `S3ContentWaitTimeoutError`, `DynamoDBFindItemTimeoutError`, `LambdaInvocableTimeoutError`) switch to use `_format_timeout_error` with the same `resource_desc` as their current first-line context.
- **D-06:** `DynamoDBWaitTimeoutError` retains its `message` parameter for backward compatibility. When `message` is provided, it appends `Actual:` to the custom message instead of using the standard format. This path is documented as a legacy compatibility path — new callers should use the standard format.

### Truncation Behavior
- **D-07:** Truncation limits: max 50 items for lists/tuples, max 500 characters per individual value (via `repr()`).
- **D-08:** Truncation annotation uses count: `... ({N} more items not shown)` for lists, `... (value truncated, showing first 500 of {total} chars)` for oversized strings/values.
- **D-09:** A shared `_truncate_value(value: Any) -> str` function in `_utils.py` handles all truncation logic. Rules:
  - `None` → `"None"`
  - `list`/`tuple` with ≤ 50 items → `repr(value)`
  - `list`/`tuple` with > 50 items → `repr(first_50) + f"\n... ({remaining} more items not shown)"`
  - Other values where `len(repr(value))` ≤ 500 → `repr(value)`
  - Other values where `len(repr(value))` > 500 → `repr(value)[:500] + f"\n... (value truncated, showing first 500 of {total_len} chars)"`

### AggregateWaitTimeoutError
- **D-10:** `AggregateWaitTimeoutError.__str__` keeps its current summary-header + per-error-details structure. No changes to the format — each sub-error's `__str__` now naturally includes `Expected:`/`Actual:` via the shared helper, so the aggregate output is automatically enriched.
- **D-11:** No changes to `AggregateWaitTimeoutError` itself — it already iterates sub-errors via `str(e)` in its `__init__` details loop.

### Shared Helper Placement
- **D-12:** Both `_format_timeout_error` and `_truncate_value` go in `aws_expect/_utils.py` — alongside existing shared helpers `_deep_matches`, `_matches_entries`, `_compute_delay`, and `_check_stop_condition`.
- **D-13:** `_format_timeout_error` is a module-level function, not a method on `WaitTimeoutError`. This keeps the helper importable by all modules that construct timeout errors (exceptions.py, s3.py, dynamodb.py, sqs.py, lambda_function.py, parallel.py) without circular imports.

### the agent's Discretion
None — all decisions were made by the user.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — ERR-01 (expected/actual fields on all WaitTimeoutError subclasses), ERR-02 (clear Expected:/Actual: labeling), ERR-03 (shared __str__ helper with truncation)
- `.planning/REQUIREMENTS.md` §Traceability — Phase 9 maps to ERR-01, ERR-02, ERR-03 only
- `.planning/REQUIREMENTS.md` §Error Enrichment — AggregateWaitTimeoutError per-callable detail and TypedDict state shapes deferred to future milestones

### Phase Definition
- `.planning/ROADMAP.md` — Phase 9 definition, goal: "Every timeout failure message shows what was expected and what was actually found", 2 success criteria, depends on Phase 8

### Prior Phase Decisions
- `.planning/phases/06-exception-foundation/06-CONTEXT.md` — D-08 (shared __str__ helper with truncation deferred to Phase 9); StopConditionMetError/StopConditionError are NOT WaitTimeoutError subclasses (out of scope for this phase)
- `.planning/phases/07-s3-smart-polling/07-CONTEXT.md` — S3 stop_when pattern reference (no changes needed here)
- `.planning/phases/08-dynamodb-smart-polling/08-CONTEXT.md` — DynamoDB stop_when pattern reference; _check_stop_condition extracted to _utils.py (same module that gets _format_timeout_error)

### Project-Level
- `.planning/PROJECT.md` §Key Decisions — StopConditionMetError is NOT a WaitTimeoutError subclass (locked); Exception-direct inheritance for non-timeout errors
- `.planning/PROJECT.md` §Constraints — must not break existing public API, requires LocalStack integration tests
- `.planning/PROJECT.md` §Core Value — "Every assertion must give a clear error explaining what was expected and what was found when it times out"
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aws_expect/_utils.py` — Shared helper module. Already hosts `_deep_matches`, `_matches_entries`, `_compute_delay`, `_check_stop_condition`. Add `_format_timeout_error` and `_truncate_value` here. All service modules already import from this file.
- `aws_expect/exceptions.py:11` — `WaitTimeoutError(Exception)` base class with `timeout` attribute. Add `expected = None` and `actual = None` as class-level attributes.
- `aws_expect/exceptions.py:98-114` — `S3ContentWaitTimeoutError.__init__` pattern: sets `self.expected`/`self.actual`, then calls `WaitTimeoutError.__init__(self, msg)`. This is the reference pattern for the new flow — replace the manual message construction with `_format_timeout_error()`.
- `aws_expect/exceptions.py:195-217` — `DynamoDBFindItemTimeoutError.__init__` — same direct-call pattern, replace with helper.
- `aws_expect/exceptions.py:316-336` — `LambdaInvocableTimeoutError.__init__` — same direct-call pattern, replace with helper.

### Established Patterns
- Classes that inherit multi-level (e.g., `DynamoDBFindItemTimeoutError` → `DynamoDBWaitTimeoutError` → `WaitTimeoutError`) call `WaitTimeoutError.__init__` directly to bypass intermediate `__init__` signature mismatches. This pattern is preserved — they'll call `WaitTimeoutError.__init__(self, _format_timeout_error(...))`.
- Docstring format: Google-style with Attributes block. All subclasses must document `expected` and `actual` (inherited from WaitTimeoutError) in their Attributes.
- Polling modules construct timeout errors inline (e.g., `raise DynamoDBWaitTimeoutError(...)`) — these call sites pass different parameter names. After rename, `entries=` → `expected=`, `body=` → `expected=`, `event=` → `expected=`.

### Integration Points
- `aws_expect/exceptions.py:11` — `WaitTimeoutError` base class — add `expected`/`actual` class-level attrs
- `aws_expect/exceptions.py:73-80` — `S3WaitTimeoutError.__init__` — wire `_format_timeout_error` (expected=None, actual=None → no block)
- `aws_expect/exceptions.py:83-115` — `S3ContentWaitTimeoutError.__init__` — replace manual message with `_format_timeout_error`
- `aws_expect/exceptions.py:147-177` — `DynamoDBWaitTimeoutError.__init__` — rename `entries`→`expected`, wire helper, preserve `message` override
- `aws_expect/exceptions.py:180-217` — `DynamoDBFindItemTimeoutError.__init__` — replace manual message with `_format_timeout_error`
- `aws_expect/exceptions.py:289-302` — `LambdaWaitTimeoutError.__init__` — wire helper (expected=None, actual=None → no block)
- `aws_expect/exceptions.py:305-336` — `LambdaInvocableTimeoutError.__init__` — replace manual message with `_format_timeout_error`
- `aws_expect/exceptions.py:377-399` — `SQSWaitTimeoutError.__init__` — rename `body`→`expected`, wire helper
- `aws_expect/exceptions.py:421-454` — `SQSEventWaitTimeoutError.__init__` — rename `event`→`expected`, wire helper
- `aws_expect/exceptions.py:478-504` — `AggregateWaitTimeoutError` — no changes needed (sub-errors auto-enriched)
- `aws_expect/_utils.py` — Add `_format_timeout_error` and `_truncate_value` functions
- `aws_expect/dynamodb.py:17,113,175,217,261,427,483,523` — All call sites passing `entries=` to `DynamoDBWaitTimeoutError` → rename to `expected=`. Also pass `actual=` where applicable.
- `aws_expect/sqs.py:87` — Call site passing `body=` → rename to `expected=`
- `aws_expect/sqs.py:284,335` — Call sites for `SQSEventWaitTimeoutError` passing `event=` → rename to `expected=`
- `aws_expect/s3.py:123,173,211,264` — S3 call sites may need `actual=` parameter adjustments
</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the captured decisions. The implementation is a mechanical refactoring: add two fields to the base class, unify field names in subclasses, extract shared string formatting logic to `_utils.py`, and add truncation guards.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 9-Richer Timeout Errors*
*Context gathered: 2026-05-10*
