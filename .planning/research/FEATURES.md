# Feature Research

**Domain:** Stop-condition predicates & richer timeout errors for Python AWS waiter library
**Researched:** 2026-05-08
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `stop_when` callable on all S3 + DynamoDB polling methods | Callers need to abort early when a resource enters a terminal failure state (e.g., S3 object marked FAILED, DynamoDB item deleted mid-wait). Without this, tests waste time waiting for full timeout when success is impossible. | MEDIUM | Must work alongside existing `timeout`/`poll_interval` params. Predicate receives the resource state dict being polled. |
| `StopConditionMetError` exception distinct from `WaitTimeoutError` | Callers must be able to distinguish "waited and it didn't work" from "it can never work because X." Catching `WaitTimeoutError` should NOT catch stop-condition failures — separate hierarchy enables different error-handling paths. | LOW | Already decided in PROJECT.md: not a WaitTimeoutError subclass. Needs to carry the predicate's return value or a descriptive message, plus the state dict that triggered it. |
| Structured `expected`/`actual` in ALL `WaitTimeoutError.__str__` | Users debugging timeout failures need to see what was expected and what was actually observed. Currently some exceptions (e.g., `S3WaitTimeoutError` from `to_exist` without entries) only show the resource path but not _why_ — no expected vs actual. | MEDIUM | Must not break existing code that parses `str(e)`. Add fields, enhance `__str__` with a structured multi-line format. |
| Stop-condition fired _before_ next sleep, not after | If the predicate detects a terminal state, the exception should be raised immediately — not after sleeping `poll_interval` seconds. This is the common-sense behavior; sleep-and-then-check is a well-known polling antipattern. | LOW | Already follows existing pattern: all current polling loops check the deadline _before_ sleeping, so adding a stop check at the same point is natural. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Typed state dict (`TypedDict` per service) for `stop_when` predicate | Python developers expect type hints. A typed `S3ObjectState` / `DynamoDBItemState` dict lets IDEs autocomplete and type-check the predicate function. No other Python polling library does this. | MEDIUM | Requires defining `TypedDict` classes. Must be backward-compatible (plain dict also accepted). Existing `_utils.py` already uses typed dicts via `mypy_boto3` stubs. |
| `stop_when` carries predicate return value in exception | Tenacity's `RetryCallState` carries `outcome` but not the predicate's own return value. Capturing what the predicate returned (e.g., a reason string) lets callers understand _why_ the stop fired without parsing the state dict. | LOW | Simple: store `stop_reason` on `StopConditionMetError`. If predicate returns non-bool, use it as the reason; if returns `True`, default to `"stop_when predicate returned True"`. |
| `StopConditionMetError` carries the remaining timeout | Debugging: "it fired at 12s out of 30s" is more actionable than just "predicate returned True." | LOW | Store `elapsed: float` and `timeout: float` on the exception. One subtraction. |
| Error messages align with pytest assertion style (`assert x == y` → `E assert ...`) | Python developers already understand this format. Using a similar "expected:\n  ...\nactual:\n  ..." layout reduces cognitive load. | LOW | Design `__str__` layout once in `WaitTimeoutError` base, reuse in all subclasses. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| JMESPath-based acceptors (like boto3's waiter model) | "Make it like the AWS SDK" | JMESPath adds a dependency, requires users to learn a query language for a single feature, and overcomplicates the simple `callable(state) -> bool` pattern. boto3 already has JMESPath acceptors for native waiters; aws-expect's value is Pythonic callables. | Keep `stop_when` as `Callable[[dict], bool]`. Simple, zero-dependency, Pythonic. |
| `stop_when` modifying `poll_interval` or timeout | "Make the predicate change polling behavior" | Conflates two concerns: _when to stop_ vs _how fast to poll_. Would require the predicate to return a complex union type (`bool | PollingConfig`), making the API confusing. | Separate `stop_when` (termination condition) from `poll_interval` (polling cadence). If a user needs adaptive polling, they adjust `poll_interval` themselves. |
| Auto-detecting "FAILED" states without caller input | "The library should know when to give up" | AWS resource state machines differ by service, resource type, and even account configuration. Hardcoding "FAILED" checks creates false positives and maintenance burden. | Let callers define their domain-specific failure conditions via `stop_when`. The library remains a framework, not an oracle. |
| `stop_when` on native-boto3-waiter methods (e.g., `to_exist` without entries, `to_not_exist`) | "Consistency across all methods" | These methods delegate to boto3's `get_waiter().wait()`, which blocks internally and doesn't expose per-iteration hooks. Adding `stop_when` would require rewriting them as custom polling loops — duplicating what boto3 already does well. | Document that `stop_when` is only available on methods using custom polling (those with `entries` or content checking). For native-waiter methods, the overhead of custom polling exceeds the benefit of early termination for simple existence checks. |
| Composable `stop_when` with `&`/`|` operators (like tenacity) | "Multiple stop conditions" | Adds complexity for a niche use case. Users can compose conditions in their predicate: `lambda s: is_failed(s) or is_deleted(s)`. A simple callable is Turing-complete. | Keep `stop_when` as a single callable. Composition happens in user code, not the library. |

## Feature Dependencies

```
stop_when parameter on polling methods
    ├──requires──> StopConditionMetError exception class
    ├──requires──> State dict definition (per service/method)
    └──enhances──> Existing polling loop pattern (deadline-based)

Richer timeout error messages
    ├──requires──> Structured __str__ layout decision
    ├──requires──> expected/actual fields on all WaitTimeoutError subclasses
    └──conflicts──> None (additive change to exception messages)

StopConditionMetError
    ├──requires──> Separate from WaitTimeoutError hierarchy (design decision)
    └──requires──> Carries stop reason + state dict + timing info
```

### Dependency Notes

- **`stop_when` requires `StopConditionMetError`:** The predicate needs an exception to raise. Must define the exception class first, then add the parameter.
- **`stop_when` requires state dict definition:** Each polling method exposes different state (S3 body vs DynamoDB item vs table status). Need to define what `state` dict the predicate receives per method.
- **Richer error messages conflict with nothing:** This is an additive change. Existing fields stay; `__str__` becomes more informative. No API breakage.
- **`stop_when` enhances existing polling loops:** All polling methods already follow `deadline = monotonic() + timeout; while True: check; if remaining <= 0: raise`. Adding a `stop_when` check before the remaining-time check is a 2-line addition per loop.

## Feature State Dict Design

### Per-Method State Available to `stop_when`

| Method | State Dict Keys | Notes |
|--------|----------------|-------|
| `S3ObjectExpectation._poll_for_entries` | `bucket: str, key: str, exists: bool, body: dict\|None` | `body` is parsed JSON or None if not found/non-JSON |
| `S3ObjectExpectation.to_have_content` | `bucket: str, key: str, exists: bool, body: dict\|None, last_body: dict\|None` | `last_body` is the most recent parseable body; `body` is current poll result |
| `DynamoDBItemExpectation.to_exist` | `table_name: str, key: dict, exists: bool, item: dict\|None, entries_match: bool` | `entries_match` only present when `entries` param given |
| `DynamoDBItemExpectation.to_have_numeric_value_close_to` | `table_name: str, key: dict, field: str, exists: bool, item: dict\|None, value: float\|None, expected: float, delta: float` | `value` is None if field absent |
| `DynamoDBItemExpectation.to_be_empty` | `table_name: str, item_count: int` | Simple count-based |
| `DynamoDBItemExpectation.to_be_not_empty` | `table_name: str, item_count: int` | Simple count-based |
| `DynamoDBItemExpectation.to_find_item` | `table_name: str, entries: dict, scan_so_far: list[dict]` | Items scanned in current pass |
| `DynamoDBItemExpectation.to_not_exist` | `table_name: str, key: dict, exists: bool, item: dict\|None` | `item` is the current item if it still exists |
| `DynamoDBTableExpectation.to_exist` | `table_name: str, exists: bool, status: str\|None` | `status` is TableStatus if table exists |
| `DynamoDBTableExpectation.to_not_exist` | `table_name: str, exists: bool` | Simple boolean |

### State Dict Design Decision

**Recommendation:** Use plain `dict[str, Any]` with documented keys rather than `TypedDict`. Rationale:
1. Different methods expose different keys — `TypedDict` would require a class per method (10+ classes) with significant maintenance burden.
2. Users define ad-hoc predicates; typed dicts add friction without safety benefit since callers already know what method they're calling.
3. Tenacity uses `RetryCallState` (a concrete class with typed attributes) — this is a cleaner pattern for v2 but overengineered for v1.3.0.
4. Document the state dict keys in each method's docstring with the `stop_when` parameter docs.

If the library grows to 5+ services with `stop_when`, a `TypedDict` per service family (e.g., `S3PollState`, `DynamoDBPollState`) becomes warranted.

## Error Message Design

### Current State (Pre-Enrichment)

| Exception | Has `expected`? | Has `actual`? | `__str__` Quality |
|-----------|----------------|---------------|-------------------|
| `S3WaitTimeoutError` (to_exist, no entries) | ❌ | ❌ | `"Timed out after 30s waiting for s3://bucket/key"` — missing _why_ |
| `S3WaitTimeoutError` (to_exist, with entries) | ❌ (in message) | ❌ | Same format — doesn't show entries that didn't match |
| `S3ContentWaitTimeoutError` | ✅ | ✅ | Already good: shows expected and last body |
| `DynamoDBWaitTimeoutError` | ✅ (optional) | ✅ (optional) | Varies: good when entries/actual present, bare when not |
| `DynamoDBFindItemTimeoutError` | ✅ | ✅ | Good |
| `LambdaWaitTimeoutError` | ❌ | ❌ | Bare: `"Timed out after 30s waiting for Lambda function 'foo'"` |
| `LambdaInvocableTimeoutError` | ✅ | ✅ | Good |
| `SQSWaitTimeoutError` | ✅ (body) | ✅ (actual) | Good |
| `SQSEventWaitTimeoutError` | ✅ (event) | ✅ (actual) | Good |
| `AggregateWaitTimeoutError` | ❌ | ❌ | Shows failure summary but not per-error expected/actual |

### Target State (Post-Enrichment)

**Design principle:** Every `WaitTimeoutError` subclass must make the failure _self-documenting_. A developer reading the error output should understand what was expected, what was found, and why the wait failed — without reading the test code.

**`__str__` format:**

```
Timed out after {timeout}s waiting for {resource_description}

Expected:
  {expected_repr}

Actual (last seen):
  {actual_repr}
```

When `expected` or `actual` is not applicable, omit that section.

**Required changes per exception:**

| Exception | Add `expected` field? | Add `actual` field? | Notes |
|-----------|----------------------|--------------------|-------|
| `S3WaitTimeoutError` | Add optional `expected: dict\|None` | Add optional `actual: dict\|None` | `to_exist(entries=...)` fills both; `to_exist()` fills neither |
| `DynamoDBWaitTimeoutError` | Already has `entries` (expected) | Already has `actual` | Enhance `__str__` to use the structured format. `to_be_empty`/`to_be_not_empty`/`to_not_exist` to include meaningful expected/actual |
| `LambdaWaitTimeoutError` | Add optional `expected_state: str` | Add optional `actual_state: str\|None` | Show expected vs actual function state |
| `AggregateWaitTimeoutError` | N/A (aggregate) | N/A | Per-error `__str__` already carries details. No change needed at aggregate level. |

**Important constraint:** All new fields must be optional (`| None`) to maintain backward compatibility. Code that catches `S3WaitTimeoutError` and accesses `.bucket`, `.key`, `.timeout` must continue working. New `expected` and `actual` fields are additive — existing attributes and their types do not change.

## Real-World Use Cases (Motivating Examples)

### Use Case 1: S3 Object Enters FAILED State
```python
def is_failed(state: dict) -> bool:
    """Stop waiting if the object metadata indicates processing failed."""
    body = state.get("body", {})
    return body.get("status") == "FAILED"

expect_s3(obj).to_have_content(
    {"status": "COMPLETED"},
    timeout=300,
    stop_when=is_failed,
)
# If object appears with {"status": "FAILED"}, raises StopConditionMetError
# instead of waiting full 300s.
```

### Use Case 2: DynamoDB Item Deleted Mid-Wait
```python
def item_disappeared(state: dict) -> bool:
    """Stop if the item we're waiting for gets deleted."""
    return not state.get("exists", True)

expect_dynamodb_item(table).to_exist(
    key={"pk": "order-123"},
    entries={"status": "PROCESSED"},
    timeout=60,
    stop_when=item_disappeared,
)
# If item is deleted before timeout, raises StopConditionMetError immediately.
```

### Use Case 3: Custom Error Reason
```python
def check(state: dict) -> str | bool:
    """Return reason string for richer error."""
    item = state.get("item", {})
    status = item.get("status")
    if status == "FAILED":
        return f"Order {item.get('id')} entered FAILED state with error: {item.get('error')}"
    return False  # keep polling

try:
    expect_dynamodb_item(table).to_exist(
        key={"pk": "order-123"},
        timeout=60,
        stop_when=check,
    )
except StopConditionMetError as e:
    print(e.stop_reason)  # "Order order-123 entered FAILED state with error: ..."
```

## Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Phase |
|---------|------------|---------------------|----------|-------|
| `stop_when` on S3 `_poll_for_entries` + `to_have_content` | HIGH | LOW — 2 lines per loop | P1 | Phase 1 |
| `stop_when` on all DynamoDB polling methods | HIGH | LOW — 2 lines per loop | P1 | Phase 1 |
| `StopConditionMetError` exception class | HIGH | LOW — ~30 lines | P1 | Phase 1 |
| Richer `__str__` on all `WaitTimeoutError` subclasses | HIGH | MEDIUM — touches 6+ exception classes | P1 | Phase 2 |
| Add `expected`/`actual` fields to exceptions that lack them | MEDIUM | MEDIUM — backward compat careful | P1 | Phase 2 |
| State dict documentation in docstrings | MEDIUM | LOW — docstring updates | P2 | Phase 1 |
| TypedDict state types | LOW | MEDIUM — 10+ TypedDict classes | P3 | Defer |
| Composable `stop_when` (`&`/`|`) | LOW | HIGH — composable predicate infra | P3 | Defer |

## Competitor Feature Analysis

| Feature | tenacity | polling2 | boto3 waiters | aws-expect (v1.3.0 target) |
|---------|----------|----------|---------------|---------------------------|
| Stop-condition callable | ✅ `stop` parameter | ❌ (success-only) | ✅ `failure` acceptors (JMESPath) | ✅ `stop_when` callable |
| Stop-condition exception | ❌ (just stops retrying) | N/A | ✅ `WaiterError` | ✅ `StopConditionMetError` |
| Rich context in error | ✅ `RetryCallState` in callbacks | ✅ `.values` + `.last` | ❌ (opaque WaiterError) | ✅ `expected`/`actual` in all errors |
| Typed state for callbacks | ✅ `RetryCallState` object | ❌ (raw return value) | ✅ JMESPath on JSON response | 🟡 plain dict (TypedDict deferred) |
| Predicate return as error context | ❌ | N/A | N/A | ✅ `stop_reason` on exception |
| Composable conditions | ✅ `&`/`|` on stop/wait/retry | ❌ | ❌ | ❌ (deferred) |

## Sources

- [boto3 waiter model JSON](https://github.com/boto/botocore/blob/develop/botocore/data/s3/2006-03-01/waiters-2.json) — 3-state acceptors (success/failure/retry). HIGH confidence.
- [tenacity stop.py](https://github.com/jd/tenacity/blob/main/tenacity/stop.py) — Composable `StopBaseT` (Callable or class). HIGH confidence.
- [tenacity docs: retry_if_result](https://context7.com/jd/tenacity/llms.txt) — Predicate-based retry with `retry_if_result`. HIGH confidence.
- [polling2 API docs](https://polling2.readthedocs.io/en/latest/api.html) — `check_success` callback (success-only, no failure predicate). HIGH confidence.
- [polling2 source](https://github.com/ddmee/polling2/blob/master/polling2.py) — `TimeoutException`/`MaxCallException` with `.values`/`.last`. HIGH confidence.
- [retry (invl) source](https://github.com/invl/retry/blob/master/retry/api.py) — Exception-only retry, no predicate-based stop. HIGH confidence.
- aws-expect codebase (`aws_expect/exceptions.py`, `s3.py`, `dynamodb.py`) — Existing polling pattern and `DynamoDBNonNumericFieldError` as pre-existing early-stop pattern. HIGH confidence.
- PROJECT.md key decision: `StopConditionMetError` is NOT a `WaitTimeoutError` subclass. HIGH confidence.

---
*Feature research for: aws-expect v1.3.0 Smart Polling & Richer Errors*
*Researched: 2026-05-08*
