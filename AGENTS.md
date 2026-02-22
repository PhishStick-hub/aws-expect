# AGENTS.md - aws-expect

This file defines how AI coding agents (OpenCode, Claude Code, etc.) should work in the `aws-expect` repository.

- It is **project-specific** — it describes this repo's conventions, tooling, and expectations.
- Agents should **read and follow this file before making any changes**.
- Keep it **short, accurate, and up to date**.

---

## 1. Project overview

### 1.1 High-level description

`aws-expect` is a Python library providing **declarative waiters for AWS services** (currently S3 and DynamoDB) using `boto3`.

The library focuses on:

- Clear, declarative API: `expect_s3`, `expect_dynamodb` and expectation classes.
- Correct timeout behavior with good error messages.
- Good developer experience: type hints, readable exceptions, and fast tests via LocalStack.

Key properties:

- **Language**: Python 3.13+
- **Package manager**: `uv`
- **Build system**: `hatchling`
- **Test framework**: `pytest` with `testcontainers` / LocalStack
- **Static typing**: `ty`
- **Lint/format**: `ruff`

### 1.2 Non-negotiable principles

Agents should always respect the following:

1. The library is **declarative**: APIs express *intent* ("wait for object to exist") rather than imperative polling logic at call sites.
2. **Correctness and clear error reporting** are more important than minor micro-optimizations.
3. Maintain a **clean, documented public API**:
   - Exports go through `aws_expect.__init__` with `__all__`.
   - Public exceptions and expectation classes are stable and well-named.
4. Keep tests fast and reliable using LocalStack + fixtures.

---

## 2. Repository structure

Current layout:

```text
aws_expect/
├── __init__.py        # Public API exports with __all__
├── exceptions.py      # Exception hierarchy (WaitTimeoutError & derived)
├── expect.py          # Public API entry points (expect_s3, expect_dynamodb)
├── s3.py              # S3ObjectExpectation implementation
└── dynamodb.py        # DynamoDBItemExpectation implementation
tests/
├── conftest.py        # pytest fixtures (LocalStack, boto3 resources)
├── test_s3_*.py       # S3 tests
└── test_dynamodb_*.py # DynamoDB tests
```

Guidelines:

- Runtime code lives under `aws_expect/`.
- Tests live under `tests/` and **mirror** the structure of `aws_expect/`.
- New AWS services or resource types should:
  - Get their own module (e.g. `sqs.py`, `events.py`).
  - Get corresponding tests (`test_sqs_*.py`, etc.).

---

## 3. Tooling and environment

### 3.1 Dependency management with uv

`uv` is the only supported dependency and environment manager.

Common commands:

```bash
# Install all dependencies (including dev)
uv sync --all-groups

# Build package
uv build
```

Guidelines for agents:

- Do **not** introduce `pip`, `poetry`, `pipenv`, or extra `requirements.txt` unless explicitly asked.
- Keep all tool configuration in `pyproject.toml`.
- Never edit `uv.lock` manually; it is managed by `uv`.

### 3.2 Testing with pytest + LocalStack

Tests are run with `pytest` via `uv`. They rely on Docker-based LocalStack / testcontainers.

Typical commands:

```bash
# Run all tests (requires Docker)
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_s3_exist.py -v

# Run a specific test class
uv run pytest tests/test_s3_exist.py::TestToExist -v

# Run a single test method
uv run pytest tests/test_s3_exist.py::TestToExist::test_returns_metadata_when_object_exists -v
```

Testing guidelines:

- Use pytest fixtures from `tests/conftest.py` for AWS resources.
- Organize tests in classes, e.g. `class TestToExist:`.
- Always test both:
  - Success paths (object appears / condition satisfied).
  - Failure paths (timeouts, missing resources, etc.).
- Prefer **short timeouts** in tests (2–10 seconds) for fast feedback.
- Use `threading.Timer` to simulate delayed resource creation for async behavior.
- When adding new waiters:
  - Add tests that cover "resource already exists".
  - Add tests for "resource appears during polling".
  - Add timeout tests that ensure proper exception types/messages.

### 3.3 Type checking with ty

`ty` is used for static type checking.

Commands:

```bash
# Run type checker (activated environment)
ty check

# Or via uv if not activated
uv run ty check
```

Guidelines:

- All function parameters and return types should be annotated.
- `boto3` resources/clients are dynamically typed — use `Any` for them.
- Use modern union syntax: `dict[str, Any] | None` instead of `Optional[dict[str, Any]]`.
- Prefer fixing type errors rather than suppressing them.
- If you must ignore something:
  - Use the narrowest scope possible (`# type: ignore[...]` with a reason in a comment).
  - Consider improving type hints in the library instead of ignoring.

### 3.4 Linting and formatting with ruff

`ruff` is used for linting and formatting.

Commands:

```bash
# Check code with ruff
uv run ruff check aws_expect/ tests/

# Auto-fix issues
uv run ruff check --fix aws_expect/ tests/

# Format code
uv run ruff format aws_expect/ tests/
```

Guidelines:

- Enforce PEP 8 and project style via `ruff`.
- Avoid disabling rules globally unless absolutely necessary.
- Prefer local `# noqa` only with a short justification if you must disable a check.

---

## 4. Code style and design guidelines

### 4.1 Imports

- Use `from __future__ import annotations` when needed for forward references.
- Group imports in this order:
  1. Standard library
  2. Third-party libraries
  3. Local imports from `aws_expect`
- Use absolute imports within the package.

### 4.2 Type hints

- Use type hints for **all** function parameters and return types.
- For AWS / boto3 use `Any`.
- Prefer `dict[str, Any] | None` over `Optional[...]`.

### 4.3 Naming conventions

- **Classes**: `PascalCase`
- **Functions / methods**: `snake_case`
- **Private attributes**: prefixed with `_`
- **Constants**: `UPPER_CASE`
- **Exceptions**:
  - Suffix with `Error`
  - Inherit from `WaitTimeoutError`

### 4.4 Docstrings

Use Google-style docstrings for public API and document:

- Parameters
- Return values
- Raised exceptions

Keep docstrings up to date when behavior changes.

### 4.5 Error handling

- All timeout exceptions must inherit from `WaitTimeoutError`.
- Store relevant context (resource ID, timeout, etc.) inside exceptions.
- Use `raise ... from exc` when wrapping lower-level exceptions.

### 4.6 Git commit messages

Use **Conventional Commits** format with a scope indicating the affected module:

```
<type>(<scope>): <description>
```

**Types**:

- `feat` — new feature or capability
- `fix` — bug fix
- `refactor` — code change that neither fixes a bug nor adds a feature
- `test` — adding or updating tests
- `docs` — documentation changes
- `chore` — maintenance tasks (CI, dependencies, config)

**Scope**: the module or area affected (e.g. `s3`, `dynamodb`, `exceptions`, `ci`, `tests`).

**Breaking changes**: append `!` after the scope to indicate a breaking change.

Examples:

```
feat(dynamodb): add to_not_exist waiter for DynamoDB items
fix(s3)!: change to_exist return type to include metadata
refactor(exceptions): simplify WaitTimeoutError hierarchy
test(s3): add timeout edge-case tests for to_exist
docs(readme): update installation instructions
chore(deps): bump boto3 minimum version
```

Guidelines:

- Keep the description **lowercase** and **imperative** (e.g. "add", not "Added" or "adds").
- Do not end the description with a period.
- Use the body (after a blank line) for additional context if needed.

---

## 5. Key library patterns

### 5.1 Expectation classes

- Accept boto3 client/resource objects in the constructor.
- Store them as private attributes.
- Provide a minimal declarative API (`to_exist`, `to_not_exist`, etc.).
- Support:
  - `timeout: float`
  - `poll_interval: float`
- Keep polling logic internal.

### 5.2 Polling implementation

- Use `time.monotonic()` for deadlines.
- Always perform at least one condition check.
- Raise a specific `*WaitTimeoutError` with a clear message.
- Sleep using `min(poll_interval, remaining_time)`.

---

## 6. Testing best practices

- Use descriptive test class names.
- Test success and failure paths.
- Test edge timing conditions.
- Use fixtures from `tests/conftest.py`.
- Use short timeouts (2–10 seconds).
- Use `threading.Timer` for delayed creation scenarios.

---

## 7. MCP tools / external helpers

Use Context7 MCP (if available) for:

- boto3 documentation lookup
- LocalStack/testcontainers reference
- Typing and API verification

---

## 8. Quality checks (required before completion)

Run in order:

```bash
uv run pytest tests/ -v
uv run ty check
uv run ruff check .
uv run ruff format .
```

Fix all failures before completing the task.

Additional checks:

- Public APIs have docstrings.
- `__all__` is updated.
- No secrets or real AWS calls in tests.

---

## 9. Security and safety rules

- Do not run destructive commands (`rm -rf`, `sudo`, etc.).
- Do not modify system-level configuration.
- Do not commit secrets or credentials.
- Use LocalStack/testcontainers instead of real AWS in tests.

If an action is unsafe:

1. Explain the risk.
2. Propose a safer alternative.
3. Ask for confirmation.

---

## 10. Task execution workflow

1. Restate the task.
2. Locate relevant modules/tests.
3. Plan the change.
4. Implement (tests first if possible).
5. Run quality checks.
6. Summarize changes and files modified.

If blocked:

- Explain why.
- Request missing context.
- Suggest the best possible partial solution.
