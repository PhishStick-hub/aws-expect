# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`aws-expect` is a Python library providing declarative, Pythonic waiters for AWS services (S3, DynamoDB, SQS) using boto3. It allows tests to wait for resource state changes with configurable timeouts and meaningful error messages.

## Commands

**Setup** (requires uv):
```bash
uv sync --all-groups
```

**Tests** (requires Docker running for LocalStack):
```bash
uv run pytest tests/ -v
uv run pytest tests/test_s3_exist.py::TestToExist::test_name -v  # single test
```

**Type checking:**
```bash
uv run ty check
```

**Linting & formatting:**
```bash
uv run ruff check .
uv run ruff format .
uv run ruff check --fix .  # auto-fix
```

**Build:**
```bash
uv build
```

All four checks (pytest, ty, ruff check, ruff format) must pass before merging.

## Architecture

### Package Structure (`aws_expect/`)

- **`expect.py`** — Factory functions: `expect_s3()`, `expect_dynamodb_item()`, `expect_dynamodb_table()`, `expect_sqs()`
- **`s3.py`** — `S3ObjectExpectation`: wraps a boto3 S3 Object resource; uses native boto3 waiters for existence, custom polling for JSON content matching
- **`dynamodb.py`** — `DynamoDBItemExpectation` (wraps a Table resource) and `DynamoDBTableExpectation` (wraps dynamodb resource + table name string); custom polling throughout
- **`sqs.py`** — `SQSQueueExpectation`: wraps a boto3 SQS Queue resource; string-body methods (`to_have_message`, `to_consume_message`, `to_not_have_message`) and JSON event methods (`to_have_event`, `to_consume_event`, `to_not_have_event`) with deep recursive subset matching via `_deep_matches`
- **`parallel.py`** — `expect_all()`: runs multiple zero-argument callables concurrently via ThreadPoolExecutor; returns ordered results or raises `AggregateWaitTimeoutError`
- **`exceptions.py`** — Exception hierarchy rooted at `WaitTimeoutError`; each subclass stores relevant context. `SQSUnexpectedMessageError` and `SQSUnexpectedEventError` inherit `Exception` directly (not `WaitTimeoutError`) as they represent unexpected presence, not a timeout.
- **`__init__.py`** — Defines `__all__` as the public API

### Polling Pattern

All custom waiters follow the same structure:
1. Compute `deadline = time.monotonic() + timeout`
2. Loop: attempt check → success → return; failure → sleep `min(poll_interval, remaining)` → check deadline → raise on expiry
3. Always attempt at least one check before raising timeout

### Testing

Tests use `testcontainers[localstack]` for a session-scoped LocalStack container. Fixtures in `tests/conftest.py` provide session-scoped clients and function-scoped buckets/tables/queues with unique names. Tests use `threading.Timer` to simulate async resource creation. Use short timeouts (2–10 s) in tests.

## Conventions

- **Python 3.13+**, full type annotations required on all code
- **Commit format**: Conventional Commits with scope — `feat(s3): ...`, `fix(dynamodb): ...`, `chore(ci): ...`; breaking changes use `!` (e.g., `feat(s3)!: ...`)
- **Imports**: stdlib → third-party → local, absolute only
- **Exceptions**: all timeout exceptions inherit `WaitTimeoutError`; use `raise NewError(...) from exc` for chaining
- **Docstrings**: Google-style for public API methods
- **Branching**: `feature/`, `fix/`, or `chore/` prefixes; every push to a feature branch auto-publishes a `.devN` version to TestPyPI
