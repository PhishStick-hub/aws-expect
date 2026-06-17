# Contributing to aws-expect

Thank you for considering contributing to aws-expect! This document provides guidelines and workflows for contributing to the project.

## Table of Contents

- [Development Workflow](#development-workflow)
- [Branch Strategy](#branch-strategy)
- [CI/CD Overview](#cicd-overview)
- [Setting Up Your Environment](#setting-up-your-environment)
- [Making Changes](#making-changes)
- [Running Tests](#running-tests)
- [Code Quality](#code-quality)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)
- [Version Numbering](#version-numbering)

---

## Development Workflow

We use a **single-branch strategy** with feature branches and automated releases via [Release Please](https://github.com/googleapis/release-please):

- **`main`** — Production-ready code
  - Protected branch (requires PR for all changes)
  - Every merge triggers release-please, which opens or updates a release PR
  - When the release PR is merged, a GitHub release and tag are created automatically, which publishes to PyPI

- **`feature/**`, `fix/**`, `chore/**`** — Active development
  - Created from `main` for each feature/fix
  - CI runs quality checks and integration tests on every push
  - Merged to `main` via Pull Request using [Conventional Commits](#version-numbering)

**Workflow diagram:**
```
feature/xxx → PR (conventional commits) → main
                                            ↓
                              release-please opens release PR
                                            ↓ (merge release PR)
                              GitHub Release + tag created
                                            ↓
                                        PyPI (automatic)
```

**Branch naming conventions:**
- `feature/description` — New features
- `fix/description` — Bug fixes
- `chore/description` — Maintenance tasks

---

## Branch Strategy

### Working on Features

1. **Always start from `main`:**
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name   # new feature
   git checkout -b fix/bug-description          # bug fix
   git checkout -b chore/task-description       # maintenance
   ```

3. **Make your changes and commit using Conventional Commits:**
   ```bash
   git add .
   git commit -m "feat(scope): add new waiter for X"
   git push origin feature/your-feature-name
   # ✅ Triggers CI (quality checks + integration tests)
   ```

4. **Create a Pull Request to `main`:**
   ```bash
   gh pr create --base main --head feature/your-feature-name \
     --title "feat(scope): add new waiter for X"
   ```

---

## CI/CD Overview

### On pull request to `main`

| Job | Depends on | What it does |
|-----|------------|--------------|
| Quality Checks | — | `ruff format --check`, `ruff check`, `ty check` |
| Integration Tests | Quality Checks | Full pytest suite (Docker/LocalStack) + coverage, 20 min timeout |
| Build | Quality Checks + Integration Tests | `uv build` + `twine check` (verifies package builds) |

### On merge of release-please PR to `main`

1. release-please creates a GitHub Release and version tag
2. Full CI + build runs against the tagged commit
3. Package is published to PyPI automatically via OIDC trusted publishing

---

## Setting Up Your Environment

### Prerequisites

- **Python 3.13+** (required)
- **uv** package manager (required)
- **Docker** (required for running tests)

### Installation

```bash
# Clone the repository
git clone https://github.com/PhishStick-hub/aws-expect.git
cd aws-expect

# Install all dependencies (including dev dependencies)
uv sync --all-groups

# Verify installation
uv run pytest tests/ -v
```

---

## Making Changes

### Code Style Guidelines

1. **Type Hints**: All functions must have type hints
2. **Docstrings**: Use Google-style docstrings for all public APIs
3. **Formatting**: Code must pass `ruff format`
4. **Linting**: Code must pass `ruff check`
5. **Type Checking**: Code must pass `ty check`

See [AGENTS.md](AGENTS.md) for detailed coding guidelines.

### Before Committing

```bash
uv run ruff format .
uv run ruff check .
uv run ty check
uv run pytest tests/ -v
```

All four checks must pass before pushing.

---

## Running Tests

```bash
# Ensure Docker is running
docker info

# Run all tests
uv run pytest tests/ -v

# Single test file
uv run pytest tests/test_s3_exist.py -v

# Single test method
uv run pytest tests/test_s3_exist.py::TestToExist::test_returns_metadata_when_object_exists -v
```

Tests use **testcontainers** and **LocalStack** to simulate AWS services locally.

---

## Code Quality

### Automated Checks (every push)

1. `ruff format --check` — formatting
2. `ruff check` — linting
3. `ty check` — type checking
4. Full pytest suite (integration tests via Docker/LocalStack)

### Manual Checks

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check && uv run pytest tests/ -v
```

---

## Submitting Changes

### For Contributors (External)

1. Fork the repository on GitHub
2. Clone your fork and create a feature branch from `main`
3. Make your changes using Conventional Commits
4. Push and create a Pull Request to `main`

### For Maintainers (Internal)

```bash
git checkout main && git pull origin main
git checkout -b feature/your-feature
# make changes
git commit -m "feat(scope): description"
git push origin feature/your-feature
gh pr create --base main --head feature/your-feature
```

Direct push to `main` is not allowed. All changes must go through Pull Requests.

### Pull Request Guidelines

- **Target branch**: Always `main`
- **Commit format**: Use [Conventional Commits](#version-numbering) — this drives the automated changelog and version bump
- **Tests**: Include tests for new features
- **Documentation**: Update README.md if adding new public APIs

---

## Release Process

Releases are **fully automated** via [Release Please](https://github.com/googleapis/release-please). Maintainers do not manually bump versions or create tags.

### How it works

1. **Merge PRs to `main` using Conventional Commits.**
   release-please reads the commit history and determines the next version
   (`fix` → patch, `feat` → minor, `feat!` / `BREAKING CHANGE` → major).

2. **release-please opens a release PR** (e.g., "Release v0.7.0") that updates
   `CHANGELOG.md` and the version in `pyproject.toml`.

3. **When the release PR is merged**, release-please creates a GitHub Release
   and a `vX.Y.Z` tag automatically.

4. **The tag triggers `publish-pypi.yml`**, which runs full CI and publishes the
   package to PyPI via OIDC trusted publishing (no API token required).
   No manual approval step is needed — the `pypi` environment gate in GitHub
   provides the protection layer.

### Hotfix Process

Hotfixes follow the same workflow:

```bash
git checkout main && git pull origin main
git checkout -b fix/critical-bug
# fix the bug
git commit -m "fix(scope): description of critical bug"
git push origin fix/critical-bug
gh pr create --base main --head fix/critical-bug --title "fix(scope): ..."
```

After merge, release-please will pick up the `fix` commit and propose a patch
release PR. Merge that PR to trigger the PyPI publish.

---

## Version Numbering

Versions follow **Semantic Versioning** and are managed automatically by release-please based on Conventional Commits.

### Conventional Commits → version bump

| Commit type | Example | Version bump |
|-------------|---------|--------------|
| `fix` | `fix(sqs): handle empty queue` | Patch (`0.6.0` → `0.6.1`) |
| `feat` | `feat(dynamodb): add batch waiter` | Minor (`0.6.1` → `0.7.0`) |
| `feat!` / `BREAKING CHANGE` | `feat(s3)!: rename to_exist` | Major (`0.7.0` → `1.0.0`) |
| `chore`, `docs`, `test`, `ci` | `chore(ci): update workflow` | No bump |

---

## Questions or Issues?

- **Bug reports**: Open an issue on GitHub
- **Feature requests**: Open an issue with [Feature Request] prefix
- **Questions**: Open a discussion on GitHub Discussions
- **Security issues**: Email ivan_shcherbenko@outlook.com privately

---

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help maintain a welcoming community

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
