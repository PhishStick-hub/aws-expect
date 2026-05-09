# Phase 7: S3 Smart Polling - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase adds `stop_when` predicate support to `S3ObjectExpectation.to_exist(entries=...)` — the custom-entry polling path. The predicate receives a shallow-copied resource state dict and can return `True` or a string reason to abort polling early via `StopConditionMetError`.

**In scope:**
- `stop_when: Callable[[dict[str, Any]], bool | str] | None` keyword-only parameter on `to_exist(entries=...)`
- Integration with `StopConditionMetError` and `StopConditionError` from Phase 6
- TypeError guard when `stop_when` is passed without `entries`
- Unit tests for the predicate integration

**Out of scope:**
- `stop_when` on `to_not_exist`, `to_have_content`, `to_not_have_content` (deferred)
- `stop_when` on native boto3 waiter path (`to_exist()` without `entries`)
- DynamoDB, Lambda, SQS stop conditions (Phases 8+, deferred)
</domain>

<decisions>
## Implementation Decisions

### State Dict Shape
- **D-01:** `stop_when(state)` receives the parsed JSON body dict as-is — no metadata keys injected. The resource IS its body.
- **D-02:** `stop_when` is only called when the body exists (`_fetch_body()` returns a dict). When body is `None` (NoSuchKey, invalid JSON), skip `stop_when` and proceed to deadline check.
- **D-03:** State dict is shallow-copied (`dict(state)` or `state.copy()`) before passing to the predicate — mutations inside the predicate do not affect subsequent poll iterations. (Carried forward from Phase 6 research.)

### Predicate Return Convention
- **D-04:** Predicate signature: `Callable[[dict[str, Any]], bool | str]`. When predicate returns `str`, that string is used directly as `stop_reason`.
- **D-05:** When predicate returns `True` (not a string), the polling loop converts it to the default `stop_reason = "stop condition met"`.
- **D-06:** Main-condition-wins ordering: entries match is checked first. Only when entries don't match is `stop_when` evaluated. When the resource already satisfies the entries condition, `stop_when` is never called.

### Predicate Crash Handling
- **D-07:** When `stop_when` raises an exception (other than `StopConditionMetError`), raise `StopConditionError(resource_id)` via `raise ... from original_exc` immediately — fail-fast, no retry.
- **D-08:** When `stop_when` raises `StopConditionMetError` directly, re-raise it as-is — the predicate authored its own error with custom `resource_id` and `stop_reason`.

### Polling Loop Integration
- **D-09:** Insertion point in `_poll_for_entries`: fetch body → entries match? → **stop_when?** → deadline → sleep. `stop_when` is checked after the main condition fails and before the timeout deadline check.
- **D-10:** `resource_id` format for `StopConditionMetError` and `StopConditionError`: `"s3://{bucket}/{key}"` — consistent with existing `S3WaitTimeoutError.__init__` message format.

### TypeError Guard
- **D-11:** `to_exist(entries=None, stop_when=<non-None>)` raises `TypeError` immediately (before any polling): `"stop_when requires entries to be provided. Use to_exist(entries={...}, stop_when=...)"`.
- **D-12:** `stop_when` is keyword-only in the `to_exist` signature — cannot be passed positionally.

### Backward Compatibility
- **D-13:** When `stop_when` is `None` (default), all existing behavior is unchanged. No new code paths are executed.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — S3P-01 (stop_when parameter), S3P-02 (TypeError guard), S3P-03 (StopConditionMetError raising)
- `.planning/REQUIREMENTS.md` §Traceability — Phase 7 maps to S3P-01, S3P-02, S3P-03 only
- `.planning/REQUIREMENTS.md` §Future — deferred: `stop_when` on `to_not_exist`/`to_have_content`/`to_not_have_content`, Lambda, SQS

### Phase Definition
- `.planning/ROADMAP.md` — Phase 7 definition, goal: "S3 polling methods support early abort via stop_when predicates", 5 success criteria, depends on Phase 6

### Prior Phase Decisions
- `.planning/phases/06-exception-foundation/06-CONTEXT.md` — StopConditionMetError(fields: resource_id, stop_reason, elapsed, timeout), StopConditionError(resource_id) via __cause__, predicate return type bool|str (D-02), pytest-assertion-style __str__ (D-06, D-07), module placement in exceptions.py

### Research
- `.planning/research/SUMMARY.md` — Main-condition-wins ordering, shallow-copied state dicts, S3 before DynamoDB, predicate exception propagation

### Project-Level
- `.planning/PROJECT.md` §Key Decisions — StopConditionMetError is NOT a WaitTimeoutError subclass (locked)
- `.planning/PROJECT.md` §Constraints — must not break existing public API, requires LocalStack integration tests
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aws_expect/exceptions.py` — `StopConditionMetError(resource_id, stop_reason, elapsed, timeout)` and `StopConditionError(resource_id, original_exc)` already implemented
- `aws_expect/s3.py:117` — `_poll_for_entries(timeout, poll_interval, entries)` — the method that gets `stop_when` parameter
- `aws_expect/s3.py:34` — `to_exist` overloads — need a new overload for the `stop_when` variant
- `aws_expect/s3.py:99` — `_fetch_body()` returns `dict | None` — already handles NoSuchKey and JSON errors

### Established Patterns
- Polling loop: `deadline = time.monotonic() + timeout`, `while True`: check condition → check deadline → `time.sleep(min(delay, remaining))`
- Attribute naming: `self._bucket`, `self._key` stored in `__init__`
- Docstring format: Google-style with Args/Returns/Raises
- Overload signatures for the two paths (entries vs no-entries) — add a third overload for the `stop_when` variant

### Integration Points
- `aws_expect/s3.py:50` — `to_exist()` signature: add `stop_when` keyword-only parameter, add overload
- `aws_expect/s3.py:85` — entries check: `if entries is not None: return self._poll_for_entries(...)` — pass `stop_when` through
- `aws_expect/s3.py:85-86` — add TypeError guard before `_poll_for_entries` call: `if stop_when is not None and entries is None`
- `aws_expect/s3.py:117-135` — `_poll_for_entries` body: insert stop_when check between entries match and deadline check
- Tests: `tests/test_s3_exist.py` — existing `to_exist(entries=)` tests — add stop_when variants
</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the captured decisions — standard polling augmentation pattern. The `stop_when` check follows the same structure as the entries match check in the existing loop.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 7-S3 Smart Polling*
*Context gathered: 2026-05-09*
