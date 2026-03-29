# SQS Event Expectation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `to_have_event`, `to_consume_event`, and `to_not_have_event` methods to `SQSQueueExpectation` for waiting on JSON-structured SQS messages using deep recursive subset matching.

**Architecture:** Three new methods on the existing `SQSQueueExpectation` class reuse the existing `_receive_batches` polling loop. A new private `_deep_matches` static helper performs recursive dict subset matching. Two new exceptions are added for typed error handling.

**Tech Stack:** Python 3.13+, boto3, pytest, testcontainers[localstack], ruff, ty

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `aws_expect/exceptions.py` | Modify | Add `SQSEventWaitTimeoutError`, `SQSUnexpectedEventError` |
| `aws_expect/__init__.py` | Modify | Export both new exceptions |
| `tests/test_sqs_event.py` | Create | All tests (TDD: written first, fail before impl) |
| `aws_expect/sqs.py` | Modify | Add `_deep_matches`, `to_have_event`, `to_consume_event`, `to_not_have_event` |

---

## Task 1: Add new exceptions

**Files:**
- Modify: `aws_expect/exceptions.py`

- [ ] **Step 1: Add `SQSEventWaitTimeoutError` and `SQSUnexpectedEventError` to `exceptions.py`**

  Open `aws_expect/exceptions.py` and append after the existing `SQSUnexpectedMessageError` class:

  ```python
  class SQSEventWaitTimeoutError(WaitTimeoutError):
      """Raised when to_have_event / to_consume_event exceeds timeout.

      Inherits WaitTimeoutError directly (not SQSWaitTimeoutError) because
      it stores event: dict[str, Any] rather than body: str. Callers that
      catch SQSWaitTimeoutError will NOT catch this exception; they must
      catch SQSEventWaitTimeoutError or the common base WaitTimeoutError.

      Attributes:
          queue_url: URL of the SQS queue that was polled.
          event: The event subset dict that was not found.
          timeout: The timeout that was configured for the wait.
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

      Attributes:
          queue_url: URL of the SQS queue that was checked.
          event: The event subset dict that was unexpectedly found.
          delay: The number of seconds waited before the check.
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

- [ ] **Step 2: Run linting and type check to verify no errors**

  ```bash
  uv run ruff check aws_expect/exceptions.py && uv run ty check
  ```
  Expected: no errors.

- [ ] **Step 3: Commit**

  ```bash
  git add aws_expect/exceptions.py
  git commit -m "feat(sqs): add SQSEventWaitTimeoutError and SQSUnexpectedEventError"
  ```

---

## Task 2: Export new exceptions

**Files:**
- Modify: `aws_expect/__init__.py`

- [ ] **Step 1: Add imports and `__all__` entries in `aws_expect/__init__.py`**

  In the `from aws_expect.exceptions import (...)` block, add (keep alphabetical order):
  ```python
  SQSEventWaitTimeoutError,
  SQSUnexpectedEventError,
  ```

  In `__all__`, add (keep alphabetical order):
  ```python
  "SQSEventWaitTimeoutError",
  "SQSUnexpectedEventError",
  ```

- [ ] **Step 2: Verify the import works**

  ```bash
  uv run python -c "from aws_expect import SQSEventWaitTimeoutError, SQSUnexpectedEventError; print('OK')"
  ```
  Expected: `OK`

- [ ] **Step 3: Commit**

  ```bash
  git add aws_expect/__init__.py
  git commit -m "feat(sqs): export SQSEventWaitTimeoutError and SQSUnexpectedEventError"
  ```

---

## Task 3: Write all failing tests (TDD RED phase)

**Files:**
- Create: `tests/test_sqs_event.py`

The `sqs_queue` fixture is already defined in `tests/conftest.py` — it creates a unique standard SQS queue backed by LocalStack and cleans up after each test. No new fixtures needed.

- [ ] **Step 1: Create `tests/test_sqs_event.py` with all tests**

  ```python
  import json
  import threading
  import time

  import pytest

  from aws_expect import (
      SQSEventWaitTimeoutError,
      SQSUnexpectedEventError,
      SQSWaitTimeoutError,
      WaitTimeoutError,
      expect_sqs,
  )


  def _send_event(queue, event: dict) -> None:
      """Helper: send a JSON-serialised event to the queue."""
      queue.send_message(MessageBody=json.dumps(event))


  class TestSQSToHaveEvent:
      """Tests for expect_sqs(queue).to_have_event(event=...)."""

      def test_returns_message_on_exact_match(self, sqs_queue):
          _send_event(sqs_queue, {"source": "my-app", "detail-type": "OrderPlaced"})

          result = expect_sqs(sqs_queue).to_have_event(
              event={"source": "my-app", "detail-type": "OrderPlaced"},
              timeout=5,
              poll_interval=1,
          )

          assert json.loads(result["Body"]) == {"source": "my-app", "detail-type": "OrderPlaced"}
          assert "MessageId" in result
          assert "ReceiptHandle" in result

      def test_returns_message_on_subset_match(self, sqs_queue):
          """Extra fields in the body are ignored."""
          _send_event(sqs_queue, {"source": "my-app", "detail-type": "OrderPlaced", "version": "0"})

          result = expect_sqs(sqs_queue).to_have_event(
              event={"source": "my-app"},
              timeout=5,
              poll_interval=1,
          )

          assert json.loads(result["Body"])["source"] == "my-app"

      def test_deep_nested_match(self, sqs_queue):
          _send_event(sqs_queue, {"source": "my-app", "detail": {"orderId": "123", "status": "placed"}})

          result = expect_sqs(sqs_queue).to_have_event(
              event={"detail": {"orderId": "123"}},
              timeout=5,
              poll_interval=1,
          )

          assert json.loads(result["Body"])["detail"]["orderId"] == "123"

      def test_non_json_body_skipped_polling_continues(self, sqs_queue):
          """Non-JSON body is ignored; polling continues until a matching JSON message arrives."""
          sqs_queue.send_message(MessageBody="not-json")

          def send_event_later() -> None:
              _send_event(sqs_queue, {"source": "my-app"})

          timer = threading.Timer(2.0, send_event_later)
          timer.start()
          try:
              result = expect_sqs(sqs_queue).to_have_event(
                  event={"source": "my-app"},
                  timeout=8,
                  poll_interval=1,
              )
              assert json.loads(result["Body"])["source"] == "my-app"
          finally:
              timer.cancel()

      def test_raises_timeout_when_queue_empty(self, sqs_queue):
          with pytest.raises(SQSEventWaitTimeoutError) as exc_info:
              expect_sqs(sqs_queue).to_have_event(
                  event={"source": "my-app"},
                  timeout=2,
                  poll_interval=1,
              )

          assert exc_info.value.event == {"source": "my-app"}
          assert exc_info.value.timeout == 2
          assert exc_info.value.queue_url == sqs_queue.url

      def test_raises_timeout_when_wrong_event_present(self, sqs_queue):
          _send_event(sqs_queue, {"source": "other-app"})

          with pytest.raises(SQSEventWaitTimeoutError):
              expect_sqs(sqs_queue).to_have_event(
                  event={"source": "my-app"},
                  timeout=2,
                  poll_interval=1,
              )

      def test_exception_chain_cause_is_sqs_wait_timeout_error(self, sqs_queue):
          """__cause__ must be SQSWaitTimeoutError to preserve exception chain."""
          with pytest.raises(SQSEventWaitTimeoutError) as exc_info:
              expect_sqs(sqs_queue).to_have_event(
                  event={"source": "my-app"},
                  timeout=2,
                  poll_interval=1,
              )

          assert isinstance(exc_info.value.__cause__, SQSWaitTimeoutError)

      def test_non_matching_messages_remain_visible(self, sqs_queue):
          """Non-destructive: message stays visible after a failed poll."""
          _send_event(sqs_queue, {"source": "other-app"})

          with pytest.raises(SQSEventWaitTimeoutError):
              expect_sqs(sqs_queue).to_have_event(
                  event={"source": "my-app"},
                  timeout=2,
                  poll_interval=1,
              )

          messages = sqs_queue.receive_messages(MaxNumberOfMessages=1)
          assert len(messages) == 1
          assert json.loads(messages[0].body)["source"] == "other-app"
          messages[0].delete()

      def test_succeeds_when_event_appears_mid_poll(self, sqs_queue):
          def send_later() -> None:
              _send_event(sqs_queue, {"source": "my-app", "detail": {"id": "42"}})

          timer = threading.Timer(2.0, send_later)
          timer.start()
          try:
              result = expect_sqs(sqs_queue).to_have_event(
                  event={"detail": {"id": "42"}},
                  timeout=8,
                  poll_interval=1,
              )
              assert json.loads(result["Body"])["detail"]["id"] == "42"
          finally:
              timer.cancel()

      def test_catchable_as_wait_timeout_error(self, sqs_queue):
          with pytest.raises(WaitTimeoutError):
              expect_sqs(sqs_queue).to_have_event(
                  event={"source": "my-app"},
                  timeout=2,
                  poll_interval=1,
              )

      def test_not_catchable_as_sqs_wait_timeout_error(self, sqs_queue):
          """SQSEventWaitTimeoutError does NOT inherit SQSWaitTimeoutError."""
          with pytest.raises(SQSEventWaitTimeoutError):
              expect_sqs(sqs_queue).to_have_event(
                  event={"source": "my-app"},
                  timeout=2,
                  poll_interval=1,
              )
          # Verify the hierarchy separately
          exc = SQSEventWaitTimeoutError("url", {"k": "v"}, 1.0)
          assert not isinstance(exc, SQSWaitTimeoutError)


  class TestSQSToConsumeEvent:
      """Tests for expect_sqs(queue).to_consume_event(event=...)."""

      def test_returns_and_deletes_matching_message(self, sqs_queue):
          _send_event(sqs_queue, {"source": "my-app"})

          result = expect_sqs(sqs_queue).to_consume_event(
              event={"source": "my-app"},
              timeout=5,
              poll_interval=1,
          )

          assert json.loads(result["Body"])["source"] == "my-app"
          messages = sqs_queue.receive_messages(MaxNumberOfMessages=1)
          assert messages == []

      def test_non_matched_in_match_batch_restored(self, sqs_queue):
          """Non-matching messages in same batch as match are restored."""
          _send_event(sqs_queue, {"source": "keep-me"})
          _send_event(sqs_queue, {"source": "delete-me"})

          result = expect_sqs(sqs_queue).to_consume_event(
              event={"source": "delete-me"},
              timeout=5,
              poll_interval=1,
          )
          assert json.loads(result["Body"])["source"] == "delete-me"

          time.sleep(1.0)  # allow change_message_visibility to propagate in LocalStack
          messages = sqs_queue.receive_messages(MaxNumberOfMessages=10)
          bodies = [json.loads(m.body)["source"] for m in messages]
          assert "delete-me" not in bodies
          assert "keep-me" in bodies
          for m in messages:
              m.delete()

      def test_non_matched_in_no_match_batch_restored(self, sqs_queue):
          """Non-matching messages in a no-match batch are restored so polling can continue."""
          _send_event(sqs_queue, {"source": "keep-me"})

          def send_target() -> None:
              _send_event(sqs_queue, {"source": "target"})

          timer = threading.Timer(2.0, send_target)
          timer.start()
          try:
              result = expect_sqs(sqs_queue).to_consume_event(
                  event={"source": "target"},
                  timeout=8,
                  poll_interval=1,
              )
              assert json.loads(result["Body"])["source"] == "target"
          finally:
              timer.cancel()

          time.sleep(1.0)
          messages = sqs_queue.receive_messages(MaxNumberOfMessages=10)
          bodies = [json.loads(m.body)["source"] for m in messages]
          assert "keep-me" in bodies
          for m in messages:
              m.delete()

      def test_raises_timeout_when_queue_empty(self, sqs_queue):
          with pytest.raises(SQSEventWaitTimeoutError) as exc_info:
              expect_sqs(sqs_queue).to_consume_event(
                  event={"source": "my-app"},
                  timeout=2,
                  poll_interval=1,
              )

          assert exc_info.value.event == {"source": "my-app"}
          assert exc_info.value.timeout == 2

      def test_succeeds_when_event_appears_mid_poll(self, sqs_queue):
          def send_later() -> None:
              _send_event(sqs_queue, {"source": "my-app"})

          timer = threading.Timer(2.0, send_later)
          timer.start()
          try:
              result = expect_sqs(sqs_queue).to_consume_event(
                  event={"source": "my-app"},
                  timeout=8,
                  poll_interval=1,
              )
              assert json.loads(result["Body"])["source"] == "my-app"
          finally:
              timer.cancel()


  class TestSQSToNotHaveEvent:
      """Tests for expect_sqs(queue).to_not_have_event(event=...)."""

      def test_returns_none_when_queue_empty(self, sqs_queue):
          result = expect_sqs(sqs_queue).to_not_have_event(
              event={"source": "my-app"}, delay=1
          )
          assert result is None

      def test_returns_none_when_non_matching_event_present(self, sqs_queue):
          _send_event(sqs_queue, {"source": "other-app"})

          result = expect_sqs(sqs_queue).to_not_have_event(
              event={"source": "my-app"}, delay=1
          )
          assert result is None

          sqs_queue.receive_messages(MaxNumberOfMessages=1)[0].delete()

      def test_raises_when_matching_event_found(self, sqs_queue):
          _send_event(sqs_queue, {"source": "bad-app", "detail-type": "Alert"})

          with pytest.raises(SQSUnexpectedEventError) as exc_info:
              expect_sqs(sqs_queue).to_not_have_event(
                  event={"source": "bad-app"},
                  delay=1,
              )

          assert exc_info.value.event == {"source": "bad-app"}
          assert exc_info.value.delay == 1
          assert exc_info.value.queue_url == sqs_queue.url

      def test_not_a_wait_timeout_error(self, sqs_queue):
          _send_event(sqs_queue, {"source": "bad-app"})

          with pytest.raises(SQSUnexpectedEventError) as exc_info:
              expect_sqs(sqs_queue).to_not_have_event(
                  event={"source": "bad-app"}, delay=1
              )

          assert not isinstance(exc_info.value, WaitTimeoutError)

      def test_delay_zero_clamped_to_one_second(self, sqs_queue):
          """delay=0 must still wait at least 1 second (_compute_delay clamps it)."""
          start = time.monotonic()
          expect_sqs(sqs_queue).to_not_have_event(event={"source": "x"}, delay=0)
          elapsed = time.monotonic() - start
          assert elapsed >= 1.0
  ```

- [ ] **Step 2: Run all new tests — confirm they ALL fail**

  ```bash
  uv run pytest tests/test_sqs_event.py -v 2>&1 | tail -20
  ```
  Expected: All tests fail. At this point the methods do not exist yet, so you will see either `ImportError` (if the exceptions aren't exported yet) or `AttributeError: 'SQSQueueExpectation' object has no attribute 'to_have_event'`. Both count as confirmed-failing — either is acceptable here since Tasks 1 and 2 have already added the exception classes. The key requirement is that no test passes before implementation.

- [ ] **Step 3: Commit the failing tests**

  ```bash
  git add tests/test_sqs_event.py
  git commit -m "test(sqs): add failing tests for event expectation methods (TDD RED)"
  ```

---

## Task 4: Implement `_deep_matches` and `to_have_event`

**Files:**
- Modify: `aws_expect/sqs.py`

- [ ] **Step 1: Add `import json` to the stdlib imports in `sqs.py`**

  The existing import block in `aws_expect/sqs.py` starts with:
  ```python
  import math
  import time
  ```
  Add `import json` in the stdlib section (alphabetically before `math`):
  ```python
  import json
  import math
  import time
  ```
  Then update the existing `from aws_expect.exceptions import ...` line to also import the two new exceptions:
  ```python
  from aws_expect.exceptions import (
      SQSEventWaitTimeoutError,
      SQSUnexpectedEventError,
      SQSUnexpectedMessageError,
      SQSWaitTimeoutError,
  )
  ```

- [ ] **Step 2: Add `_deep_matches` static method to `SQSQueueExpectation`**

  Add after `_compute_delay` at the bottom of the class:

  ```python
  @staticmethod
  def _deep_matches(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
      """Check whether *actual* contains all key-value pairs in *expected*.

      Recurses into nested dicts. Lists and all other types use exact equality.

      Args:
          actual: The parsed JSON dict from the SQS message body.
          expected: The subset dict to match against.

      Returns:
          True if every key in *expected* is present in *actual* and matches.
      """
      for key, value in expected.items():
          if key not in actual:
              return False
          if isinstance(value, dict):
              if not isinstance(actual[key], dict):
                  return False
              if not SQSQueueExpectation._deep_matches(actual[key], value):
                  return False
          elif actual[key] != value:
              return False
      return True
  ```

- [ ] **Step 3: Add `to_have_event` method**

  `_receive_batches` takes `body: str` as its first argument (used only inside `SQSWaitTimeoutError` if timeout occurs). Pass `str(event)` as a placeholder — this appears only on the chained `__cause__` and is not exposed to callers.

  Add method to `SQSQueueExpectation`:

  ```python
  def to_have_event(
      self,
      event: dict[str, Any],
      timeout: float = 30,
      poll_interval: float = 5,
  ) -> dict[str, Any]:
      """Wait for a message whose JSON body deep-matches *event*.

      Non-destructive: messages are received with ``VisibilityTimeout=0``
      so they remain visible and the queue state is unchanged.

      Args:
          event: Dict of expected key-value pairs. Matched recursively
              against the parsed JSON body (subset match).
          timeout: Maximum seconds to wait.
          poll_interval: Seconds between polls (minimum 1).

      Returns:
          The matching SQS message dict (includes ``Body``, ``MessageId``,
          ``ReceiptHandle``).

      Raises:
          SQSEventWaitTimeoutError: If no matching message appears within *timeout*.
      """
      try:
          for messages in self._receive_batches(
              str(event), timeout, poll_interval, visibility_timeout=0
          ):
              for message in messages:
                  try:
                      body = json.loads(message["Body"])
                  except (json.JSONDecodeError, ValueError):
                      continue
                  if isinstance(body, dict) and self._deep_matches(body, event):
                      return message
      except SQSWaitTimeoutError as exc:
          raise SQSEventWaitTimeoutError(self._queue_url, event, timeout) from exc
      raise AssertionError("unreachable")  # pragma: no cover
  ```

- [ ] **Step 4: Run `TestSQSToHaveEvent` tests**

  ```bash
  uv run pytest tests/test_sqs_event.py::TestSQSToHaveEvent -v
  ```
  Expected: All 10 tests PASS.

- [ ] **Step 5: Run linting and type check**

  ```bash
  uv run ruff check aws_expect/sqs.py && uv run ruff format --check aws_expect/sqs.py && uv run ty check
  ```
  Expected: no errors.

- [ ] **Step 6: Commit**

  ```bash
  git add aws_expect/sqs.py
  git commit -m "feat(sqs): add _deep_matches helper and to_have_event method"
  ```

---

## Task 5: Implement `to_consume_event`

**Files:**
- Modify: `aws_expect/sqs.py`

- [ ] **Step 1: Add `to_consume_event` method to `SQSQueueExpectation`**

  ```python
  def to_consume_event(
      self,
      event: dict[str, Any],
      timeout: float = 30,
      poll_interval: float = 5,
  ) -> dict[str, Any]:
      """Wait for a message whose JSON body deep-matches *event* and delete it.

      Destructive: the matching message is permanently deleted before returning.
      Non-matching messages received in the same batch are immediately restored
      via ``change_message_visibility(VisibilityTimeout=0)``.

      Args:
          event: Dict of expected key-value pairs. Matched recursively
              against the parsed JSON body (subset match).
          timeout: Maximum seconds to wait.
          poll_interval: Seconds between polls (minimum 1).

      Returns:
          The consumed SQS message dict (includes ``Body``, ``MessageId``,
          ``ReceiptHandle``).

      Raises:
          SQSEventWaitTimeoutError: If no matching message appears within *timeout*.
      """
      try:
          for messages in self._receive_batches(
              str(event), timeout, poll_interval, visibility_timeout=10
          ):
              matched: dict[str, Any] | None = None
              for message in messages:
                  try:
                      body = json.loads(message["Body"])
                  except (json.JSONDecodeError, ValueError):
                      continue
                  if isinstance(body, dict) and self._deep_matches(body, event):
                      matched = message
                      break

              if matched is not None:
                  for message in messages:
                      if message is not matched:
                          self._client.change_message_visibility(
                              QueueUrl=self._queue_url,
                              ReceiptHandle=message["ReceiptHandle"],
                              VisibilityTimeout=0,
                          )
                  self._client.delete_message(
                      QueueUrl=self._queue_url,
                      ReceiptHandle=matched["ReceiptHandle"],
                  )
                  return matched

              # No match in this batch — restore all so they stay visible
              for message in messages:
                  self._client.change_message_visibility(
                      QueueUrl=self._queue_url,
                      ReceiptHandle=message["ReceiptHandle"],
                      VisibilityTimeout=0,
                  )
      except SQSWaitTimeoutError as exc:
          raise SQSEventWaitTimeoutError(self._queue_url, event, timeout) from exc
      raise AssertionError("unreachable")  # pragma: no cover
  ```

- [ ] **Step 2: Run `TestSQSToConsumeEvent` tests**

  ```bash
  uv run pytest tests/test_sqs_event.py::TestSQSToConsumeEvent -v
  ```
  Expected: All 5 tests PASS.

- [ ] **Step 3: Run linting and type check**

  ```bash
  uv run ruff check aws_expect/sqs.py && uv run ruff format --check aws_expect/sqs.py && uv run ty check
  ```
  Expected: no errors.

- [ ] **Step 4: Commit**

  ```bash
  git add aws_expect/sqs.py
  git commit -m "feat(sqs): add to_consume_event method"
  ```

---

## Task 6: Implement `to_not_have_event`

**Files:**
- Modify: `aws_expect/sqs.py`

- [ ] **Step 1: Add `to_not_have_event` method to `SQSQueueExpectation`**

  ```python
  def to_not_have_event(
      self,
      event: dict[str, Any],
      delay: float,
  ) -> None:
      """Assert no message matching *event* is present after a fixed delay.

      Sleeps for *delay* seconds (minimum 1 via :meth:`_compute_delay`), then
      performs a single non-destructive receive_message check.

      Args:
          event: Dict of expected key-value pairs to match against parsed JSON body.
          delay: Seconds to sleep before performing the check (minimum 1).

      Returns:
          ``None`` when no matching message is found.

      Note:
          At most 10 messages are inspected (SQS API limit). On queues with
          many messages, a matching event may not be returned in the single
          poll even if it is present.

      Raises:
          SQSUnexpectedEventError: If a matching message is found.
      """
      time.sleep(self._compute_delay(delay))
      response = self._client.receive_message(
          QueueUrl=self._queue_url,
          MaxNumberOfMessages=10,
          VisibilityTimeout=0,
          WaitTimeSeconds=0,
      )
      for message in response.get("Messages", []):
          try:
              body = json.loads(message["Body"])
          except (json.JSONDecodeError, ValueError):
              continue
          if isinstance(body, dict) and self._deep_matches(body, event):
              raise SQSUnexpectedEventError(self._queue_url, event, delay)
  ```

- [ ] **Step 2: Run `TestSQSToNotHaveEvent` tests**

  ```bash
  uv run pytest tests/test_sqs_event.py::TestSQSToNotHaveEvent -v
  ```
  Expected: All 5 tests PASS.

- [ ] **Step 3: Run all SQS event tests**

  ```bash
  uv run pytest tests/test_sqs_event.py -v
  ```
  Expected: All 20 tests PASS.

- [ ] **Step 4: Run linting and type check**

  ```bash
  uv run ruff check aws_expect/sqs.py && uv run ruff format --check aws_expect/sqs.py && uv run ty check
  ```
  Expected: no errors.

- [ ] **Step 5: Commit**

  ```bash
  git add aws_expect/sqs.py
  git commit -m "feat(sqs): add to_not_have_event method"
  ```

---

## Task 7: Final verification

**Files:** None (read-only checks)

- [ ] **Step 1: Run the full test suite**

  ```bash
  uv run pytest tests/ -v
  ```
  Expected: All tests pass. No regressions in existing S3, DynamoDB, or SQS string-body tests.

- [ ] **Step 2: Run full quality gate (all four checks required by the project)**

  ```bash
  uv run ruff check . && uv run ruff format --check . && uv run ty check
  ```
  Expected: All pass with no errors.

- [ ] **Step 3: If `ruff format --check` reports issues, fix them**

  ```bash
  uv run ruff format .
  git add aws_expect/ tests/
  git commit -m "chore(sqs): apply ruff formatting"
  ```
