# AWS Expect

Declarative, Pythonic waiters for AWS services using boto3 resources.

## Features

- 🎯 **Declarative syntax**: `expect_s3(obj).to_exist(timeout=30)`
- 🔄 **Native boto3 waiters**: Uses AWS's built-in waiter infrastructure
- 🧪 **Testing-friendly**: Perfect for integration tests and CI/CD
- 📦 **Resource-based**: Works with boto3 resource objects (not low-level clients)
- ⏱️ **Flexible timeouts**: Configure both timeout and poll intervals

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

# Create S3 resource and object
s3 = boto3.resource("s3")
obj = s3.Object("my-bucket", "report.csv")

# Wait for object to exist (returns metadata)
try:
    metadata = expect_s3(obj).to_exist(timeout=30, poll_interval=5)
    print(f"Object exists! Size: {metadata['ContentLength']} bytes")
except S3WaitTimeoutError:
    print("Object did not appear within 30 seconds")

# Wait for object to be deleted
expect_s3(obj).to_not_exist(timeout=10, poll_interval=2)
```

### DynamoDB Item Waiting

```python
import boto3
from aws_expect import expect_dynamodb, DynamoDBWaitTimeoutError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("orders")

# Wait for an item to exist (by primary key)
try:
    item = expect_dynamodb(table).to_exist(
        key={"pk": "order-123"},
        timeout=30,
        poll_interval=5,
    )
    print(f"Order found: {item}")
except DynamoDBWaitTimeoutError:
    print("Item did not appear within 30 seconds")

# Wait for an item with specific field values (subset match)
item = expect_dynamodb(table).to_exist(
    key={"pk": "order-123"},
    entries={"status": "shipped"},
    timeout=60,
    poll_interval=5,
)

# Composite key (partition + sort key)
item = expect_dynamodb(table).to_exist(
    key={"pk": "user-1", "sk": "order-456"},
    timeout=30,
)

# Wait for an item to be deleted
expect_dynamodb(table).to_not_exist(key={"pk": "order-123"}, timeout=10)
```

### Catching Any Timeout

All service-specific exceptions inherit from `WaitTimeoutError`, so you can
catch timeouts from any service in a single handler:

```python
from aws_expect import expect_s3, WaitTimeoutError

try:
    expect_s3(obj).to_exist(timeout=30)
except WaitTimeoutError:
    print("Timed out waiting for resource")
```

## API Reference

### `expect_s3(s3_object)`

Creates an `S3ObjectExpectation` wrapper for an S3 resource Object.

**Parameters**:
- `s3_object`: A `boto3.resource("s3").Object(bucket, key)` instance

**Returns**: `S3ObjectExpectation`

---

### `expect_dynamodb(table)`

Creates a `DynamoDBItemExpectation` wrapper for a DynamoDB Table resource.

**Parameters**:
- `table`: A `boto3.resource("dynamodb").Table(name)` instance

**Returns**: `DynamoDBItemExpectation`

---

### `S3ObjectExpectation.to_exist(timeout=30, poll_interval=5)`

Wait for the S3 object to exist using the native `object_exists` waiter.

**Parameters**:
- `timeout` (float): Maximum time in seconds to wait (default: 30)
- `poll_interval` (float): Time in seconds between polling attempts, minimum 1 (default: 5)

**Returns**: `dict[str, Any]` — The `head_object` response metadata

**Raises**: `S3WaitTimeoutError` — If the object does not exist within timeout

**Example**:
```python
metadata = expect_s3(obj).to_exist(timeout=60, poll_interval=10)
print(metadata["ETag"], metadata["ContentType"])
```

---

### `S3ObjectExpectation.to_not_exist(timeout=30, poll_interval=5)`

Wait for the S3 object to not exist (be deleted) using the native `object_not_exists` waiter.

**Parameters**:
- `timeout` (float): Maximum time in seconds to wait (default: 30)
- `poll_interval` (float): Time in seconds between polling attempts, minimum 1 (default: 5)

**Returns**: `None`

**Raises**: `S3WaitTimeoutError` — If the object still exists after timeout

---

### `DynamoDBItemExpectation.to_exist(key, timeout=30, poll_interval=5, entries=None)`

Poll `get_item` until the item exists and optionally matches the expected entries.

**Parameters**:
- `key` (dict[str, Any]): Primary key dict, e.g. `{"pk": "val"}` or `{"pk": "val", "sk": "val"}`
- `timeout` (float): Maximum time in seconds to wait (default: 30)
- `poll_interval` (float): Time in seconds between polling attempts, minimum 1 (default: 5)
- `entries` (dict[str, Any] | None): Optional expected key-value pairs. When provided, the item must contain **at least** these entries (subset match) before the wait succeeds.

**Returns**: `dict[str, Any]` — The full item from DynamoDB

**Raises**: `DynamoDBWaitTimeoutError` — If the item does not exist or does not match entries within timeout

**Example**:
```python
item = expect_dynamodb(table).to_exist(
    key={"pk": "order-1"},
    entries={"status": "shipped"},
    timeout=60,
)
print(item["status"], item["total"])
```

---

### `DynamoDBItemExpectation.to_not_exist(key, timeout=30, poll_interval=5)`

Poll `get_item` until the item no longer exists.

**Parameters**:
- `key` (dict[str, Any]): Primary key dict
- `timeout` (float): Maximum time in seconds to wait (default: 30)
- `poll_interval` (float): Time in seconds between polling attempts, minimum 1 (default: 5)

**Returns**: `None`

**Raises**: `DynamoDBWaitTimeoutError` — If the item still exists after timeout

---

### Exceptions

#### `WaitTimeoutError`

Base exception for all wait timeout errors. Catch this to handle timeouts from any AWS service.

**Attributes**:
- `timeout` (float): The timeout value that was exceeded

#### `S3WaitTimeoutError(WaitTimeoutError)`

Raised when an S3 wait operation exceeds the specified timeout.

**Attributes**:
- `bucket` (str): The S3 bucket name
- `key` (str): The S3 object key
- `timeout` (float): The timeout value that was exceeded

#### `DynamoDBWaitTimeoutError(WaitTimeoutError)`

Raised when a DynamoDB wait operation exceeds the specified timeout.

**Attributes**:
- `table_name` (str): The DynamoDB table name
- `key` (dict[str, str]): The primary key that was being waited on
- `timeout` (float): The timeout value that was exceeded

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
# Clone the repository
git clone https://github.com/PhishStick-hub/aws-expect
cd aws-expect

# Install with dev dependencies
uv sync --all-groups
```

### Running Tests

Tests use testcontainers and LocalStack for real AWS API simulation:

```bash
# Ensure Docker is running
docker info

# Run tests
uv run pytest tests/ -v
```

### Project Structure

```
aws-expect/
├── aws_expect/
│   ├── __init__.py          # Public API exports
│   ├── exceptions.py        # WaitTimeoutError hierarchy
│   ├── expect.py            # expect_s3(), expect_dynamodb()
│   ├── dynamodb.py          # DynamoDBItemExpectation
│   └── s3.py                # S3ObjectExpectation
├── tests/
│   ├── conftest.py          # LocalStack fixtures
│   ├── test_dynamodb_item.py
│   ├── test_s3_exist.py
│   └── test_s3_not_exist.py
└── pyproject.toml
```

## Future Roadmap

- [x] DynamoDB item waiters
- [ ] Lambda function readiness waiters
- [ ] More S3 matchers (content-type, size, tags)

## License

MIT License - see LICENSE file for details

## Author

Ivan Shcherbenko

## Credits

Built with:
- [boto3](https://github.com/boto/boto3) — AWS SDK for Python
- [testcontainers-python](https://github.com/testcontainers/testcontainers-python) — Testing with real services
- [LocalStack](https://github.com/localstack/localstack) — Local AWS cloud stack
