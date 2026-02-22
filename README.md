# AWS Expect

Declarative, Pythonic waiters for AWS services using boto3 resources.

## Features

- **Declarative syntax**: `expect_s3(obj).to_exist(timeout=30)`
- **Native boto3 waiters**: Uses AWS's built-in waiter infrastructure
- **Testing-friendly**: Perfect for integration tests and CI/CD
- **Resource-based**: Works with boto3 resource objects (not low-level clients)
- **Flexible timeouts**: Configure both timeout and poll intervals

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

try:
    metadata = expect_s3(obj).to_exist(timeout=30, poll_interval=5)
    print(f"Object exists! Size: {metadata['ContentLength']} bytes")
except S3WaitTimeoutError:
    print("Object did not appear within 30 seconds")

expect_s3(obj).to_not_exist(timeout=10, poll_interval=2)
```

### DynamoDB Item Waiting

```python
import boto3
from aws_expect import expect_dynamodb_item, DynamoDBWaitTimeoutError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("orders")

try:
    item = expect_dynamodb_item(table).to_exist(
        key={"pk": "order-123"},
        timeout=30,
        poll_interval=5,
    )
    print(f"Order found: {item}")
except DynamoDBWaitTimeoutError:
    print("Item did not appear within 30 seconds")

item = expect_dynamodb_item(table).to_exist(
    key={"pk": "order-123"},
    entries={"status": "shipped"},
    timeout=60,
    poll_interval=5,
)

expect_dynamodb_item(table).to_not_exist(key={"pk": "order-123"}, timeout=10)
```

### Catching Any Timeout

All service-specific exceptions inherit from `WaitTimeoutError`, so you can catch timeouts from any service in a single handler:

```python
from aws_expect import expect_s3, WaitTimeoutError

try:
    expect_s3(obj).to_exist(timeout=30)
except WaitTimeoutError:
    print("Timed out waiting for resource")
```

## API Reference

| Function | Description | Returns |
|----------|-------------|----------|
| `expect_s3(s3_object)` | Creates `S3ObjectExpectation` wrapper | `S3ObjectExpectation` |
| `expect_dynamodb_item(table)` | Creates `DynamoDBItemExpectation` wrapper | `DynamoDBItemExpectation` |

| Method | Description | Raises |
|--------|-------------|-------|
| `to_exist(timeout=30, poll_interval=5)` | Waits for resource to exist | `S3WaitTimeoutError` / `DynamoDBWaitTimeoutError` |
| `to_not_exist(timeout=30, poll_interval=5)` | Waits for resource to not exist | `S3WaitTimeoutError` / `DynamoDBWaitTimeoutError` |

**S3 Parameters**: `timeout` (float), `poll_interval` (float, min 1)

**DynamoDB Parameters**: `key` (dict), `timeout` (float), `poll_interval` (float, min 1), `entries` (dict, optional)

## Exceptions

All timeout exceptions inherit from `WaitTimeoutError`:

- **S3WaitTimeoutError**: attributes include `bucket`, `key`, `timeout`
- **DynamoDBWaitTimeoutError**: attributes include `table_name`, `key`, `timeout`

## How It Works

**S3** — uses boto3's native waiter infrastructure:
- `to_exist()` → `client.get_waiter("object_exists").wait()`
- `to_not_exist()` → `client.get_waiter("object_not_exists").wait()`

**DynamoDB** — uses a custom polling loop over `get_item` (DynamoDB does not provide built-in item-level waiters):
- `to_exist()` → polls `table.get_item(Key=...)` until the item appears and optionally matches expected entries
- `to_not_exist()` → polls `table.get_item(Key=...)` until the item is gone

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

## Future Roadmap

- [x] DynamoDB item waiters
- [ ] Lambda function readiness waiters
- [ ] More S3 matchers (content-type, size, tags)

## License

MIT License - see LICENSE file for details.

## Author

Ivan Shcherbenko

## Credits

Built with:
- [boto3](https://github.com/boto/boto3) — AWS SDK for Python
- [testcontainers-python](https://github.com/testcontainers/testcontainers-python) — Testing with real services
- [LocalStack](https://github.com/localstack/localstack) — Local AWS cloud stack