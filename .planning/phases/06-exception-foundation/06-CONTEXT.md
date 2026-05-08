# Phase 6: Exception Foundation - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers two new exception classes — `StopConditionMetError` and `StopConditionError` — that are importable from `aws_expect`, integrate cleanly into the existing exception hierarchy, and are ready for consumption by Phases 7 (S3 Smart Polling) and 8 (DynamoDB Smart Polling).

These are **pure exception classes with zero runtime dependencies.** No AWS service integration, no polling logic, no changes to existing waiters.
</domain>

<decisions>
## Implementation Decisions

### StopConditionMetError

- **D-01: Fields** — `resource_id` (str), `stop_reason` (str), `elapsed` (float), `timeout` (float). `stop_reason` is the predicate's string return value; `elapsed` is how long was actually waited before the stop fired; `timeout` is the originally configured timeout.
- **D-02: Predicate return type** — The `stop_when` predicate signature across all phases will be `Callable[[dict[str, Any]], bool | str]`. Returning `True` gives a generic fallback reason; returning a `str` provides a descriptive reason (e.g., `"Order 123 entered FAILED state"`). The polling loop (Phases 7-8) is responsible for converting `True` to a generic string before constructing the exception.
- **D-03: Constructor** — Positional args matching existing patterns: `StopConditionMetError(resource_id, stop_reason, elapsed, timeout)`.

### StopConditionError

- **D-04: Attributes** — `resource_id` (str) identifies which resource was being polled when the predicate crashed. The wrapped original exception is accessible via `__cause__` using standard `raise StopConditionError(id) from original_exc`.
- **D-05: Constructor** — `StopConditionError(resource_id)` used exclusively via `raise ... from`. No explicit exception parameter — `__cause__` is sufficient and matches Python convention.

### __str__ Formatting

- **D-06: StopConditionMetError** — Pytest-assertion style with labeled sections:
  ```
  Stop condition met for {resource_id} after {elapsed}s (timeout={timeout}s)
  Stop reason: {stop_reason}
  ```
  Matches the existing `Expected:` / `Actual:` pattern used in `DynamoDBWaitTimeoutError`.
- **D-07: StopConditionError** — Includes original exception text inline:
  ```
  Error in stop_when predicate for {resource_id}: {original_exception_text}
  ```
  Where `original_exception_text` is `str(original_exc)`, giving both resource context and the specific failure.
- **D-08: No shared helper yet** — Each class formats `__str__` inline. The shared `__str__` helper with truncation (50 items / 500 chars) is deferred to Phase 9 (Richer Timeout Errors).

### Module Placement

- **D-09: Same file** — Both classes go in `aws_expect/exceptions.py` (not a separate module). 450-line file, ~40 lines added.
- **D-10: Placement** — Insert after `WaitTimeoutError` class definition (~line 18) and before the service-specific subclasses that begin at `S3WaitTimeoutError` (~line 21). This positions them as foundational exception types at the top of the hierarchy.
- **D-11: `__init__.py` integration** — Add both to the `from aws_expect.exceptions import (...)` block and to `__all__` alphabetically. `StopConditionError` goes before `StopConditionMetError` (alphabetical). Both inserted after `S3UnexpectedContentError` and before `S3WaitTimeoutError` in the import list, and similarly in `__all__`.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — EXN-01 (`StopConditionMetError`) and EXN-02 (`StopConditionError`) requirements with field descriptions and hierarchy rules
- `.planning/REQUIREMENTS.md` §Traceability — Shows that Phase 6 maps to EXN-01 and EXN-02 only; richer error enrichment is Phase 9

### Phase Definition
- `.planning/ROADMAP.md` — Phase 6 definition, goal statement, success criteria (3 items), and dependency: "Depends on: Nothing (first phase of v1.3.0)"

### Project-Level Decisions
- `.planning/PROJECT.md` §Key Decisions — `StopConditionMetError` is NOT a `WaitTimeoutError` subclass (locked decision); Exception-direct inheritance for non-timeout errors; `WaitTimeoutError.__init__` direct call pattern

### Research
- `.planning/research/SUMMARY.md` — Recommended approach, critical pitfalls (5 documented), main-condition-wins ordering, shallow-copied state dicts, predicate exception propagation rules
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aws_expect/exceptions.py:11` — `WaitTimeoutError(Exception)` base class with `timeout` attribute — model for attribute documentation pattern
- `aws_expect/exceptions.py:21` — `S3WaitTimeoutError(bucket, key, timeout)` positional constructor — pattern reference for D-03
- `aws_expect/exceptions.py:95` — `DynamoDBWaitTimeoutError` with labeled `Expected entries:` / `Actual (last seen):` message format — pattern reference for D-06
- `aws_expect/exceptions.py:168` — `DynamoDBUnexpectedItemError(Exception)` direct Exception inheritance — precedent for D-01 hierarchy decision

### Established Patterns
- Service-specific timeout errors inherit `WaitTimeoutError`; non-timeout errors inherit `Exception` directly — the two new classes follow the latter pattern
- Exception constructors take positional args, set `self.*` attrs, call `super().__init__(message)` or `WaitTimeoutError.__init__(self, message)` for parent-initialized classes
- Docstrings document all attributes inline (`Attributes:` block) — follow this for both new classes
- `__init__.py` imports are alphabetically ordered within the tuple
- `__all__` includes both exception classes and factory functions, alphabetically ordered

### Integration Points
- `aws_expect/exceptions.py` — Insert `StopConditionError` and `StopConditionMetError` after `WaitTimeoutError` (line ~18), before `S3WaitTimeoutError` (line ~21)
- `aws_expect/__init__.py` — Add imports to line 4–21 `from aws_expect.exceptions import (...)` block and to `__all__` list (line 34–63)
- No changes needed to `expect.py`, `s3.py`, `dynamodb.py`, or any other module — these are consumed by Phases 7–8 only
</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the captured decisions — standard Python exception patterns apply.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 6-Exception Foundation*
*Context gathered: 2026-05-08*
