# AGENTS.md

## Commands

```bash
uv sync --all-groups                                        # install
uv run pytest tests/ -v                                     # all tests (Docker required)
uv run pytest tests/test_s3_exist.py::TestToExist::test_name -v  # single test
uv run ruff check . && uv run ruff format --check . && uv run ty check  # verify
uv run vulture aws_expect/ tests/                           # dead code
uv build                                                    # build
```

CI runs: `ruff format --check` → `ruff check` → `ty check` → `pytest` (20 min timeout). All must pass.

## Architecture

- **`aws_expect/expect.py`** — factory functions: `expect_s3`, `expect_dynamodb_item`, `expect_dynamodb_table`, `expect_sqs`, `expect_lambda`
- **`aws_expect/s3.py`** — `S3ObjectExpectation`; native boto3 waiters for existence, custom polling for JSON content matching
- **`aws_expect/dynamodb.py`** — `DynamoDBItemExpectation` (single-item `get_item` operations) + `DynamoDBTableExpectation` (table-level `describe_table` + `scan` operations); both accept a `Table` resource
- **`aws_expect/sqs.py`** — `SQSQueueExpectation`; string-body methods + JSON event methods with deep subset matching via `_deep_matches`
- **`aws_expect/lambda_function.py`** — `LambdaFunctionExpectation`; uses boto3 **client** (no resource API). `to_respond_with` is not a waiter — asserts immediately
- **`aws_expect/parallel.py`** — `expect_all` / `expect_any`; `ThreadPoolExecutor`, accepts callables or `(fn, *args)` tuples
- **`aws_expect/_utils.py`** — shared internal helpers: `_matches_entries` (shallow subset), `_deep_matches` (recursive subset), `_format_timeout_error` (structured error messages), `_check_stop_condition` (stop_when predicate evaluation), `_truncate_value`, `_compute_delay`, `_build_waiter_config`
- **`aws_expect/exceptions.py`** — hierarchy rooted at `WaitTimeoutError`; `LambdaResponseMismatchError`, `SQSUnexpectedMessageError`/`SQSUnexpectedEventError`, `S3UnexpectedContentError`, `S3ObjectAppearedError`, `DynamoDBUnexpectedItemError`, `DynamoDBNonNumericFieldError`, `DynamoDBInvalidTimestampError`, `StopConditionMetError`, `StopConditionError` inherit `Exception` directly (assertion failures, not timeouts)
- **`aws_expect/__init__.py`** — public API via `__all__`; update when adding exports; version string lives here **and** in `pyproject.toml` — release-please manages both, never bump manually

## Testing gotchas

- Tests use `testcontainers[localstack]` with session-scoped container; fixtures in `tests/conftest.py`
- Lambda handlers deployed via `inspect.getsource` — stdlib imports (e.g. `json`) **must** be inside the function body with `# noqa: PLC0415`, not at module level
- LocalStack 4 requires Docker socket mount (`/var/run/docker.sock`) for Lambda execution — the `localstack` fixture handles this
- Use `threading.Timer` for delayed resource creation; short timeouts (2–10 s)
- Use `http.HTTPStatus` for status codes and `http.HTTPMethod` for method names in tests; skip for invalid sentinels (e.g. `999`)
- SQS: `_receive_batches` raises `SQSWaitTimeoutError` — callers needing a different exception must wrap in `try/except` and re-raise
- During TDD RED: don't import exceptions not yet used — ruff F401 will fail

## Conventions

- Python 3.13+, full type annotations required; `dict[str, Any] | None` over `Optional[...]`; boto3 types use `Any`
- Use boto3 **resource API** where available; fall back to client only when no resource interface exists (e.g. Lambda, EventBridge)
- Conventional Commits with scope: `feat(s3): ...`, `fix(dynamodb): ...`; breaking: `feat(s3)!: ...`
- Never add AI tool attribution (Co-authored-by, "Generated with...") to commits or PRs
- Google-style docstrings for public API; exceptions suffix `Error`, inherit `WaitTimeoutError`
- Branches: `feature/`, `fix/`, `chore/` prefixes; `release/` for TestPyPI dev builds
