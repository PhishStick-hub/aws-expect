# Architecture Research: Stop-Condition Predicates & Richer Timeout Errors

**Domain:** Python AWS waiter library (aws-expect)
**Researched:** 2026-05-08
**Confidence:** HIGH

## Executive Summary

Two new capabilities integrate into the existing aws-expect architecture: a `stop_when` predicate parameter on S3 and DynamoDB polling methods, and enriched `expected`/`actual` attributes across all `WaitTimeoutError` subclasses. The integration touches the exception hierarchy, the polling-loop pattern, and method signatures — all additive, no existing API breaks.

## System Overview (Current → Target)

```
┌────────────────────────────────────────────────────────────────────┐
│                        aws_expect Public API                        │
│  expect_s3 / expect_dynamodb_item / expect_dynamodb_table / ...    │
├────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌───────────────────┐  ┌───────────────┐   │
│  │ S3Object         │  │ DynamoDBItem      │  │ DynamoDBTable │   │
│  │ Expectation      │  │ Expectation       │  │ Expectation   │   │
│  │                  │  │                   │  │               │   │
│  │ to_exist         │  │ to_exist          │  │ to_exist      │   │
│  │ to_not_exist     │  │ to_not_exist      │  │ to_not_exist  │   │
│  │ to_have_content  │  │ to_have_numeric   │  │               │   │
│  │ to_not_have_cont │  │ to_be_empty       │  │               │   │
│  │ _poll_for_entries│  │ to_be_not_empty   │  │               │   │
│  │                  │  │ to_find_item      │  │               │   │
│  └────────┬─────────┘  └────────┬──────────┘  └───────┬───────┘   │
│           │                     │                       │          │
│  ┌────────┴─────────────────────┴───────────────────────┴───────┐  │
│  │                     Polling Loop Pattern                      │  │
│  │  fetch → check condition → check stop_when → sleep/repeat    │  │
│  └─────────────────────────────┬────────────────────────────────┘  │
│                                │                                   │
│  ┌─────────────────────────────┴────────────────────────────────┐  │
│  │                    Exception Hierarchy                        │  │
│  │  Exception                                                    │  │
│  │   ├── WaitTimeoutError           ← richer: +expected/+actual  │  │
│  │   │   ├── S3WaitTimeoutError     ← richer                    │  │
│  │   │   ├── S3ContentWaitTimeoutError  ✓ already has them      │  │
│  │   │   ├── DynamoDBWaitTimeoutError   ✓ already has entries   │  │
│  │   │   ├── LambdaWaitTimeoutError     ← richer                │  │
│  │   │   ├── LambdaInvocableTimeoutError ✓ already has them     │  │
│  │   │   ├── SQSWaitTimeoutError        ✓ already has body      │  │
│  │   │   ├── SQSEventWaitTimeoutError   ✓ already has event     │  │
│  │   │   └── AggregateWaitTimeoutError  (different structure)   │  │
│  │   ├── StopConditionMetError       ★ NEW — NOT WaitTimeout   │  │
│  │   ├── S3UnexpectedContentError                                │  │
│  │   ├── DynamoDBUnexpectedItemError                              │  │
│  │   ├── DynamoDBNonNumericFieldError                             │  │
│  │   └── ...                                                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                │                                   │
│  ┌─────────────────────────────┴────────────────────────────────┐  │
│  │                    Shared Utilities (_utils.py)               │  │
│  │  _deep_matches / _matches_entries / _compute_delay /         │  │
│  │  _build_waiter_config                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

## Integration Point: stop_when in the Polling Loop

### The Universal Insertion Point

Every custom polling loop in `s3.py` and `dynamodb.py` follows this pattern:

```python
delay = _compute_delay(poll_interval)
deadline = time.monotonic() + timeout

while True:
    state = _fetch_resource()       # ← fetch current state
    if _condition_met(state):       # ← check success
        return state
    remaining = deadline - time.monotonic()
    if remaining <= 0:              # ← timeout
        raise SpecificError(...)
    time.sleep(min(delay, remaining))
```

`stop_when` inserts **between** the resource fetch and the condition check. This ordering matters: if the condition is already met, we return immediately — the stop predicate is never consulted for an already-successful state.

```python
while True:
    state = _fetch_resource()
    
    # ★ NEW: stop-condition check (before success check)
    if stop_when is not None and stop_when(state):
        raise StopConditionMetError(
            resource_id=...,
            stop_state=state,
            timeout=timeout,
        )
    
    if _condition_met(state):
        return state
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SpecificError(...)
    time.sleep(min(delay, remaining))
```

**Rationale for ordering (stop_when BEFORE condition check):** When a resource exists but is in a terminal failure state, the caller wants `StopConditionMetError` raised immediately — not polled again only to time out. If the condition IS already satisfied on this poll, we return without checking `stop_when`. This matches user intent: "wait for X, but stop early if Y" — "X happened first" is a success.

### What stop_when Receives per Method

The `stop_when` callable signature is `(state: dict[str, Any]) -> bool`. The state dict varies by method:

| Module | Method | State Dict Passed | Notes |
|--------|--------|-------------------|-------|
| `s3.py` | `_poll_for_entries` | parsed JSON body `dict` or `None` | Used by `to_exist(entries=...)`. `None` when object doesn't exist or body is non-JSON. |
| `s3.py` | `to_have_content` | parsed JSON body `dict` or `None` | `None` when object doesn't exist or body is invalid. |
| `dynamodb.py` | `to_exist` | item `dict` or `None` | `None` when `get_item` returns no Item. |
| `dynamodb.py` | `to_have_numeric_value_close_to` | item `dict` or `None` | Same as `to_exist`. |
| `dynamodb.py` | `to_be_empty` | `{"count": int}` | Scan returns count. |
| `dynamodb.py` | `to_be_not_empty` | `{"count": int}` | Scan returns count. |
| `dynamodb.py` | `to_find_item` | `{"current_item": dict, "items_seen_this_pass": int}` | Per-item in paginated scan; updated on each item yielded. |
| `dynamodb.py` | `to_not_exist` (item) | item `dict` or `None` | `None` when item is deleted. |
| `dynamodb.py` | `to_exist` (table) | `TableDescriptionTypeDef` or `None` | `None` on ResourceNotFoundException. |
| `dynamodb.py` | `to_not_exist` (table) | `TableDescriptionTypeDef` or `None` | `None` when table is deleted. |

**Special case — `to_find_item`:** This method paginates through all items on each poll. `stop_when` is evaluated per-item (the stop predicate receives that item). If `stop_when` fires for any item, the waiter aborts. The per-item state is `{"current_item": <item dict>, "items_seen_this_pass": <int>}`, giving the predicate visibility into progress without having to track it externally.

### Methods NOT Getting stop_when

These use native boto3 waiters (no custom polling loop) or are single-check (not polling):

| Method | Reason |
|--------|--------|
| `S3ObjectExpectation.to_exist(entries=None)` | Native boto3 `object_exists` waiter |
| `S3ObjectExpectation.to_not_exist()` | Native boto3 `object_not_exists` waiter |
| `DynamoDBItemExpectation.to_not_find_item()` | Single scan after delay (not a polling loop) |
| `S3ObjectExpectation.to_not_have_content()` | Single check after delay (not a polling loop) |

**Decision:** These methods do NOT get `stop_when`. Converting native waiters to custom loops solely for `stop_when` adds risk and complexity for minimal benefit. This is documented in method docstrings.

## Exception Hierarchy Changes

### New: StopConditionMetError

```python
class StopConditionMetError(Exception):
    """Raised when a stop_when predicate returns True during polling.
    
    Does NOT inherit WaitTimeoutError — callers must catch this explicitly.
    This is intentional: a stop-condition trigger is semantically different
    from a timeout, and callers should not accidentally catch it with a
    broad except WaitTimeoutError.
    """
    
    def __init__(
        self,
        resource_identifier: str,      # e.g. "s3://bucket/key" or "table:item"
        stop_state: dict[str, Any] | None,  # the state dict that triggered the stop
        timeout: float,
        poll_count: int,               # how many polls executed before stopping
        elapsed: float,                # wall-clock seconds elapsed
    ) -> None:
        ...

# Minimal __str__: clear resource identifier + state summary
# "Stop condition met for s3://my-bucket/report.csv after 3 polls (4.2s elapsed):
#  {'status': 'FAILED', 'error': 'invalid format'}"
```

**Key design properties:**
- `resource_identifier`: Human-readable resource string (e.g. `"s3://bucket/key"`, `"table Users, key={'pk':'u1'}"`). Consistent format with existing error messages.
- `stop_state`: The exact dict that was passed to `stop_when` when it returned True. Allows introspection of what triggered the stop.
- `poll_count` / `elapsed`: Timing info for debugging how quickly the condition fired.
- **NOT a `WaitTimeoutError`** — per PROJECT.md Key Decisions table and confirmed by existing codebase pattern (non-timeout errors like `DynamoDBNonNumericFieldError`, `LambdaResponseMismatchError` all inherit `Exception` directly).

### Modified: S3WaitTimeoutError

Currently stores `bucket`, `key`, `timeout`, no `expected`/`actual`. Must add:

```python
class S3WaitTimeoutError(WaitTimeoutError):
    def __init__(
        self,
        bucket: str,
        key: str,
        timeout: float,
        expected: str = "",       # ★ NEW: description of what was expected
        actual: str = "",         # ★ NEW: description of what was found
    ) -> None:
        self.bucket = bucket
        self.key = key
        self.timeout = timeout
        self.expected = expected  # ★ NEW
        self.actual = actual      # ★ NEW
        msg = f"Timed out after {timeout}s waiting for s3://{bucket}/{key}"
        if expected:
            msg += f"\n\nExpected:\n  {expected}"
        if actual:
            msg += f"\n\nActual:\n  {actual}"
        super().__init__(msg)
```

**Call sites that need updating:**
1. `s3.py line 96` — `to_exist(entries=None)` timeout: `expected="object to exist"`, `actual="object not found"`
2. `s3.py line 134` — `_poll_for_entries` timeout: `expected=f"entries={entries!r}"`, `actual="last body: None"` 
3. `s3.py line 225` — `to_not_exist` timeout: `expected="object to not exist"`, `actual="object still exists"`

### Modified: LambdaWaitTimeoutError

Currently stores `function_name`, `timeout`, no `expected`/`actual`. Add:

```python
class LambdaWaitTimeoutError(WaitTimeoutError):
    def __init__(
        self,
        function_name: str,
        timeout: float,
        expected: str = "",       # ★ NEW
        actual: str = "",         # ★ NEW
    ) -> None:
        ...
```

**Call sites to update (in lambda_function.py):**
1. Line 67 — `to_exist` timeout
2. Line 104 — `to_not_exist` timeout
3. Line 137 — `to_be_active` timeout
4. Line 172 — `to_be_updated` timeout
5. Line 231 — `to_be_invocable(entries=None)` timeout

### No Changes Needed (Already Satisfy expected/actual)

| Exception | Has `expected` | Has `actual` | Notes |
|-----------|---------------|-------------|-------|
| `S3ContentWaitTimeoutError` | ✓ | ✓ | Already stores `self.expected`, `self.actual` |
| `DynamoDBWaitTimeoutError` | via `entries` | ✓ | Stores `self.entries` (≈ expected), `self.actual` |
| `DynamoDBFindItemTimeoutError` | ✓ | ✓ | Already perfect |
| `LambdaInvocableTimeoutError` | ✓ | ✓ | Already perfect |
| `SQSWaitTimeoutError` | via `body` | ✓ | Stores `self.body` (≈ expected), `self.actual` |
| `SQSEventWaitTimeoutError` | via `event` | ✓ | Stores `self.event` (≈ expected), `self.actual` |
| `AggregateWaitTimeoutError` | N/A | N/A | Different structure — aggregation, not single expectation |

**Decision:** Do NOT rename `entries`/`body`/`event` to `expected` in `DynamoDBWaitTimeoutError`, `SQSWaitTimeoutError`, `SQSEventWaitTimeoutError`. These are existing public attributes with callers that may depend on the names. Add `expected` as a property alias if needed, but the `__str__` already includes structured comparison output.

## Method Signature Changes

### Pattern for Adding stop_when

Every S3 and DynamoDB polling method gains a keyword-only parameter:

```python
def to_exist(
    self,
    key: dict[str, Any],
    timeout: float = 30,
    poll_interval: float = 5,
    entries: dict[str, Any] | None = None,
    *,
    stop_when: Callable[[dict[str, Any]], bool] | None = None,  # ★ NEW
) -> dict[str, Any]:
```

`stop_when` is keyword-only (after `*`) to avoid positional ambiguity and maintain forward compatibility. Position is always last.

### Complete List of Modified Signatures

**S3 (`s3.py`):**
1. `_poll_for_entries(timeout, poll_interval, entries, *, stop_when=None)` — internal method
2. `to_have_content(entries, timeout, poll_interval, *, stop_when=None)` — public method
3. `to_exist(timeout, poll_interval, entries, *, stop_when=None)` — adds kwarg forwarding to internal `_poll_for_entries`

**Note:** `to_exist(entries=None)` using native waiter path does NOT accept `stop_when`. The overload decorators guide callers: passing `stop_when` without `entries` is a no-op with a clear docstring note.

**DynamoDBItem (`dynamodb.py`):**
1. `to_exist(key, timeout, poll_interval, entries, *, stop_when=None)`
2. `to_have_numeric_value_close_to(key, field, expected, delta, timeout, poll_interval, *, stop_when=None)`
3. `to_be_empty(timeout, poll_interval, *, stop_when=None)`
4. `to_be_not_empty(timeout, poll_interval, *, stop_when=None)`
5. `to_find_item(entries, timeout, poll_interval, *, stop_when=None)`
6. `to_not_exist(key, timeout, poll_interval, *, stop_when=None)`

**DynamoDBTable (`dynamodb.py`):**
1. `to_exist(timeout, poll_interval, *, stop_when=None)`
2. `to_not_exist(timeout, poll_interval, *, stop_when=None)`

### Parallel Module Impact

`expect_any` calls through future results — if a `StopConditionMetError` is raised inside a thread, it will propagate through `future.exception()` as a non-`WaitTimeoutError`, so it bubbles up immediately (existing behavior at `parallel.py` line 77 and line 151). **No change needed in parallel.py** — the `isinstance(exc, WaitTimeoutError)` check correctly lets non-timeout exceptions propagate.

`expect_all` similarly: `StopConditionMetError` propagates because it fails the `isinstance(exc, WaitTimeoutError)` check at line 74.

**However:** Callers of `expect_all` / `expect_any` need to be aware that `StopConditionMetError` can now be raised (it was not possible before). This is a documentation concern, not a code change.

## Data Flow: Full Poll Cycle with stop_when

```
Caller invokes:
  expect_s3(obj).to_have_content({"status": "ok"}, stop_when=my_pred)

    ↓
    
S3ObjectExpectation.to_have_content(...)
    │
    │  delay = _compute_delay(poll_interval)
    │  deadline = monotonic() + timeout
    │  last_body = None
    │
    │  ┌─── while True ──────────────────────────────────────┐
    │  │                                                       │
    │  │  body = _fetch_body()                    ← AWS API     │
    │  │       │                                                │
    │  │       ├─ NoSuchKey → body = None                       │
    │  │       ├─ JSON parse error → body = None                │
    │  │       └─ success → body = parsed dict                  │
    │  │                                                        │
    │  │  ★ stop_when check:                                    │
    │  │  if stop_when and stop_when(body):                     │
    │  │      raise StopConditionMetError(                     │
    │  │          "s3://bucket/key", body, timeout,             │
    │  │          poll_count, elapsed                           │
    │  │      )                                                 │
    │  │                                                        │
    │  │  if body and _deep_matches(body, entries):             │
    │  │      return body          ← success                    │
    │  │                                                        │
    │  │  last_body = body                                      │
    │  │                                                        │
    │  │  remaining = deadline - monotonic()                    │
    │  │  if remaining <= 0:                                    │
    │  │      raise S3ContentWaitTimeoutError(                 │
    │  │          bucket, key, entries, last_body, timeout      │
    │  │      )                      ← timeout (already rich)   │
    │  │                                                        │
    │  │  sleep(min(delay, remaining))                          │
    │  │                                                        │
    │  └───────────────────────────────────────────────────────┘
```

## Build Order (Dependency Graph)

```
1. StopConditionMetError        ──── no dependencies
       │
2. S3WaitTimeoutError.expected/actual   ──── dep on step 1 concepts only
       │
3. LambdaWaitTimeoutError.expected/actual ─── dep on step 1 concepts only
       │
4. S3 polling loops + stop_when    ──── dep on steps 1, 2
       │
5. DynamoDBItem polling loops + stop_when ── dep on step 1
       │
6. DynamoDBTable polling loops + stop_when ── dep on step 1
       │
7. __init__.py exports update      ──── dep on steps 1-6
       │
8. Test suite (S3)                 ──── dep on steps 2, 4, 7
       │
9. Test suite (DynamoDB)           ──── dep on steps 5, 6, 7
       │
10. Test suite (Lambda richer errors) ── dep on step 3
```

**Rationale:**
- Exception classes first (they have no runtime deps, only standard library).
- S3 changes before DynamoDB because S3 is the simpler polling loop — establishes the pattern.
- `__init__.py` exports after all modules are done (avoids import errors during incremental implementation).
- Tests last after implementation is stable.

**Parallelization opportunity:** Steps 2 and 3 can run in parallel (both modify exceptions.py, different classes). Steps 5 and 6 can run in parallel (different methods in the same file, but non-overlapping).

## Architectural Patterns

### Pattern 1: Predicate Injection into Polling Loop

**What:** A callable `stop_when(state) -> bool` is injected into the polling loop at a well-defined insertion point. When it returns True, a dedicated exception (`StopConditionMetError`) is raised. The predicate receives the raw resource state, allowing callers to inspect any property.

**When to use:** Whenever a polling waiter should abort early based on resource state that is independent of the success condition. Typical: "wait for deployment to succeed BUT stop if it enters Failed state."

**Trade-offs:**
- Pro: Clean separation — success condition vs. stop condition are independent concerns
- Pro: Caller controls stop logic without subclassing the expectation class
- Con: Predicate runs on every poll (adds per-poll overhead — acceptable for callables that are fast lookups)
- Con: `StopConditionMetError` is not a `WaitTimeoutError` — existing `except WaitTimeoutError` handlers will miss it (by design)

### Pattern 2: Backward-Compatible Signature Extension

**What:** Add a keyword-only parameter at the end of the method signature. Existing positional and keyword calls remain valid. Type checkers enforce the new parameter is keyword-only.

**Example:**
```python
def to_exist(
    self,
    key: dict[str, Any],
    timeout: float = 30,
    poll_interval: float = 5,
    entries: dict[str, Any] | None = None,
    *,
    stop_when: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
```

**Trade-offs:**
- Pro: Zero breakage — all existing calls compile and behave identically
- Pro: Type-safe — mypy/ty enforces keyword-only
- Con: Signature grows longer (mitigated by sensible defaults)

### Pattern 3: Context-Rich Exceptions

**What:** Every exception instance carries structured attributes (`expected`, `actual`, `resource_identifier`) that callers can inspect programmatically, not just read from `__str__`.

**When to use:** Any exception raised from a waiter where the caller might want to assert on specific properties of the failure (e.g., "did it time out because the item was missing, or because it had the wrong fields?").

**Anti-pattern avoided:** Don't force callers to parse error message strings. Always store structured data on exception attributes.

## Anti-Patterns to Avoid

### Anti-Pattern 1: stop_when with Side Effects

**What people do:** Use `stop_when` to mutate external state or perform additional AWS calls.

```python
# BAD: side effect in stop predicate
count = 0
def count_and_check(state):
    global count
    count += 1
    return state and state.get("status") == "FAILED"

expect_s3(obj).to_have_content(entries, stop_when=count_and_check)
```

**Why wrong:** The predicate runs on every poll iteration — side effects accumulate unpredictably. If the predicate raises, the polling loop terminates with an unhandled exception (not `StopConditionMetError`).

**Do this instead:** Keep predicates pure. If counting is needed, do it outside the predicate:

```python
# GOOD: pure predicate
def is_failed(state):
    return state is not None and state.get("status") == "FAILED"

expect_s3(obj).to_have_content(entries, stop_when=is_failed)
```

### Anti-Pattern 2: Overly Broad except WaitTimeoutError

**What people do:** Catch `WaitTimeoutError` expecting to handle ALL failure modes.

```python
try:
    expect_s3(obj).to_have_content({"status": "ok"}, stop_when=is_failed)
except WaitTimeoutError:
    # handles timeout, but MISSES StopConditionMetError
    retry()
```

**Why wrong:** `StopConditionMetError` is NOT a `WaitTimeoutError` subclass. The handler above silently ignores stop-condition triggers, potentially retrying an operation that should have been aborted.

**Do this instead:** Handle both:

```python
from aws_expect import StopConditionMetError, WaitTimeoutError

try:
    expect_s3(obj).to_have_content({"status": "ok"}, stop_when=is_failed)
except StopConditionMetError as e:
    # terminal failure detected — don't retry
    raise
except WaitTimeoutError:
    # genuine timeout — may retry
    retry()
```

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `exceptions.py` | All exception types including new `StopConditionMetError` | `s3.py`, `dynamodb.py`, `lambda_function.py`, `parallel.py` |
| `s3.py` | S3 polling loops with `stop_when` support | `exceptions.py`, `_utils.py`, boto3 S3 client |
| `dynamodb.py` | DynamoDB item + table polling loops with `stop_when` | `exceptions.py`, `_utils.py`, boto3 DynamoDB resource/client |
| `_utils.py` | Shared matching/delay utilities | All expectation modules |
| `parallel.py` | Thread-pool orchestration; passes through `StopConditionMetError` | `exceptions.py` |
| `__init__.py` | Public API export surface | All modules |
| `expect.py` | Factory functions (no changes needed) | `s3.py`, `dynamodb.py`, etc. |

## Scaling Considerations

| Scale | Concern | Approach |
|-------|---------|----------|
| Few waiters, short timeouts | Predicate overhead negligible | Direct `callable(state)` in loop |
| Many concurrent waiters (expect_all) | `StopConditionMetError` propagation through thread pool | Already handled — non-`WaitTimeoutError` exceptions bubble up immediately |
| Large state dicts passed to `stop_when` | Memory — state dicts are shared, not copied | Acceptable — state dicts are already held by polling loop |
| Deeply nested stop predicates | Stack depth on recursion | Callers own this; library just calls `stop_when(state)` — no recursion from our side |

## Sources

- Existing codebase: `aws_expect/exceptions.py`, `aws_expect/s3.py`, `aws_expect/dynamodb.py` — HIGH confidence (primary source)
- `.planning/PROJECT.md` — HIGH confidence (project requirements and Key Decisions)
- Key Decision: `StopConditionMetError` is NOT a `WaitTimeoutError` subclass — confirmed in PROJECT.md

---

*Architecture research for: aws-expect v1.3.0 — stop-condition predicates and richer timeout errors*
*Researched: 2026-05-08*
*Confidence: HIGH — all findings verified against the live codebase*
