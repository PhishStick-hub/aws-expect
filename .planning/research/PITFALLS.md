# Pitfalls Research

**Domain:** Python AWS waiter library — adding `stop_when` predicates and richer timeout error messages
**Researched:** 2026-05-08
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Exceptions raised inside the `stop_when` callable are silently swallowed

**What goes wrong:**
A user passes `stop_when=lambda state: state["status"] == "DONE"`. The `state` dict lacks the key `"status"`, the lambda raises `KeyError`, and the polling loop continues as if the predicate returned `False`. The user never discovers the bug — the waiter just times out with a cryptic `WaitTimeoutError` that says nothing about the predicate failure.

**Why it happens:**
The natural implementation wraps the predicate call in `try/except` to prevent an exception from crashing the polling loop. But without re-raising or logging, the exception is lost. Tenacity's `stop` callback *propagates* exceptions from predicates — the design rationale is that a predicate that raises means the caller's logic is broken, and silently continuing is worse than crashing.

**How to avoid:**
Do NOT catch exceptions in `stop_when`. Let them propagate naturally. The only wrapping needed is wrapping the exception in a new exception type that identifies it as a `stop_when` failure:

```python
class StopConditionError(Exception):
    """Raised when the stop_when predicate raises an exception."""
    def __init__(self, predicate_exception: Exception) -> None:
        self.predicate_exception = predicate_exception
        super().__init__(
            f"stop_when predicate raised {type(predicate_exception).__name__}: "
            f"{predicate_exception}"
        )
```

**Warning signs:**
- A `try/except Exception` around the predicate call in the polling loop
- Logging as the only action after catching
- Timeout errors where the predicate clearly should have fired if it worked

**Phase to address:**
Phase 1 (implementation) — must be designed into the first `stop_when` polling loop.

---

### Pitfall 2: Confusing `StopConditionMetError` semantics — "stop if true" vs "abort if true"

**What goes wrong:**
The method is named `stop_when`. The user writes `stop_when=lambda state: state.get("error")` and expects polling to stop when `error` is truthy. But the implementation checks `if stop_when_result: raise StopConditionMetError(...)`. If the predicate returns a non-`bool` truthy value, it behaves unexpectedly. Worse, if the predicate returns `True` but the user meant "stop polling and consider it a success" (not an error), the semantics are wrong.

**Why it happens:**
The name `stop_when` is ambiguous — it doesn't say what happens *after* stopping. Is it an error? A success? A neutral abort? The tenacity library uses separate keywords: `stop` (abort retries), `retry` (should I retry?), and `reraise` (re-raise the last exception). The proposed `StopConditionMetError` name implies an error, but the parameter name `stop_when` implies a generic stop.

**How to avoid:**
Two design decisions must be locked in:

1. **`stop_when` returns `bool`** — document that only `True`/`False` are expected. Type-hint as `Callable[[dict[str, Any]], bool]`.
2. **`StopConditionMetError` is always raised when `stop_when` returns `True`** — no option to treat it as success. The error message MUST include what the predicate received to debug *why* it fired.

For the case where a user wants "stop and succeed," they should use the existing methods without `stop_when`. `stop_when` is exclusively for "something is wrong, stop polling before timeout."

**Warning signs:**
- Predicates returning non-`bool` values (e.g., `None`, the state dict, a string)
- Confusion in test names or docstrings about success vs. error semantics
- A parameter like `stop_when_is_error: bool = True` that tries to handle both cases

**Phase to address:**
Phase 0 (design/API contract) — must be unambiguous before implementation starts.

---

### Pitfall 3: `StopConditionMetError` not catching correctly because it inherits from `Exception` directly

**What goes wrong:**
A test or production code does:

```python
try:
    expect_s3(obj).to_exist(stop_when=my_stop)
except WaitTimeoutError:
    # clean up
```

`stop_when` fires, `StopConditionMetError` is raised, but it is NOT caught by `except WaitTimeoutError` because `StopConditionMetError` inherits from `Exception` directly (as decided in PROJECT.md Key Decisions). The cleanup code never runs, and the error propagates as an unhandled exception. This is by *design* per the project decision, but it's a pitfall for callers who don't know the distinction.

**Why it happens:**
The decision to make `StopConditionMetError` inherit from `Exception` (not `WaitTimeoutError`) is correct — a stop-condition trigger is semantically different from a timeout. But existing codebases that `except WaitTimeoutError` will miss it.

**How to avoid:**
1. Prominently document in the `StopConditionMetError` docstring that it does NOT inherit `WaitTimeoutError`.
2. In the README, show a combined catch pattern:
   ```python
   except (WaitTimeoutError, StopConditionMetError) as e:
   ```
3. Consider making the `stop_when` docstring in each method explicitly warn: "Raises `StopConditionMetError` which is NOT a subclass of `WaitTimeoutError`."
4. Test that `StopConditionMetError` is NOT caught by `except WaitTimeoutError` — make this a test case.

**Warning signs:**
- Users reporting "unhandled exception" when `stop_when` fires in code that already catches `WaitTimeoutError`
- Confusion in issues/PRs about the inheritance hierarchy
- Reviewers asking "Shouldn't this inherit WaitTimeoutError?"

**Phase to address:**
Phase 1 (implementation) — the `StopConditionMetError` class definition; Phase 3 (testing) — test the catch pattern explicitly.

---

### Pitfall 4: `stop_when` predicate receives mutable state that gets mutated by the predicate

**What goes wrong:**
The polling loop fetches `state = self._table.get_item(Key=key)["Item"]`, passes it to `stop_when(state)`, and the predicate does `state.pop("sensitive")` or `state["processed"] = True`. The mutation persists because Python dicts are passed by reference. The next loop iteration uses the mutated dict, leading to silent corruption.

**Why it happens:**
The simplest implementation passes the state dict directly without copying. The dict is large enough that deep-copying every poll feels wasteful. But mutating a resource state dict is an easy mistake.

**How to avoid:**
Pass a shallow copy: `state_copy = dict(state)`. This is cheap for the expected dict sizes (DynamoDB items, S3 JSON bodies are typically small). Document that the predicate receives a *snapshot* — modifications do not affect the actual resource state or subsequent polls.

```python
if stop_when is not None and stop_when(dict(state)):
    raise StopConditionMetError(...)
```

**Warning signs:**
- Test failures where a predicate seems to affect subsequent polling behavior
- The word "copy" or "clone" missing from `stop_when` parameter docstring
- Flaky tests where predicate side effects influence timing

**Phase to address:**
Phase 1 (implementation) — in the polling loop, pass `dict(state)` not `state`.

---

### Pitfall 5: Inconsistent `expected`/`actual` attribute names across `WaitTimeoutError` subclasses

**What goes wrong:**
Some existing exceptions use `expected`/`actual` (e.g., `S3ContentWaitTimeoutError`), some use `entries`/`actual` (e.g., `DynamoDBWaitTimeoutError`), some use `body`/`actual` (e.g., `SQSWaitTimeoutError`), and some use `event`/`actual` (e.g., `SQSEventWaitTimeoutError`). When adding "richer timeout error messages" with structured expected/actual in `__str__`, the attribute naming is inconsistent. A generic error-formatting function would need to handle all these cases.

**Why it happens:**
Each exception was added incrementally with its own attribute naming convention. `S3WaitTimeoutError` predates the `expected`/`actual` pattern entirely. There was no cross-service review of attribute names when `S3ContentWaitTimeoutError` introduced the `expected`/`actual` pair.

**How to avoid:**
Standardize on `expected` as the attribute name for "what the user asked for" and `actual` for "what was observed." For exceptions where `expected` doesn't make semantic sense (e.g., `S3WaitTimeoutError` which just waits for existence), add them as `None` defaults. Do NOT rename existing public attributes — that's a breaking change. Instead:

1. Add `expected` and `actual` attributes to exceptions that lack them, with `None` defaults where not applicable.
2. Implement `__str__` using these standardized attributes with a shared helper function.
3. Keep legacy attribute names (`entries`, `body`, `event`) as aliases pointing to `expected` for backward compatibility, or leave them as-is and only standardize the `__str__` output format.

**Warning signs:**
- Multiple PRs each adding their own `__str__` format
- Docstring references to both `entries` and `expected` in the same exception class
- Tests checking for different attribute names in different exception types

**Phase to address:**
Phase 2 (error message enrichment) — must standardize naming before implementing `__str__`.

---

### Pitfall 6: `__str__` of `WaitTimeoutError` silently raises on format errors

**What goes wrong:**
`WaitTimeoutError.__str__` uses `repr()` on `expected` and `actual`. If one of these contains an object with a broken `__repr__`, the string formatting fails and `__str__` raises an exception. But Python's exception display mechanism swallows exceptions from `__str__`, falling back to a generic string. The user sees `"<unprintable WaitTimeoutError>"`, losing all debugging context.

**Why it happens:**
`Python` calls `__str__` during exception formatting. If `__str__` raises, the interpreter catches it and uses the default `Exception.__str__` format. The enriched error message is lost, and there's no indication that the formatting failed.

**How to avoid:**
Wrap the `__str__` body in a `try/except` that falls back to a safe format:

```python
def __str__(self) -> str:
    try:
        expected_repr = repr(self.expected) if self.expected is not None else "None"
        actual_repr = repr(self.actual) if self.actual is not None else "None"
        return f"{super().__str__()}\n\nExpected:\n  {expected_repr}\n\nActual:\n  {actual_repr}"
    except Exception:
        return super().__str__()
```

Or, at minimum, use a shared utility function `_safe_repr(obj)` that catches exceptions from `repr()`. This is cheap insurance for a message that exists solely for debugging.

**Warning signs:**
- `repr()` calls on boto3 response objects (which can contain botocore types with complex `__repr__`)
- No error handling in `__str__` methods
- Tests that don't verify `__str__` output for exceptions with large/irregular payloads

**Phase to address:**
Phase 2 (error message enrichment) — in the shared `__str__` formatting helper.

---

### Pitfall 7: Adding `stop_when` to methods that use native boto3 waiters (not custom polling loops)

**What goes wrong:**
`S3ObjectExpectation.to_exist()` uses the native `object_exists` waiter when `entries` is `None` (line 88-97 of `s3.py`). The native waiter is a single `wait()` call — there's no polling loop to insert `stop_when` into. If `stop_when` is added to the parameter list and the user passes both `stop_when=...` and `entries=None`, the predicate is never called. The user gets a confusing silent failure.

**Why it happens:**
The code path bifurcates: `entries` -> custom polling loop; no `entries` -> native waiter. The `stop_when` parameter must be acknowledged in both code paths.

**How to avoid:**
Two options:

**Option A (recommended):** Accept `stop_when` but raise `TypeError` or `ValueError` immediately if it's passed when `entries` is `None` — tells the user upfront that `stop_when` requires the custom polling path (`entries` must be provided).

**Option B:** Force the custom polling path when `stop_when` is not `None`, even without `entries`. Replace the native waiter call with a simple existence poll loop.

Option A is simpler and avoids subtle behavioral differences. Option B provides better UX but introduces two polling implementations of the same wait. Choose Option A and document the restriction.

**Warning signs:**
- `stop_when` parameter in a method's signature but unreachable in one code path
- Type checker not warning about `stop_when` being ignored
- Test where `stop_when` is passed without `entries` and the test "passes" because the native waiter succeeds

**Phase to address:**
Phase 1 (implementation) — must address when adding `stop_when` to `S3ObjectExpectation.to_exist()`.

---

### Pitfall 8: Predicate is checked AFTER timeout rather than BEFORE, causing off-by-one-poll

**What goes wrong:**
The polling loop structure:

```python
while True:
    state = self._fetch_body()
    if state is not None and _matches_entries(state, entries):
        return state  # success
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError(...)  # timeout
    time.sleep(...)
```

When `stop_when` is added, a naive insertion puts it before the timeout check but after the main condition:

```python
    if state is not None and stop_when is not None and stop_when(state):
        raise StopConditionMetError(...)
    remaining = deadline - time.monotonic()
```

This is correct. But a tempting alternative inserts it BEFORE the main condition check, which means `stop_when` always fires even if the main condition is already satisfied — causing spurious `StopConditionMetError` raises when the resource actually met the expected state.

**Why it happens:**
It's tempting to check `stop_when` early — "if we should stop, stop before doing anything else." But the contract is: the main condition is the primary goal. `stop_when` is a secondary abort mechanism for when further polling is pointless. If the main condition is met, return success regardless of `stop_when`.

**How to avoid:**
Order operations in the polling loop:
1. Fetch current state
2. Check main condition → if met, return success
3. Check `stop_when` predicate → if True, raise `StopConditionMetError`
4. Check timeout → if exceeded, raise `WaitTimeoutError`
5. Sleep

Enforce this ordering with a comment in every polling loop and a shared test that verifies "main condition wins over stop_when."

**Warning signs:**
- Tests where `to_exist(entries=..., stop_when=always_true)` raises `StopConditionMetError` instead of returning the item
- `stop_when` check appearing above the main condition check in the loop
- No test case for "resource meets both main condition and stop condition simultaneously"

**Phase to address:**
Phase 1 (implementation) — in every polling loop that adds `stop_when`. Phase 3 (testing) — explicit test case.

---

### Pitfall 9: `__str__` output truncation loses critical context for large payloads

**What goes wrong:**
`DynamoDBFindItemTimeoutError.__str__` uses `repr(actual)` where `actual` is `list[dict[str, Any]]`. A DynamoDB table with 10,000 items produces a `repr()` that is megabytes long. This floods test output, CI logs, and terminal sessions with unreadable garbage. Users can't find the expected vs actual diff because it's buried in noise.

**Why it happens:**
`repr()` on large data structures produces complete output. There's no built-in truncation. The error message that was supposed to help debugging becomes the debugging problem.

**How to avoid:**
Use length-limited representation for collections:

```python
MAX_ITEMS_IN_ERROR = 50
MAX_STR_LEN = 500

def _safe_repr(obj: object) -> str:
    s = repr(obj)
    if len(s) > MAX_STR_LEN:
        s = s[:MAX_STR_LEN] + f"... (truncated, total {len(repr(obj))} chars)"
    return s

def _format_actual(actual: list[dict[str, Any]] | None, expected: dict[str, Any]) -> str:
    if actual is None:
        return "None (no data seen)"
    shown = actual[:MAX_ITEMS_IN_ERROR]
    suffix = f"\n... and {len(actual) - MAX_ITEMS_IN_ERROR} more items" if len(actual) > MAX_ITEMS_IN_ERROR else ""
    return repr(shown) + suffix
```

This is essential for `DynamoDBFindItemTimeoutError.actual` and `SQSEventWaitTimeoutError.actual`, which can hold lists of items/messages.

**Warning signs:**
- CI logs that get cut off by log-length limits when a timeout error is printed
- Users reporting "error message too long to read"
- `repr()` on a `list` without length guard

**Phase to address:**
Phase 2 (error message enrichment) — in the `__str__` formatting helper.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Pass `state` dict directly to `stop_when` without copying | Avoids shallow copy allocation | Predicate side-effects corrupt subsequent polls; impossible-to-debug flaky tests | Never |
| Catch `Exception` around `stop_when` call in polling loop | "Safe" — no crash from broken predicate | Silently swallows user bugs; predicates that raise become invisible | Never |
| Add `stop_when` parameter only to methods with custom polling loops, skip native-waiter methods | Less code to change | Inconsistent API — some methods support `stop_when`, others don't; confusing docs | Only if the omitted methods are clearly documented as unsupported with a runtime error |
| Use `repr()` directly in `__str__` without truncation | Simple implementation | Terminal/log flooding for large payloads | Only for exceptions that never hold collections (e.g., `LambdaWaitTimeoutError`) |
| Copy-paste `expected`/`actual` formatting into each exception's `__str__` | No need for shared helper design | Divergent formats across exceptions; fixing one bug means fixing N places | Never — use a shared `_format_expected_actual()` helper |
| Make `StopConditionMetError` a `WaitTimeoutError` subclass | Simplifies `try/except` for existing callers | Semantic confusion — stop-condition fire is not a timeout; callers can't distinguish | Never per existing Key Decision |

## Integration Gotchas

Common mistakes when connecting these features to the existing codebase.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Adding `stop_when` to `S3ObjectExpectation.to_exist()` | `stop_when` silently ignored when `entries=None` (native waiter code path) | Raise `TypeError` when `stop_when` is non-`None` and `entries` is `None`; document restriction |
| Adding `stop_when` to `DynamoDBItemExpectation.to_exist()` | Parameter added in wrong position, breaking positional callers | Add as keyword-only parameter (`*, stop_when: ... = None`) |
| Adding `stop_when` to `to_be_empty()` / `to_be_not_empty()` | Predicate receives `None` (no item) — useless for a state-dependent check | Skip `stop_when` for methods with no resource-state payload OR document that predicate receives `None` |
| Adding `stop_when` to `to_have_numeric_value_close_to()` | Predicate receives item but non-numeric-field abort (the existing `DynamoDBNonNumericFieldError`) fires first | Non-numeric-field check should fire BEFORE `stop_when` — it's a permanent error, not a state-dependent stop |
| Exporting `StopConditionMetError` from `__init__.py` | Forgetting to add to `__all__` and import block | Add to both `from aws_expect.exceptions import ...` and `__all__` |
| Adding `expected` attribute to `S3WaitTimeoutError` | AttributeError in existing code accessing `.bucket`/`.key` but not `.expected` | Add `expected: None = None` and `actual: None = None` as class-level defaults |
| `DynamoDBWaitTimeoutError.__init__` already has `entries`/`actual` params with complex optional logic (lines 99-125) | Adding `expected` param duplicates `entries`; confusion about which to use | Keep `entries` as the parameter name but set `self.expected = entries` internally for attribute consistency |
| `AggregateWaitTimeoutError` stores `errors: list[WaitTimeoutError]` | `StopConditionMetError` is NOT a `WaitTimeoutError`, so it can never appear in the errors list of `AggregateWaitTimeoutError` | This is correct behavior — document that `expect_any`/`expect_all` only aggregate timeout errors, not stop-condition errors |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Deep-copying state dict for every `stop_when` call | Increased memory allocation per poll; GC pressure under tight polling intervals | Use shallow copy `dict(state)` — only copies top-level keys, not nested values | When state dicts have 10,000+ keys (unlikely for DynamoDB items/S3 JSON) |
| Calling `repr()` on full collection in timeout error `__str__` | Terminal freeze, CI log truncation | Truncate collection repr to first N items (50) with count suffix | When `actual` is a `list` with 100+ items (e.g., `DynamoDBFindItemTimeoutError`) |
| `stop_when` predicate that makes AWS API calls | Doubles the API calls per poll iteration | Document that `stop_when` should only inspect state, not make API calls. Alternative: provide the expectation object so the predicate can call methods | When users try to check "is another resource ready?" inside `stop_when` |
| `stop_when` predicate that does synchronous I/O (HTTP, file) | Blocks the polling loop; extends effective poll interval | Same as above — document inspection-only contract | When users use `stop_when` for cross-service coordination |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| `stop_when` predicate receives raw AWS credentials from state dict | Credential leakage in error messages if `StopConditionMetError.__str__` includes state | `StopConditionMetError` should store only the predicate return value and resource identifier, not the full state that was passed to the predicate |
| `expected`/`actual` attributes in timeout errors containing secrets (API keys, tokens) from resource state | Secret exposure in logs/CI output | Document that `expected`/`actual` reflect the user's expected values and observed resource state; users should not put secrets in `entries` dicts |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| `StopConditionMetError` with no resource context in message | User sees "Stop condition met" with no clue which resource, which condition, or what state triggered it | Include resource identifier (bucket/key, table/key), timeout, and the last observed state in the error attributes and message |
| `stop_when` parameter not discoverable via IDE autocomplete because it's not keyword-only | User passes it positionally, or tools don't show it as an option | Mark as keyword-only: `def to_exist(self, ..., *, stop_when: Callable[[...], bool] | None = None)` |
| Inconsistent `__str__` format across different timeout exceptions | User can't quickly scan logs for expected vs actual; each service looks different | Use a shared `_format_error_with_expected_actual()` helper with a consistent template |
| `StopConditionMetError` docstring doesn't show example predicate | User doesn't know the callable signature — what does the predicate receive? | Include explicit `Callback[[dict[str, Any]], bool]` type annotation and an example in every method's docstring |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **`StopConditionMetError` export:** Verify it appears in `aws_expect/__init__.py` imports AND `__all__` list
- [ ] **`stop_when` on all S3 methods:** `to_exist`, `to_have_content`, `to_not_have_content`, `to_not_exist` — each must accept and invoke the parameter
- [ ] **`stop_when` on all DynamoDB item methods:** `to_exist`, `to_have_numeric_value_close_to`, `to_find_item`, `to_not_exist`, `to_be_empty`, `to_be_not_empty` — at minimum, `stop_when` should be accepted (even if a no-op for methods with no state payload like `to_be_empty`)
- [ ] **`stop_when` ordering test:** Verify "main condition satisfied + stop_when true = main condition wins" for every method
- [ ] **`stop_when` exception propagation test:** Verify predicate `KeyError` → `StopConditionError` wrapping → test captures it
- [ ] **`StopConditionMetError` is NOT caught by `except WaitTimeoutError`:** Add explicit test
- [ ] **`__str__` on every `WaitTimeoutError` subclass:** Every subclass must have structured expected/actual in `__str__`, not just the new ones
- [ ] **Truncation test:** Test `__str__` with 10,000 items — output must be bounded
- [ ] **Type stubs for `stop_when`:** `Callable[[dict[str, Any]], bool]` annotation; `ty` must pass
- [ ] **Existing tests still pass:** No regression in the 167 existing integration tests

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Exception in predicate swallowed | MEDIUM | Remove `try/except` around predicate call; add `StopConditionError` wrapping; update tests to expect the wrapper exception |
| `stop_when` silently ignored in native-waiter path | LOW | Add `TypeError` raise + test for the combination; update docs |
| `StopConditionMetError` confusion (not caught) | LOW | Add docstring note and README example; existing code that wasn't catching it just needs a combined `except` |
| `__str__` format inconsistency | MEDIUM | Refactor all `__str__` to use shared helper; regression-test all exception string formats |
| State mutation via predicate | LOW | Change `state` to `dict(state)` in polling loop; no API change needed |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| #1 — Exception in predicate swallowed | Phase 1 (S3 stop_when implementation) | Test that predicate `KeyError` raises `StopConditionError` |
| #2 — `stop_when` semantics confusion | Phase 0 (API design/review) | Docstring review; parameter naming final |
| #3 — `StopConditionMetError` not caught by `except WaitTimeoutError` | Phase 1 (implementation) | Explicit test: `StopConditionMetError` is NOT caught by `except WaitTimeoutError` |
| #4 — Predicate mutates state | Phase 1 (implementation) | Code review: `dict(state)` not bare `state` in predicate call |
| #5 — Inconsistent `expected`/`actual` naming | Phase 2 (error message enrichment) | Audit all exception subclasses for consistent `.expected`/`.actual` attributes |
| #6 — `__str__` raises on format errors | Phase 2 (error message enrichment) | Test `__str__` with objects that have broken `__repr__` |
| #7 — `stop_when` silent in native-waiter methods | Phase 1 (S3 implementation) | Test: `to_exist(stop_when=..., entries=None)` raises `TypeError` |
| #8 — Predicate checked before main condition | Phase 1 (implementation) | Test: `to_exist(entries=correct, stop_when=always_true)` returns item |
| #9 — `__str__` output truncation | Phase 2 (error message enrichment) | Test `DynamoDBFindItemTimeoutError.__str__` with 10k items |

## Sources

- **Codebase analysis:** `aws_expect/exceptions.py` (452 lines), `aws_expect/s3.py` (226 lines), `aws_expect/dynamodb.py` (470 lines) — actual polling loop patterns, exception hierarchy, and method signatures
- **Tenacity library patterns:** `/jd/tenacity` — stop conditions via callables (`my_stop(retry_state) -> bool`), exception propagation from predicates, `RetryCallState` for structured context
- **Python exception handling semantics:** Python 3.13 `Exception.__str__` fallback behavior — if `__str__` raises, Python uses default representation, silently discarding the enriched message
- **PROJECT.md Key Decisions:** `StopConditionMetError` is NOT a `WaitTimeoutError` subclass — confirmed design constraint
- **boto3 waiter patterns:** `/boto/boto3` — single `wait()` call with no per-poll callback, confirming that native-waiter code paths cannot support `stop_when`

---

*Pitfalls research for: aws-expect v1.3.0 — stop_when predicates + richer timeout error messages*
*Researched: 2026-05-08*
