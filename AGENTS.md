# AGENTS.md - aws-expect Coding Guidelines

This file provides guidance for AI agents working on the aws-expect repository.

## Project Overview

A Python library providing declarative waiters for AWS services (S3, DynamoDB) using boto3.

- **Language**: Python 3.13+
- **Package Manager**: uv
- **Build System**: hatchling
- **Test Framework**: pytest with testcontainers/LocalStack

## Build Commands

```bash
# Install all dependencies (including dev)
uv sync --all-groups

# Run all tests (requires Docker)
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_s3_exist.py -v

# Run a specific test class
uv run pytest tests/test_s3_exist.py::TestToExist -v

# Run a single test method
uv run pytest tests/test_s3_exist.py::TestToExist::test_returns_metadata_when_object_exists -v

# Build package
uv build
```

## Code Style Guidelines

### Imports

- Use `from __future__ import annotations` when needed for forward references
- Group imports: stdlib → third-party → local
- Use absolute imports within the package (e.g., `from aws_expect.exceptions import ...`)

### Type Hints

- Use type hints for all function parameters and return types
- Use `Any` from `typing` for boto3 resources/clients (they're dynamically typed)
- Prefer union syntax: `dict[str, Any] | None` instead of `Optional[dict[str, Any]]`

### Naming Conventions

- **Classes**: PascalCase (e.g., `S3ObjectExpectation`, `WaitTimeoutError`)
- **Functions/Methods**: snake_case (e.g., `to_exist`, `expect_s3`)
- **Private attributes**: prefix with underscore (e.g., `self._table`, `self._bucket`)
- **Constants**: UPPER_CASE for module-level constants
- **Exceptions**: Suffix with `Error`, inherit from base `WaitTimeoutError`

### Docstrings

Use Google-style docstrings:

```python
def to_exist(self, timeout: float = 30) -> dict[str, Any]:
    """Wait for the object to exist.

    Args:
        timeout: Maximum time in seconds to wait.

    Returns:
        The response metadata dict.

    Raises:
        S3WaitTimeoutError: If the object does not exist within timeout.
    """
```

### Error Handling

- All timeout exceptions inherit from `WaitTimeoutError` base class
- Exception constructors should store relevant context (bucket, key, timeout, etc.)
- Use `raise ... from exc` when wrapping exceptions

### Project Structure

```
aws_expect/
├── __init__.py       # Public API exports with __all__
├── exceptions.py     # Exception hierarchy
├── expect.py         # Public API entry points (expect_s3, expect_dynamodb)
├── s3.py            # S3ObjectExpectation implementation
└── dynamodb.py      # DynamoDBItemExpectation implementation
tests/
├── conftest.py      # pytest fixtures (LocalStack, boto3 resources)
├── test_s3_*.py     # S3 tests
└── test_dynamodb_*.py # DynamoDB tests
```

### Key Patterns

**Creating Expectation Classes:**

- Accept boto3 resource objects in constructor
- Store as private attributes (e.g., `self._obj`, `self._table`)
- Use `to_exist()` and `to_not_exist()` method naming
- Support `timeout` and `poll_interval` parameters

**Polling Implementation:**

```python
default_delay = max(1, math.ceil(poll_interval))  # minimum 1 second
deadline = time.monotonic() + timeout
while True:
    # check condition
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError(...)
    time.sleep(min(delay, remaining))
```

### Testing

- Tests use LocalStack containers via testcontainers
- Use pytest fixtures from `conftest.py` for AWS resources
- Tests are organized in classes (e.g., `class TestToExist:`)
- Use short timeouts in tests (2-10 seconds) for fast feedback
- Use threading.Timer for async operations in tests

### Linting and Type Checking

This project uses `ty` for type checking and `ruff` for linting and formatting:

**Type Checking with ty:**

```bash
# Run type checker (activated environment)
ty check

# Run type checker (without activated environment)
uv run ty check
```

**Linting and Formatting with ruff:**

```bash
# Check code with ruff
uv run ruff check aws_expect/ tests/

# Auto-fix issues
uv run ruff check --fix aws_expect/ tests/

# Format code
uv run ruff format aws_expect/ tests/
```

### Exception Handling Pattern

When creating new service waiters, follow this exception pattern:

```python
class ServiceWaitTimeoutError(WaitTimeoutError):
    """Raised when a service wait operation exceeds the specified timeout."""

    def __init__(
        self,
        resource_id: str,
        timeout: float,
        message: str | None = None,
    ) -> None:
        self.resource_id = resource_id
        self.timeout = timeout
        if message is not None:
            msg = message
        else:
            msg = f"Timed out after {timeout}s waiting for {resource_id}"
        super().__init__(msg)
```

### Testing Best Practices

- **Use descriptive test class names**: `TestS3ToExist`, `TestDynamoDBItemOperations`
- **Test both success and failure cases**: Always include timeout/exception tests
- **Use fixtures for resource setup**: Leverage `conftest.py` fixtures
- **Mock time-sensitive operations**: Use `threading.Timer` to simulate delayed operations
- **Test async behavior**: Verify waiters work when resources appear mid-poll
- **Short test timeouts**: Use 2-10 second timeouts in tests for fast feedback

### MCP Tools

Always use Context7 MCP when you need library/API documentation, code generation, code quality verification, setup or configuration steps without the user having to explicitly ask.

### Quality Checks

**IMPORTANT**: After making any changes to the project, you MUST run the following checks in order:

1. **Run local tests**: `uv run pytest tests/ -v` - Ensure all tests pass
2. **Run type checker**: `uv run ty check` (or `ty check` if ty is globally available) - Verify type correctness
3. **Run linter**: `uv run ruff check .` - Check for code issues
4. **Run formatter**: `uv run ruff format .` - Ensure consistent formatting

**If any of these checks fail, you MUST fix the issues before considering the task complete.**

Additional pre-commit checks:

- Verify docstrings are complete for all public APIs
- Ensure `__all__` is updated in `__init__.py` for new exports
- Use Context7 MCP for library/API documentation and code quality verification when needed
