# Contributing to aws-expect

Thank you for considering contributing to aws-expect! This document provides guidelines and workflows for contributing to the project.

## Table of Contents

- [Development Workflow](#development-workflow)
- [Branch Strategy](#branch-strategy)
- [Setting Up Your Environment](#setting-up-your-environment)
- [Making Changes](#making-changes)
- [Running Tests](#running-tests)
- [Code Quality](#code-quality)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)
- [Version Numbering](#version-numbering)

---

## Development Workflow

We use a **two-branch strategy** for development and releases:

- **`develop`** — Active development branch (default)
  - All feature development happens here
  - Automatically publishes to TestPyPI on every push
  - Uses development versions (e.g., `0.1.0.dev1`)

- **`main`** — Production-ready code
  - Only receives changes via Pull Requests from `develop`
  - Tagged releases publish to Production PyPI
  - Uses stable versions (e.g., `0.1.0`)

```
Feature Branch → develop → TestPyPI (automatic)
                    ↓ PR
                  main → PyPI (on tag, manual approval)
```

---

## Branch Strategy

### Working on Features

1. **Always start from `develop`:**
   ```bash
   git checkout develop
   git pull origin develop
   ```

2. **Create a feature branch (optional but recommended):**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes, commit, and push:**
   ```bash
   git add .
   git commit -m "Add feature: your feature description"
   git push origin feature/your-feature-name
   ```

4. **Create a Pull Request to `develop`** (or push directly to `develop` if you're a maintainer)

### Direct Push to `develop` (Maintainers)

If you're a maintainer, you can push directly to `develop`:

```bash
git checkout develop
# Make changes
git add .
git commit -m "Your commit message"
git push origin develop
# ✅ This automatically triggers CI and publishes to TestPyPI
```

### Creating a Production Release

Only maintainers can release to production PyPI:

1. **Prepare the release on `develop`:**
   ```bash
   git checkout develop
   
   # Update version in pyproject.toml (remove .dev suffix)
   # Example: 0.1.1.dev1 → 0.1.1
   
   git add pyproject.toml
   git commit -m "Bump version to 0.1.1 for release"
   git push origin develop
   ```

2. **Create a Pull Request from `develop` to `main`:**
   ```bash
   gh pr create --base main --head develop \
     --title "Release v0.1.1" \
     --body "Release version 0.1.1 with [list changes here]"
   ```

3. **Wait for CI to pass and merge the PR**

4. **Create and push a git tag:**
   ```bash
   git checkout main
   git pull origin main
   
   git tag v0.1.1
   git push origin v0.1.1
   ```

5. **Approve the deployment:**
   - GitHub Actions will trigger the PyPI publish workflow
   - You'll receive a notification to approve the deployment
   - Review the changes and approve to publish to PyPI

6. **Return to `develop` and bump to next dev version:**
   ```bash
   git checkout develop
   git merge main  # Sync any changes from main
   
   # Update version in pyproject.toml to next dev version
   # Example: 0.1.1 → 0.1.2.dev1 or 0.2.0.dev1
   
   git add pyproject.toml
   git commit -m "Bump version to 0.1.2.dev1"
   git push origin develop
   ```

---

## Setting Up Your Environment

### Prerequisites

- **Python 3.13+** (required)
- **uv** package manager (recommended)
- **Docker** (required for running tests)

### Installation

```bash
# Clone the repository
git clone https://github.com/PhishStick-hub/aws-expect.git
cd aws-expect

# Checkout develop branch
git checkout develop

# Install all dependencies (including dev dependencies)
uv sync --all-groups

# Verify installation
uv run pytest tests/ -v
```

### Alternative: Using pip

```bash
# Create virtual environment
python3.13 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

---

## Making Changes

### Code Style Guidelines

This project follows strict code quality standards:

1. **Type Hints**: All functions must have type hints
2. **Docstrings**: Use Google-style docstrings for all public APIs
3. **Formatting**: Code must pass `ruff format`
4. **Linting**: Code must pass `ruff check`
5. **Type Checking**: Code must pass `ty check`

See [AGENTS.md](AGENTS.md) for detailed coding guidelines.

### Before Committing

Always run the quality checks locally:

```bash
# Format code
uv run ruff format .

# Check for linting issues
uv run ruff check .

# Run type checker
uv run ty check

# Run tests
uv run pytest tests/ -v
```

**IMPORTANT:** All four checks must pass before pushing your changes.

---

## Running Tests

### Full Test Suite

```bash
# Ensure Docker is running
docker info

# Run all tests
uv run pytest tests/ -v
```

### Run Specific Tests

```bash
# Single test file
uv run pytest tests/test_s3_exist.py -v

# Single test class
uv run pytest tests/test_s3_exist.py::TestToExist -v

# Single test method
uv run pytest tests/test_s3_exist.py::TestToExist::test_returns_metadata_when_object_exists -v
```

### Test Requirements

- Tests use **testcontainers** and **LocalStack** to simulate AWS services
- Docker must be running for tests to pass
- Tests are run automatically in CI for every push

---

## Code Quality

### Automated Checks

Every push triggers GitHub Actions CI that runs:

1. **Quality Checks**:
   - `ruff format --check` — Verify code formatting
   - `ruff check` — Lint code for issues
   - `ty check` — Type checking

2. **Test Suite**:
   - Full pytest suite with Docker/LocalStack

3. **Build**:
   - Package build verification

### Manual Checks

Before pushing, run locally:

```bash
# Run all checks in sequence
uv run ruff format . && \
  uv run ruff check . && \
  uv run ty check && \
  uv run pytest tests/ -v
```

---

## Submitting Changes

### For Contributors (External)

1. **Fork the repository** on GitHub

2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/aws-expect.git
   cd aws-expect
   ```

3. **Create a feature branch from `develop`:**
   ```bash
   git checkout develop
   git checkout -b feature/your-feature
   ```

4. **Make your changes and commit:**
   ```bash
   git add .
   git commit -m "Add: brief description of changes"
   ```

5. **Push to your fork:**
   ```bash
   git push origin feature/your-feature
   ```

6. **Create a Pull Request** to the `develop` branch (not `main`)

### For Maintainers (Internal)

You can push directly to `develop` or create feature branches:

```bash
git checkout develop
# Make changes
git add .
git commit -m "Your changes"
git push origin develop
```

### Pull Request Guidelines

- **Target branch**: Always create PRs to `develop` (unless it's a hotfix)
- **Title**: Use descriptive titles (e.g., "Add DynamoDB batch item waiter")
- **Description**: Explain what changes you made and why
- **Tests**: Include tests for new features
- **Documentation**: Update README.md if adding new public APIs

---

## Release Process

### Overview

Releases follow this workflow:

```
develop (0.1.1.dev1) → TestPyPI (automatic)
         ↓
   PR to main
         ↓
main (0.1.1) → Tag v0.1.1 → PyPI (manual approval)
         ↓
   Merge back to develop
         ↓
develop (0.1.2.dev1) → Continue development
```

### Detailed Steps (Maintainers Only)

#### 1. Prepare Release on `develop`

```bash
git checkout develop
git pull origin develop

# Edit pyproject.toml: version = "0.1.1" (remove .dev)
git add pyproject.toml
git commit -m "Bump version to 0.1.1 for release"
git push origin develop
```

#### 2. Create Release PR

```bash
gh pr create --base main --head develop \
  --title "Release v0.1.1" \
  --body "## Changes in v0.1.1

- Added feature X
- Fixed bug Y
- Updated documentation Z

Closes #123"
```

#### 3. Review and Merge

- Wait for CI to pass
- Review changes
- Merge PR to `main`

#### 4. Tag and Trigger Release

```bash
git checkout main
git pull origin main

git tag v0.1.1
git push origin v0.1.1
```

This triggers the PyPI publish workflow, which:
- Runs all quality checks and tests
- Builds the package
- **Waits for manual approval** (you'll get a notification)
- Publishes to PyPI after approval
- Creates a GitHub Release with artifacts

#### 5. Approve Deployment

1. Go to: https://github.com/PhishStick-hub/aws-expect/actions
2. Find the "Publish to PyPI" workflow run
3. Click **"Review deployments"**
4. Check the changes and click **"Approve and deploy"**

#### 6. Bump `develop` to Next Version

```bash
git checkout develop
git merge main  # Sync with main

# Edit pyproject.toml: version = "0.1.2.dev1"
git add pyproject.toml
git commit -m "Bump version to 0.1.2.dev1"
git push origin develop
```

### Hotfix Process (Emergency Fixes)

If a critical bug is found in production:

```bash
# 1. Branch from main (not develop)
git checkout main
git checkout -b hotfix/critical-bug

# 2. Fix the bug
git add .
git commit -m "Fix: critical bug description"

# 3. Create PR to main
gh pr create --base main --head hotfix/critical-bug

# 4. After merge, tag immediately
git checkout main
git pull origin main
git tag v0.1.2  # Patch version bump
git push origin v0.1.2

# 5. Backport to develop
git checkout develop
git merge main
git push origin develop
```

---

## Version Numbering

We follow **Semantic Versioning** with development versions:

### Development Versions (on `develop`)

Format: `X.Y.Z.devN`

- `0.1.0.dev1` — First development version
- `0.1.0.dev2` — Second iteration
- `0.2.0.dev1` — Working toward next minor release

**When to increment:**
- Increment `.devN` after significant changes
- Or keep the same dev version (TestPyPI will overwrite)

### Production Versions (on `main`)

Format: `X.Y.Z` (standard semantic versioning)

- **MAJOR** (`X`): Breaking API changes
- **MINOR** (`Y`): New features, backward compatible
- **PATCH** (`Z`): Bug fixes, backward compatible

Examples:
- `0.1.0` → `0.1.1` — Bug fix
- `0.1.1` → `0.2.0` — New feature
- `0.2.0` → `1.0.0` — First stable release or breaking change

---

## Testing Your Changes

### Test from TestPyPI

After pushing to `develop`, test the package from TestPyPI:

```bash
# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  aws-expect

# Note: --extra-index-url is needed for dependencies (boto3)
```

### Test Locally

```bash
# Install in editable mode
uv pip install -e .

# Or with pip
pip install -e .

# Test your changes
python -c "from aws_expect import expect_s3; print('Import successful')"
```

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

---

Thank you for contributing to aws-expect! 🚀
