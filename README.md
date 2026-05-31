# AWS Expect

Declarative, Pythonic waiters for AWS services using boto3.
Wait for S3 objects, DynamoDB items/tables, SQS messages/events, and Lambda functions to reach an expected state — with content matching, `stop_when` predicates for early abort, structured `Expected:`/`Actual:` error messages, and parallel execution via `expect_all` / `expect_any`.

## Features

- **Declarative syntax**: `expect_s3(obj).to_exist(timeout=30)`
- **Content matching**: Wait for S3 body JSON or DynamoDB item attributes to match expected values
- **Smart polling**: `stop_when` predicates abort early when further polling is pointless
- **Richer errors**: Structured `Expected:`/`Actual:` sections in timeout error messages
- **Native boto3 waiters**: Uses AWS's built-in waiter infrastructure where available
- **Testing-friendly**: Perfect for integration tests and CI/CD pipelines
- **Resource-based**: Works with boto3 resource objects (S3, DynamoDB, SQS) and client (Lambda)
- **Flexible timeouts**: Configure both timeout and poll intervals
- **Parallel waiting**: `expect_all()` / `expect_any()` run multiple expectations concurrently, accepting both plain callables and `(fn, *args)` tuples
- **Zero-boilerplate tuples**: `(fn, *args)` tuples eliminate `lambda:` wrappers at call sites; trailing dict is unpacked as `**kwargs`

## Installation

```bash
pip install aws-expect
```

Or with uv:

```bash
uv add aws-expect
```

## Quick Start

### S3 Object Waiting

```python
import boto3
from aws_expect import expect_s3

s3 = boto3.resource("s3")
obj = s3.Object("my-bucket", "report.csv")

metadata = expect_s3(obj).to_exist(timeout=30, poll_interval=5)
print(f"Object exists! Size: {metadata['ContentLength']} bytes")

expect_s3(obj).to_not_exist(timeout=10, poll_interval=2)

# Wait for object body to be valid JSON that deep-matches expected content
body = expect_s3(obj).to_have_content({"status": "shipped"}, timeout=30)

# Assert object body does NOT match after a delay
expect_s3(obj).to_not_have_content({"status": "cancelled"}, delay=5)

# Abort early with stop_when predicate
body = expect_s3(obj).to_exist(
    entries={"status": "shipped"},
    stop_when=lambda state: state.get("status") == "cancelled",
    timeout=60,
)
```

### DynamoDB Item Waiting

```python
import boto3
from aws_expect import expect_dynamodb_item

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("orders")

item = expect_dynamodb_item(table).to_exist(
    key={"pk": "order-123"},
    entries={"status": "shipped"},
    timeout=60,
    poll_interval=5,
)

expect_dynamodb_item(table).to_not_exist(key={"pk": "order-123"}, timeout=10)

# Wait for a timestamp field to be close to a target datetime
from datetime import datetime, timedelta, timezone

item = expect_dynamodb_item(table).to_have_datetime_close_to(
    key={"pk": "event-1"},
    field="created_at",
    delta=timedelta(seconds=30),
    expected=datetime(2025, 1, 1, tzinfo=timezone.utc),
    timeout=10,
)

# Defaults to now(UTC) when expected is omitted
item = expect_dynamodb_item(table).to_have_datetime_close_to(
    key={"pk": "event-1"},
    field="created_at",
    delta=timedelta(minutes=5),
    timeout=10,
)
```

### DynamoDB Table Waiting

```python
from aws_expect import expect_dynamodb_table

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("orders")

description = expect_dynamodb_table(table).to_exist(timeout=30)
expect_dynamodb_table(table).to_not_exist(timeout=30)

# Wait for table to be empty (no items)
expect_dynamodb_table(table).to_be_empty(timeout=30)

# Wait for table to contain at least one item
expect_dynamodb_table(table).to_be_not_empty(timeout=30)

# Scan table for an item matching entries
item = expect_dynamodb_table(table).to_find_item(
    entries={"status": "pending"},
    timeout=30,
)

# Assert no matching item exists after a delay
expect_dynamodb_table(table).to_not_find_item({"status": "cancelled"}, delay=5)

# Abort scan early with stop_when predicate
item = expect_dynamodb_table(table).to_find_item(
    entries={"status": "pending"},
    stop_when=lambda item: item.get("status") == "failed",
    timeout=60,
)
```

### SQS Message Waiting

```python
import boto3
from aws_expect import expect_sqs

sqs = boto3.resource("sqs")
queue = sqs.Queue("https://sqs.us-east-1.amazonaws.com/123456789/my-queue")

# Wait for a plain-text message (non-destructive)
msg = expect_sqs(queue).to_have_message("order-confirmed", timeout=30)

# Wait and consume (delete) the matching message
msg = expect_sqs(queue).to_consume_message("order-confirmed", timeout=30)

# Assert message is absent after a delay
expect_sqs(queue).to_not_have_message("order-confirmed", delay=5)
```

### SQS JSON Event Waiting

```python
# Wait for a JSON message that deep-matches the expected event (non-destructive)
msg = expect_sqs(queue).to_have_event({"type": "ORDER_CREATED", "orderId": "123"}, timeout=30)

# Wait and consume (delete) the matching event
msg = expect_sqs(queue).to_consume_event({"type": "ORDER_CREATED"}, timeout=30)

# Assert no matching event is present after a delay
expect_sqs(queue).to_not_have_event({"type": "ORDER_CREATED"}, delay=5)
```

### Lambda Function Waiting

```python
import boto3
from aws_expect import expect_lambda

lambda_client = boto3.client("lambda")

# Wait for function to exist / be deleted
response = expect_lambda(lambda_client).to_exist("my-function", timeout=30)
expect_lambda(lambda_client).to_not_exist("my-function", timeout=30)

# Wait for function to reach Active state after deployment
response = expect_lambda(lambda_client).to_be_active("my-function", timeout=60)

# Wait for a function update to complete
response = expect_lambda(lambda_client).to_be_updated("my-function", timeout=60)

# Wait until the function can be invoked and returns expected output
payload = expect_lambda(lambda_client).to_be_invocable(
    "my-function",
    payload={"key": "value"},
    entries={"statusCode": 200},
    timeout=30,
)

# Invoke once and assert the response (not a waiter — raises immediately on mismatch)
from aws_expect import LambdaResponseMismatchError

result = expect_lambda(lambda_client).to_respond_with(
    "my-function",
    status_code=200,
    body={"message": "hello"},
    payload={"key": "value"},
)
```

### Parallel Waiting

```python
from aws_expect import expect_all, expect_s3, expect_dynamodb_item

# Wait for ALL expectations to succeed (raises if any times out)
results = expect_all([
    lambda: expect_s3(obj).to_exist(timeout=30),
    lambda: expect_dynamodb_item(table).to_exist(key={"pk": "order-123"}, timeout=30),
])

# Wait for the FIRST expectation to succeed (returns its result)
from aws_expect import expect_any, expect_dynamodb_item

result = expect_any([
    lambda: expect_dynamodb_item(table_a).to_exist(key={"pk": "u1"}, timeout=30),
    lambda: expect_dynamodb_item(table_b).to_exist(key={"pk": "u1"}, timeout=30),
])

# Tuple form — pass (callable, *args) to skip lambda: boilerplate.
# Trailing dict is unpacked as **kwargs.
results = expect_all([
    (expect_dynamodb_item(table_a).to_exist, {"pk": "a"}, 30, 1),
    (expect_dynamodb_item(table_b).to_exist, {"key": {"pk": "b"}, "timeout": 30}),
])
```

### Catching Any Timeout

All service-specific exceptions inherit from `WaitTimeoutError`:

```python
from aws_expect import WaitTimeoutError

try:
    expect_s3(obj).to_exist(timeout=30)
except WaitTimeoutError:
    print("Timed out waiting for resource")
```

## API Reference

### Factory Functions

| Function | Description |
|----------|-------------|
| `expect_s3(s3_object)` | Creates `S3ObjectExpectation` |
| `expect_dynamodb_item(table)` | Creates `DynamoDBItemExpectation` |
| `expect_dynamodb_table(table)` | Creates `DynamoDBTableExpectation` |
| `expect_sqs(queue)` | Creates `SQSQueueExpectation` |
| `expect_lambda(lambda_client)` | Creates `LambdaFunctionExpectation` |
| `expect_all(expectations)` | Runs expectations concurrently; accepts callables or `(fn, *args)` tuples; returns all results or raises |
| `expect_any(expectations)` | Runs expectations concurrently; accepts callables or `(fn, *args)` tuples; returns first to succeed |

### S3 (`S3ObjectExpectation`)

| Method | Description |
|--------|-------------|
| `to_exist(timeout, poll_interval, entries, *, stop_when)` | Wait for object to exist; with *entries*, **shallow** subset-match body JSON (top-level keys only); supports `stop_when` |
| `to_not_exist(timeout, poll_interval)` | Wait for object to be deleted |
| `to_not_appear(timeout, poll_interval)` | Assert object does not appear within timeout |
| `to_have_content(entries, timeout, poll_interval)` | Wait until object body is valid JSON **deep**-matching `entries` (recursive subset) |
| `to_not_have_content(entries, delay)` | Assert object body does not deep-match `entries` after `delay` |

### DynamoDB Item (`DynamoDBItemExpectation`)

| Method | Description |
|--------|-------------|
| `to_exist(key, timeout, poll_interval, entries, *, stop_when)` | Wait for item to exist; optionally match attribute entries and abort early via `stop_when` |
| `to_not_exist(key, timeout, poll_interval)` | Wait for item to be deleted |
| `to_have_numeric_value_close_to(key, field, value, delta, timeout, poll_interval)` | Wait for a numeric field to be within delta of value |
| `to_have_datetime_close_to(key, field, delta, expected, timeout, poll_interval)` | Wait for a timestamp field (epoch or ISO 8601) to be within *delta* of *expected* (defaults to `now(UTC)`) |

### DynamoDB Table (`DynamoDBTableExpectation`)

| Method | Description |
|--------|-------------|
| `to_exist(timeout, poll_interval)` | Wait for table to exist (Active state) |
| `to_not_exist(timeout, poll_interval)` | Wait for table to be deleted |
| `to_be_empty(timeout, poll_interval)` | Wait for table to exist, be Active, and contain no items |
| `to_be_not_empty(timeout, poll_interval)` | Wait for table to exist, be Active, and contain at least one item |
| `to_find_item(entries, timeout, poll_interval, *, stop_when)` | Scan table until at least one item subset-matches `entries`; abort via `stop_when` |
| `to_not_find_item(entries, delay)` | Assert no item matches `entries` after `delay` |

### SQS (`SQSQueueExpectation`)

| Method | Description |
|--------|-------------|
| `to_have_message(body, timeout, poll_interval)` | Wait for exact-body message (non-destructive) |
| `to_consume_message(body, timeout, poll_interval)` | Wait and delete matching message |
| `to_not_have_message(body, delay)` | Assert message absent after delay |
| `to_have_event(event, timeout, poll_interval)` | Wait for JSON subset match (non-destructive) |
| `to_consume_event(event, timeout, poll_interval)` | Wait and delete matching JSON event |
| `to_not_have_event(event, delay)` | Assert JSON event absent after delay |

### Lambda (`LambdaFunctionExpectation`)

| Method | Description |
|--------|-------------|
| `to_exist(function_name, timeout, poll_interval)` | Wait for function to exist |
| `to_not_exist(function_name, timeout, poll_interval)` | Wait for function to be deleted |
| `to_be_active(function_name, timeout, poll_interval)` | Wait for `State == "Active"` |
| `to_be_updated(function_name, timeout, poll_interval)` | Wait for `LastUpdateStatus == "Successful"` |
| `to_be_invocable(function_name, timeout, poll_interval, payload, entries)` | Wait until invocation succeeds; optionally match response payload entries |
| `to_respond_with(function_name, status_code, body, payload)` | Invoke once and assert `statusCode` and/or JSON `body` (not a waiter) |

## Exceptions

All timeout exceptions inherit from `WaitTimeoutError`:

| Exception | Raised by |
|-----------|-----------|
| `S3WaitTimeoutError` | S3 existence methods |
| `S3ContentWaitTimeoutError` | `to_have_content` |
| `S3UnexpectedContentError` | `to_not_have_content` (not a timeout) |
| `DynamoDBWaitTimeoutError` | DynamoDB methods |
| `DynamoDBFindItemTimeoutError` | `to_find_item` |
| `DynamoDBUnexpectedItemError` | `to_not_find_item` (not a timeout) |
| `DynamoDBNonNumericFieldError` | `to_have_numeric_value_close_to` (not a timeout) |
| `DynamoDBInvalidTimestampError` | `to_have_datetime_close_to` (not a timeout) |
| `SQSWaitTimeoutError` | SQS string-body methods |
| `SQSEventWaitTimeoutError` | SQS JSON event methods |
| `SQSUnexpectedMessageError` | `to_not_have_message` (not a timeout) |
| `SQSUnexpectedEventError` | `to_not_have_event` (not a timeout) |
| `LambdaWaitTimeoutError` | Lambda methods |
| `LambdaInvocableTimeoutError` | `to_be_invocable` (with `entries`) |
| `LambdaResponseMismatchError` | `to_respond_with` (not a timeout) |
| `StopConditionMetError` | `stop_when` predicate returns `True` (not a timeout) |
| `StopConditionError` | `stop_when` predicate raises an exception (not a timeout) |
| `AggregateWaitTimeoutError` | `expect_all`, `expect_any` |

## Development

### Setup

```bash
git clone https://github.com/PhishStick-hub/aws-expect
cd aws-expect
uv sync --all-groups
```

### Running Tests

Tests use testcontainers and LocalStack for real AWS API simulation:

```bash
docker info
uv run pytest tests/ -v
```

## License

MIT License - see LICENSE file for details.

## Author

Ivan Shcherbenko
