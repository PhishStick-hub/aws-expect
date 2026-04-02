# AWS Expect

Declarative, Pythonic waiters for AWS services using boto3.
Wait for S3 objects, DynamoDB items/tables, SQS messages/events, and Lambda functions to reach an expected state — with optional content matching and parallel execution via `expect_all`.

## Features

- **Declarative syntax**: `expect_s3(obj).to_exist(timeout=30)`
- **Native boto3 waiters**: Uses AWS's built-in waiter infrastructure where available
- **Testing-friendly**: Perfect for integration tests and CI/CD pipelines
- **Resource-based**: Works with boto3 resource objects (S3, DynamoDB, SQS) and client (Lambda)
- **Flexible timeouts**: Configure both timeout and poll intervals
- **Parallel waiting**: `expect_all()` runs multiple expectations concurrently

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
from aws_expect import expect_s3, S3WaitTimeoutError

s3 = boto3.resource("s3")
obj = s3.Object("my-bucket", "report.csv")

metadata = expect_s3(obj).to_exist(timeout=30, poll_interval=5)
print(f"Object exists! Size: {metadata['ContentLength']} bytes")

expect_s3(obj).to_not_exist(timeout=10, poll_interval=2)
```

### DynamoDB Item Waiting

```python
import boto3
from aws_expect import expect_dynamodb_item, DynamoDBWaitTimeoutError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("orders")

item = expect_dynamodb_item(table).to_exist(
    key={"pk": "order-123"},
    entries={"status": "shipped"},
    timeout=60,
    poll_interval=5,
)

expect_dynamodb_item(table).to_not_exist(key={"pk": "order-123"}, timeout=10)
```

### DynamoDB Table Waiting

```python
from aws_expect import expect_dynamodb_table

dynamodb = boto3.resource("dynamodb")

description = expect_dynamodb_table(dynamodb, "orders").to_exist(timeout=30)
expect_dynamodb_table(dynamodb, "orders").to_not_exist(timeout=30)
```

### SQS Message Waiting

```python
import boto3
from aws_expect import expect_sqs, SQSWaitTimeoutError

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
from aws_expect import expect_lambda, LambdaWaitTimeoutError

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
```

### Parallel Waiting

```python
from aws_expect import expect_all, expect_s3, expect_dynamodb_item

results = expect_all([
    lambda: expect_s3(obj).to_exist(timeout=30),
    lambda: expect_dynamodb_item(table).to_exist(key={"pk": "order-123"}, timeout=30),
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
| `expect_dynamodb_table(dynamodb, table_name)` | Creates `DynamoDBTableExpectation` |
| `expect_sqs(queue)` | Creates `SQSQueueExpectation` |
| `expect_lambda(lambda_client)` | Creates `LambdaFunctionExpectation` |
| `expect_all(callables)` | Runs expectations concurrently |

### S3 (`S3ObjectExpectation`)

| Method | Description |
|--------|-------------|
| `to_exist(timeout, poll_interval, entries)` | Wait for object to exist; optionally match metadata entries |
| `to_not_exist(timeout, poll_interval)` | Wait for object to be deleted |

### DynamoDB Item (`DynamoDBItemExpectation`)

| Method | Description |
|--------|-------------|
| `to_exist(key, timeout, poll_interval, entries)` | Wait for item to exist; optionally match attribute entries |
| `to_not_exist(key, timeout, poll_interval)` | Wait for item to be deleted |
| `to_be_empty(timeout, poll_interval)` | Wait for table to have no items |
| `to_be_not_empty(timeout, poll_interval)` | Wait for table to have at least one item |
| `to_have_numeric_value_close_to(key, field, value, delta, timeout, poll_interval)` | Wait for a numeric field to be within delta of value |

### DynamoDB Table (`DynamoDBTableExpectation`)

| Method | Description |
|--------|-------------|
| `to_exist(timeout, poll_interval)` | Wait for table to exist (Active state) |
| `to_not_exist(timeout, poll_interval)` | Wait for table to be deleted |

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

## Exceptions

All timeout exceptions inherit from `WaitTimeoutError`:

| Exception | Raised by |
|-----------|-----------|
| `S3WaitTimeoutError` | S3 methods |
| `DynamoDBWaitTimeoutError` | DynamoDB methods |
| `SQSWaitTimeoutError` | SQS string-body methods |
| `SQSEventWaitTimeoutError` | SQS JSON event methods |
| `LambdaWaitTimeoutError` | Lambda methods |
| `AggregateWaitTimeoutError` | `expect_all` |
| `DynamoDBNonNumericFieldError` | `to_have_numeric_value_close_to` |
| `SQSUnexpectedMessageError` | `to_not_have_message` (not a timeout) |
| `SQSUnexpectedEventError` | `to_not_have_event` (not a timeout) |

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

## Credits

Built with:
- [boto3](https://github.com/boto/boto3) — AWS SDK for Python
- [testcontainers-python](https://github.com/testcontainers/testcontainers-python) — Testing with real services
- [LocalStack](https://github.com/localstack/localstack) — Local AWS cloud stack
