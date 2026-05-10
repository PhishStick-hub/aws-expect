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

**Dead code detection:**
```bash
uv run vulture aws_expect/ tests/
```

**Build:**
```bash
uv build
```

All four checks (pytest, ty, ruff check, ruff format) must pass before merging.

Combined verify:
```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
```

## Git Workflow

- Always run the full test suite (`uv run pytest tests/ -v`) before committing
- Release tagging order: bump version → commit → tag the latest commit → push with `--tags`
- Never add Co-authored-by or other AI tool attribution to commit messages or PR bodies

## Research Before Coding

- Always check Context7 MCP or official documentation before implementing AWS/API solutions
- When reviewing code, use current docs (via Context7) to enrich the review — don't wait to be asked

## Python Toolchain

- Use `uv` for package management, `ruff` for linting/formatting, `ty` for type checking
- Use the boto3 resource API where available; fall back to the client API only when no resource interface exists (e.g., EventBridge)

## Architecture

### Package Structure (`aws_expect/`)

- **`expect.py`** — Factory functions: `expect_s3()`, `expect_dynamodb_item()`, `expect_dynamodb_table()`, `expect_sqs()`, `expect_lambda()`
- **`s3.py`** — `S3ObjectExpectation`: wraps a boto3 S3 Object resource; uses native boto3 waiters for existence, custom polling for JSON content matching
- **`dynamodb.py`** — `DynamoDBItemExpectation` (wraps a Table resource) and `DynamoDBTableExpectation` (wraps dynamodb resource + table name string); custom polling throughout
- **`sqs.py`** — `SQSQueueExpectation`: wraps a boto3 SQS Queue resource; string-body methods (`to_have_message`, `to_consume_message`, `to_not_have_message`) and JSON event methods (`to_have_event`, `to_consume_event`, `to_not_have_event`) with deep recursive subset matching via `_deep_matches`
- **`lambda_function.py`** — `LambdaFunctionExpectation`: wraps a boto3 Lambda **client** (no resource API exists); function name passed per method call. Methods: `to_exist`, `to_not_exist`, `to_be_active`, `to_be_updated` use native boto3 waiters; `to_be_invocable` uses custom polling with optional payload and entries subset matching; `to_respond_with` invokes the function **once** and asserts `statusCode` and/or the JSON-parsed `body` field (shallow subset); raises `LambdaResponseMismatchError` on mismatch (not a waiter).
- **`parallel.py`** — `expect_all()`: runs multiple zero-argument callables concurrently via `ThreadPoolExecutor`; returns ordered results or raises `AggregateWaitTimeoutError`. `expect_any()`: same concurrency model but returns the result of the first callable to succeed; raises `AggregateWaitTimeoutError` only if every callable times out.
- **`exceptions.py`** — Exception hierarchy rooted at `WaitTimeoutError`; each subclass stores relevant context and includes an `actual` field (last-seen value) surfaced in the error message. `LambdaInvocableTimeoutError` is a `LambdaWaitTimeoutError` subclass raised specifically by `to_be_invocable` when `entries` matching fails, carrying `expected` and `actual` payload dicts. `LambdaResponseMismatchError` and `SQSUnexpectedMessageError`/`SQSUnexpectedEventError` inherit `Exception` directly (not `WaitTimeoutError`) as they represent assertion failures, not timeouts.
- **`__init__.py`** — Defines `__all__` as the public API; exports `expect_all`, `expect_any`, `LambdaInvocableTimeoutError`, `LambdaResponseMismatchError` alongside all other factory functions and exception classes

### Polling Pattern

All custom waiters follow the same structure:
1. Compute `deadline = time.monotonic() + timeout`
2. Loop: attempt check → success → return; failure → sleep `min(poll_interval, remaining)` → check deadline → raise on expiry
3. Always attempt at least one check before raising timeout

### SQS-Specific Patterns

- **`_receive_batches` raises `SQSWaitTimeoutError`** — callers that need a different exception type must wrap the loop in `try/except SQSWaitTimeoutError` and re-raise; pass `str(event)` as the `error_hint` argument for event methods.
- **Method triplet order**: `to_have_*` → `to_consume_*` → `to_not_have_*` (matches the existing string-body ordering).
- **Test files**: one file per concern — `test_sqs.py` for string-body methods, `test_sqs_event.py` for JSON event methods.
- **Deferred imports**: during TDD RED phase, don't import exceptions that aren't used yet — ruff F401 will fail.

### Testing

Tests use `testcontainers[localstack]` for a session-scoped LocalStack container. Fixtures in `tests/conftest.py` provide session-scoped clients and function-scoped buckets/tables/queues/functions with unique names. Tests use `threading.Timer` to simulate async resource creation. Use short timeouts (2–10 s) in tests.

**Lambda testing**: LocalStack 4 requires the Docker socket to be mounted (`/var/run/docker.sock`) for Lambda execution. The `localstack` fixture does this automatically. The `lambda_function` fixture creates a Python 3.13 function from an in-memory zip and waits for `function_active_v2` before yielding; teardown ignores `ResourceNotFoundException` in case the test already deleted the function. The `lambda_function_json_body` fixture creates a function whose `body` response field is a JSON-encoded dict (`{"message": "hello", "status": "ok"}`), used for `to_respond_with` tests.

**Lambda handler stubs**: `_make_lambda_zip` deploys handlers via `inspect.getsource` — the function body is extracted verbatim and runs in an isolated Lambda environment with no access to conftest.py's module-level imports. Any stdlib module a handler needs (e.g. `json`) **must** be imported inside the function body with `# noqa: PLC0415`. Moving such imports to the module level breaks the deployed handler at runtime.

## Conventions

- **Python 3.13+**, full type annotations required on all code
- **Commit format**: Conventional Commits with scope — `feat(s3): ...`, `fix(dynamodb): ...`, `chore(ci): ...`; breaking changes use `!` (e.g., `feat(s3)!: ...`). Never add AI tool attribution (e.g., "Generated with Claude Code") to commit messages or PR bodies.
- **Imports**: stdlib → third-party → local, absolute only
- **Exceptions**: all timeout exceptions inherit `WaitTimeoutError`; use `raise NewError(...) from exc` for chaining
- **Docstrings**: Google-style for public API methods
- **Branching**: `feature/`, `fix/`, or `chore/` prefixes; every push to a feature branch auto-publishes a `.devN` version to TestPyPI
- **HTTP constants**: use `http.HTTPStatus` for status codes and `http.HTTPMethod` for method names in tests; skip for invalid sentinel values (e.g. `999`) and for Lambda handler source extracted via `inspect.getsource`
