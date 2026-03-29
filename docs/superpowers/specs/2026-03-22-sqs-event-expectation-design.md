# SQS Event Expectation — Design Spec

**Date:** 2026-03-22
**Status:** Approved

## Overview

Add three methods to `SQSQueueExpectation` for waiting on JSON-structured SQS messages using deep recursive subset matching. The feature works for any JSON body, including EventBridge event envelopes delivered to SQS.

## API

```python
# Non-destructive: message stays visible after match
message = expect_sqs(queue).to_have_event(
    event={"source": "my-app", "detail": {"orderId": "123"}},
    timeout=30,
    poll_interval=5,
)

# Destructive: matched message is deleted from the queue
message = expect_sqs(queue).to_consume_event(
    event={"detail-type": "OrderPlaced"},
    timeout=30,
    poll_interval=5,
)

# Negative: assert no matching event arrives within a delay
expect_sqs(queue).to_not_have_event(event={"source": "bad-app"}, delay=5)
```

Method signatures:
```python
def to_have_event(self, event: dict[str, Any], timeout: float = 30, poll_interval: float = 5) -> dict[str, Any]: ...
def to_consume_event(self, event: dict[str, Any], timeout: float = 30, poll_interval: float = 5) -> dict[str, Any]: ...
def to_not_have_event(self, event: dict[str, Any], delay: float) -> None: ...
```

Note: `to_not_have_event` has no default for `delay` — consistent with `to_not_have_message(body, delay)`.

Parameters:
- `event: dict[str, Any]` — expected subset; deep recursive match against parsed JSON body
- `timeout: float` (positive waiters) — max seconds to poll
- `poll_interval: float` (positive waiters) — seconds between polls, clamped to minimum 1
- `delay: float` (negative) — seconds to sleep before the single check, clamped to minimum 1

## Components

### `aws_expect/sqs.py`

Three new public methods on `SQSQueueExpectation`:

| Method | Destructive | Returns |
|--------|------------|---------|
| `to_have_event` | No (VisibilityTimeout=0) | matched SQS message dict |
| `to_consume_event` | Yes (delete on match) | matched SQS message dict |
| `to_not_have_event` | No | `None` |

One new private static helper:

```python
@staticmethod
def _deep_matches(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Recursive subset check.
    - If key missing from actual → False.
    - If expected[key] is dict AND actual[key] is dict → recurse.
    - If expected[key] is dict but actual[key] is NOT dict → False.
    - Otherwise → equality (lists: exact equality, no subset semantics).
    Returns True only if all keys in expected are satisfied.
    """
```

### `aws_expect/exceptions.py`

Two new exception classes:

```python
class SQSEventWaitTimeoutError(WaitTimeoutError):
    """Raised when to_have_event / to_consume_event exceeds timeout.

    Inherits WaitTimeoutError directly (not SQSWaitTimeoutError) because
    it stores event: dict[str, Any] rather than body: str. Callers that
    catch SQSWaitTimeoutError will NOT catch this exception; they must
    catch SQSEventWaitTimeoutError or the common base WaitTimeoutError.
    """

    def __init__(self, queue_url: str, event: dict[str, Any], timeout: float) -> None:
        self.queue_url = queue_url
        self.event = event
        self.timeout = timeout
        super().__init__(
            f"Timed out after {timeout}s waiting for event matching {event!r}"
            f" in queue {queue_url}"
        )


class SQSUnexpectedEventError(Exception):
    """Raised when to_not_have_event finds a matching event.

    Does NOT inherit WaitTimeoutError — mirrors SQSUnexpectedMessageError.
    """

    def __init__(self, queue_url: str, event: dict[str, Any], delay: float) -> None:
        self.queue_url = queue_url
        self.event = event
        self.delay = delay
        super().__init__(
            f"Unexpected event matching {event!r} found in queue {queue_url}"
            f" after {delay}s delay"
        )
```

### `aws_expect/__init__.py`

Add import lines AND add both new exceptions to `__all__`:
```python
from aws_expect.exceptions import (
    ...
    SQSEventWaitTimeoutError,
    SQSUnexpectedEventError,
)
__all__ = [
    ...
    "SQSEventWaitTimeoutError",
    "SQSUnexpectedEventError",
]
```

## Data Flow

### Exception strategy for positive waiters

`_receive_batches` raises `SQSWaitTimeoutError` on deadline. The new methods catch it and re-raise as `SQSEventWaitTimeoutError`:

```python
try:
    for messages in self._receive_batches(str(event), timeout, poll_interval, visibility_timeout=0):
        ...
except SQSWaitTimeoutError as exc:
    raise SQSEventWaitTimeoutError(self._queue_url, event, timeout) from exc
```

`_receive_batches` takes `body: str` which it uses only in the `SQSWaitTimeoutError` it raises internally. We pass `str(event)` as a placeholder; this string appears only on the chained `__cause__` and is an internal implementation detail not exposed to callers. The public exception raised to callers is always `SQSEventWaitTimeoutError` with the original `event: dict`.

### `to_have_event` (non-destructive)
1. Wrap `_receive_batches(..., visibility_timeout=0)` in try/except as above
2. For each message in each batch: parse `Body` as JSON; skip non-JSON silently (continue)
3. Run `_deep_matches(parsed, event)` — on match return the SQS message dict
4. On `SQSWaitTimeoutError`: re-raise as `SQSEventWaitTimeoutError`

### `to_consume_event` (destructive)
1. Wrap `_receive_batches(..., visibility_timeout=10)` in try/except as above
2. For each batch:
   a. Parse all messages (skip non-JSON), find first match via `_deep_matches`
   b. **If match found**: restore non-matched via `change_message_visibility(0)`, delete matched, return matched
   c. **If no match in batch**: restore ALL messages via `change_message_visibility(0)`, continue polling
3. On `SQSWaitTimeoutError`: re-raise as `SQSEventWaitTimeoutError`

### `to_not_have_event` (single-shot)
1. `time.sleep(_compute_delay(delay))` — clamped to minimum 1 second
2. One `receive_message` call (VisibilityTimeout=0, MaxNumberOfMessages=10)
3. Parse each body as JSON; skip non-JSON silently
4. Run `_deep_matches(parsed, event)` — on match raise `SQSUnexpectedEventError(self._queue_url, event, delay)`
5. If no match: return `None`

**Note:** Like `to_not_have_message`, at most 10 messages are inspected per call (SQS API limit). On queues with many messages, a matching event may not be returned in the single poll even if it is present. This is a known limitation inherited from the SQS polling model.

### `_deep_matches(actual, expected)`
```
for key, value in expected.items():
    if key not in actual → return False
    if isinstance(value, dict):
        if not isinstance(actual[key], dict) → return False   # type mismatch
        if not _deep_matches(actual[key], value) → return False  # recurse
    else:
        if actual[key] != value → return False   # equality (lists: exact)
return True
```

**List behaviour:** lists are compared with exact equality — `{"resources": ["arn:aws:s3:::bucket"]}` requires `resources` to be exactly `["arn:aws:s3:::bucket"]`.

**None and scalar mismatches:** if `expected[key]` is a dict but `actual[key]` is `None` or any non-dict, returns `False` immediately.

## Error Handling

- Non-JSON message bodies: silently skipped (continue), polling continues
- `SQSEventWaitTimeoutError` inherits `WaitTimeoutError` directly — NOT `SQSWaitTimeoutError`. Callers catching `SQSWaitTimeoutError` will not catch it; they must use `SQSEventWaitTimeoutError` or `WaitTimeoutError`.
- `SQSUnexpectedEventError` does NOT inherit `WaitTimeoutError` — mirrors `SQSUnexpectedMessageError`
- `delay=0` (or any value < 1) is clamped to 1 second by `_compute_delay`

## Testing

File: `tests/test_sqs_event.py`
Fixtures: reuse `sqs_queue` from `conftest.py` — no new fixtures needed.

**TDD order:** write all tests first (RED), then implement (GREEN).

### `TestSQSToHaveEvent`
- Returns matching message on exact event match
- Returns matching message on subset match (extra fields in body ignored)
- Deep nested match works (`{"detail": {"orderId": "123"}}`)
- Non-JSON body silently skipped, polling continues
- Raises `SQSEventWaitTimeoutError` when queue empty (verify `.event`, `.timeout`, `.queue_url` attrs)
- Raises `SQSEventWaitTimeoutError` when wrong event present
- `SQSEventWaitTimeoutError.__cause__` is a `SQSWaitTimeoutError` (exception chain preserved)
- Non-matching messages remain visible after failed poll (non-destructive guarantee)
- Succeeds when matching event appears mid-poll (`threading.Timer`)
- Catchable as `WaitTimeoutError`; NOT catchable as `SQSWaitTimeoutError`

### `TestSQSToConsumeEvent`
- Returns and deletes matching message
- Non-matching messages in the same batch as match are restored (VisibilityTimeout=0)
- Non-matching messages in a batch with no match are restored (VisibilityTimeout=0), polling continues
- Raises `SQSEventWaitTimeoutError` on timeout
- Succeeds mid-poll

### `TestSQSToNotHaveEvent`
- Returns `None` when queue empty
- Returns `None` when non-matching event present
- Raises `SQSUnexpectedEventError` when matching event found (verify `.event`, `.delay`, `.queue_url`)
- Not a `WaitTimeoutError` instance
- `delay=0` still waits at least 1 second (clamped by `_compute_delay`)

## Constraints

- Python 3.13+, full type annotations
- No new dependencies
- `_receive_batches` reused unchanged; new methods catch `SQSWaitTimeoutError` and re-raise
- Polling pattern mirrors existing `to_have_message` / `to_consume_message`
