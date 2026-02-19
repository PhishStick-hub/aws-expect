# Contributing to aws-expect

Thank you for considering contributing to aws-expect! This document provides guidelines and workflows for contributing to the project.

## Table of Contents

- [Development Workflow](#development-workflow)
- [Branch Strategy](#branch-strategy)
- [Feature Branch CI/CD](#feature-branch-cicd)
- [Setting Up Your Environment](#setting-up-your-environment)
- [Making Changes](#making-changes)
- [Running Tests](#running-tests)
- [Code Quality](#code-quality)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)
- [Version Numbering](#version-numbering)

---

## Development Workflow

We use a **single-branch strategy** with feature branches:

- **`main`** — Production-ready code
  - Protected branch (requires PR for all changes)
  - Tagged releases publish to Production PyPI
  - Uses stable versions (e.g., `0.1.0`)

- **Feature Branches** — Active development
  - Created from `main` for each feature/fix
  - Automatically publish to TestPyPI on every push
  - Use development versions (e.g., `0.1.0.dev1`, `0.1.0.dev2`)
  - Merged to `main` via Pull Request

**Workflow diagram:**
```
Feature Branch (0.1.0.dev1) → TestPyPI (automatic)
         ↓ Push (0.1.0.dev2) → TestPyPI (automatic)
         ↓ PR
       main → PyPI (on tag, manual approval)
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

2. **Create a feature branch (required):**
   ```bash
   # For new features
   git checkout -b feature/your-feature-name
   
   # For bug fixes
   git checkout -b fix/bug-description
   
   # For maintenance tasks
   git checkout -b chore/task-description
   ```

3. **Set the development version in `pyproject.toml`:**
   ```toml
   # Example: Starting development for version 0.1.1
   version = "0.1.1.dev1"
   ```

4. **Make your changes, commit, and push:**
   ```bash
   git add .
   git commit -m "Add feature: your feature description"
   git push origin feature/your-feature-name
   # ✅ This automatically triggers CI and publishes to TestPyPI
   ```

5. **If you need to publish another test version:**
   ```bash
   # Increment the dev version in pyproject.toml
   # Example: 0.1.1.dev1 → 0.1.1.dev2
   
   git add pyproject.toml
   git commit -m "Bump dev version for testing"
   git push origin feature/your-feature-name
   # ✅ Publishes new dev version to TestPyPI
   ```
   
   **Note:** TestPyPI does not allow overwriting the same version. You must increment the `.devN` suffix each time you want to publish a new test version.

6. **When ready, create a Pull Request to `main`:**
   ```bash
   # Before creating PR, update version to stable release (remove .dev suffix)
   # Example: 0.1.1.dev2 → 0.1.1
   
   git add pyproject.toml
   git commit -m "Bump version to 0.1.1 for release"
   git push origin feature/your-feature-name
   
   # Create PR
   gh pr create --base main --head feature/your-feature-name \
     --title "Add: your feature description" \
     --body "Describe your changes here"
   ```

### Creating a Production Release

Only maintainers can release to production PyPI:

1. **Ensure your feature branch has the release version:**
   ```bash
   git checkout feature/your-feature-name
   
   # Update version in pyproject.toml (remove .dev suffix)
   # Example: 0.1.1.dev2 → 0.1.1
   
   git add pyproject.toml
   git commit -m "Bump version to 0.1.1 for release"
   git push origin feature/your-feature-name
   ```

2. **Create a Pull Request to `main`:**
   ```bash
   gh pr create --base main --head feature/your-feature-name \
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

---

## Feature Branch CI/CD

### Automatic TestPyPI Publishing

Every push to a feature branch automatically triggers CI/CD that:

1. **Runs Quality Checks**:
   - `ruff format --check` — Verify code formatting
   - `ruff check` — Lint code for issues
   - `ty check` — Type checking

2. **Runs Test Suite**:
   - Full pytest suite with Docker/LocalStack

3. **Publishes to TestPyPI**:
   - Publishes the version specified in `pyproject.toml`
   - Uses dev versions (e.g., `0.1.1.dev1`, `0.1.1.dev2`)

### Version Management in Feature Branches

**Important:** TestPyPI does not allow overwriting existing versions. Each time you want to publish a new test version, you must:

1. **Increment the dev version** in `pyproject.toml`:
   ```toml
   # First iteration
   version = "0.1.1.dev1"
   
   # After making changes and wanting to test again
   version = "0.1.1.dev2"
   
   # After more changes
   version = "0.1.1.dev3"
   ```

2. **Commit and push**:
   ```bash
   git add pyproject.toml
   git commit -m "Bump dev version to 0.1.1.dev2"
   git push origin feature/your-feature
   ```

3. **Verify publication**:
   - Check GitHub Actions for successful publish
   - Verify at https://test.pypi.org/project/aws-expect/

### Testing Your Dev Versions

Install and test your published dev version:

```bash
# Install specific dev version from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  aws-expect==0.1.1.dev2

# Test your changes
python -c "from aws_expect import expect_s3; print('Import successful')"
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

# Checkout main branch
git checkout main

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

3. **Create a feature branch from `main`:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/your-feature  # or fix/... or chore/...
   ```

4. **Set development version in `pyproject.toml`:**
   ```toml
   # Example: version = "0.1.1.dev1"
   # Increment .devN each time you want to publish to TestPyPI
   ```

5. **Make your changes and commit:**
   ```bash
   git add .
   git commit -m "Add: brief description of changes"
   ```

6. **Push to your fork:**
   ```bash
   git push origin feature/your-feature
   # ✅ This automatically publishes to TestPyPI
   ```

7. **Create a Pull Request** to the `main` branch

### For Maintainers (Internal)

Maintainers must also use feature branches and Pull Requests:

```bash
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature

# Set dev version in pyproject.toml (e.g., "0.1.1.dev1")

# Make changes
git add .
git commit -m "Your changes"
git push origin feature/your-feature

# Create PR to main
gh pr create --base main --head feature/your-feature
```

**Note:** Direct push to `main` is not allowed. All changes must go through Pull Requests.

### Pull Request Guidelines

- **Target branch**: Always create PRs to `main`
- **Title**: Use descriptive titles (e.g., "Add DynamoDB batch item waiter")
- **Description**: Explain what changes you made and why
- **Tests**: Include tests for new features
- **Documentation**: Update README.md if adding new public APIs

---

## Release Process

### Overview

Releases follow this workflow:

```
Feature Branch (0.1.1.dev1) → TestPyPI (automatic)
         ↓ Increment version
Feature Branch (0.1.1.dev2) → TestPyPI (automatic)
         ↓ Remove .dev suffix
Feature Branch (0.1.1) → PR to main
         ↓ Merge
       main (0.1.1) → Tag v0.1.1 → PyPI (manual approval)
```

### Detailed Steps (Maintainers Only)

#### 1. Prepare Release in Feature Branch

```bash
git checkout feature/your-feature
git pull origin feature/your-feature

# Edit pyproject.toml: version = "0.1.1" (remove .dev suffix)
git add pyproject.toml
git commit -m "Bump version to 0.1.1 for release"
git push origin feature/your-feature
```

#### 2. Create Release PR

```bash
gh pr create --base main --head feature/your-feature \
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

### Hotfix Process (Emergency Fixes)

Hotfixes follow the same workflow as feature branches:

```bash
# 1. Branch from main
git checkout main
git pull origin main
git checkout -b fix/critical-bug

# 2. Set hotfix version in pyproject.toml
# Example: If main is at 0.1.1, hotfix would be 0.1.2.dev1
# For immediate release, use 0.1.2 (no .dev suffix)

# 3. Fix the bug
git add .
git commit -m "Fix: critical bug description"
git push origin fix/critical-bug

# 4. Create PR to main
gh pr create --base main --head fix/critical-bug \
  --title "Hotfix: critical bug description" \
  --body "Emergency fix for critical bug"

# 5. After merge, tag immediately
git checkout main
git pull origin main
git tag v0.1.2  # Patch version bump
git push origin v0.1.2

# 6. Approve deployment in GitHub Actions (same as regular releases)
```

**Note:** For emergency hotfixes, you can skip the dev version and go straight to the release version (e.g., `0.1.2`) in your PR.

---

## Version Numbering

We follow **Semantic Versioning** with development versions:

### Development Versions (on Feature Branches)

Format: `X.Y.Z.devN`

- `0.1.0.dev1` — First development version
- `0.1.0.dev2` — Second iteration
- `0.1.0.dev3` — Third iteration
- `0.2.0.dev1` — Working toward next minor release

**When to increment:**
- **Required:** You MUST increment `.devN` before each push if you want to publish to TestPyPI
- TestPyPI does not allow overwriting existing versions
- Each push to a feature branch triggers automatic TestPyPI publish
- Example workflow:
  - Initial: `0.1.1.dev1` → push → publishes to TestPyPI
  - Make changes, bump to `0.1.1.dev2` → push → publishes to TestPyPI
  - Make changes, bump to `0.1.1.dev3` → push → publishes to TestPyPI
  - Ready for release: remove `.dev3` → `0.1.1` → PR to main

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

After pushing to your feature branch, your dev version is automatically published to TestPyPI. You can test it:

```bash
# Install from TestPyPI (replace X.Y.Z.devN with your version)
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  aws-expect==0.1.1.dev1

# Note: --extra-index-url is needed for dependencies (boto3)
```

**Tip:** Check TestPyPI to verify your version was published: https://test.pypi.org/project/aws-expect/

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
