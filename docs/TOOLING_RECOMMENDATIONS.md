# Tooling Recommendations for QuizWeaver

> Researched 2026-02-12 | Python 3.14 | Flask + SQLAlchemy + SQLite
> Codebase: 37 source files (13,475 lines), 72 test files (20,727 lines), 1,381+ tests

This document evaluates development tools and plugins for QuizWeaver.
Each recommendation includes what it does, why it helps, effort to adopt,
priority, and downsides.

---

## Table of Contents

1. [Linting and Formatting: Ruff](#1-linting-and-formatting-ruff)
2. [Type Checking: mypy vs pyright](#2-type-checking-mypy-vs-pyright)
3. [Pre-commit Framework](#3-pre-commit-framework)
4. [Test Coverage: pytest-cov](#4-test-coverage-pytest-cov)
5. [Dependency Management: uv vs poetry vs pip-tools](#5-dependency-management-uv-vs-poetry-vs-pip-tools)
6. [Documentation Generation: MkDocs vs Sphinx](#6-documentation-generation-mkdocs-vs-sphinx)
7. [Database Migrations: Alembic vs Current Runner](#7-database-migrations-alembic-vs-current-runner)
8. [CI/CD: GitHub Actions](#8-cicd-github-actions)
9. [Security Scanning: Bandit + pip-audit](#9-security-scanning-bandit--pip-audit)
10. [Editor/IDE Tools](#10-editoride-tools)
11. [Claude Code Tools](#11-claude-code-tools)
12. [Python Packaging: pyproject.toml](#12-python-packaging-pyprojecttoml)
13. [Summary Matrix](#13-summary-matrix)
14. [Recommended Adoption Order](#14-recommended-adoption-order)

---

## 1. Linting and Formatting: Ruff

**What it does:** Ruff is an extremely fast Python linter and formatter written
in Rust. It replaces flake8, black, isort, pydocstyle, pyupgrade, and autoflake
in a single tool. It runs 150-200x faster than flake8.

**Why it helps QuizWeaver:**
- 34,000+ lines with zero linting or formatting today means inconsistent style
- One tool replaces many (no need to install/configure black + isort + flake8)
- Auto-fix mode can clean up most issues automatically on first run
- Configurable via `pyproject.toml` (consolidates project config)
- Catches real bugs: unused imports, unreachable code, f-string issues

**Effort:** LOW
- Install: `pip install ruff`
- First run: `ruff check --fix .` then `ruff format .` to auto-fix
- Config: ~15 lines in pyproject.toml
- Expect 30-60 minutes for initial cleanup pass

**Priority:** P1 (highest value-to-effort ratio of any tool here)

**Downsides:**
- First run on 34k lines will produce many warnings (use `--fix` to auto-resolve most)
- Team must agree on formatting style (Ruff defaults match Black, which is standard)
- Some rules may conflict with QuizWeaver patterns (e.g., broad exception catches
  are intentional in migration runner) -- use per-line `# noqa` or config excludes

**Recommended config (pyproject.toml):**
```toml
[tool.ruff]
target-version = "py39"  # Match minimum Python version
line-length = 120  # Slightly wider than default 88, matches existing style

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
# E=pycodestyle, F=pyflakes, W=warnings, I=isort, UP=pyupgrade,
# B=bugbear, SIM=simplify
ignore = ["E501"]  # Line length handled by formatter

[tool.ruff.format]
quote-style = "double"
```

**References:**
- [Ruff documentation](https://docs.astral.sh/ruff/)
- [Ruff GitHub](https://github.com/astral-sh/ruff)
- [Real Python: Ruff guide](https://realpython.com/ruff-python/)

---

## 2. Type Checking: mypy vs pyright

**What they do:** Static type checkers that analyze Python code for type errors
without running it. They catch bugs like passing a string where an int is expected.

**Why it helps QuizWeaver:**
- Many functions pass config dicts, JSON data, and ORM objects -- type errors
  are a real risk (e.g., the `q.data.items` vs `q.data['items']` Jinja2 bug)
- SQLAlchemy 2.0+ has native type support without plugins
- Gradual typing is possible: add types to new code, leave old code untyped

**mypy vs pyright comparison for this project:**

| Factor | mypy | pyright |
|--------|------|---------|
| Speed | Slower (pure Python) | 3-5x faster |
| SQLAlchemy 2.0 | Native support (no plugin needed) | Native support |
| Flask support | Partial (dynamic runtime) | Partial (dynamic runtime) |
| Plugin system | Yes (but SA plugin deprecated) | No |
| VS Code integration | Good | Excellent (built into Pylance) |
| Config | pyproject.toml | pyproject.toml or pyrightconfig.json |

**Recommendation:** **Defer to P3.** The codebase has zero type annotations today.
Adding types to 13,000+ lines of source is a large effort with modest payoff for
a teacher-facing app. If adopted later, start with **mypy** in `--ignore-missing-imports`
mode on new files only.

**Effort:** HIGH (to type existing code), LOW (for new code only with `--ignore-missing-imports`)

**Priority:** P3

**Downsides:**
- Flask and Jinja2 are highly dynamic -- type checkers produce many false positives
- SQLAlchemy ORM queries are hard to type correctly
- Adds friction to rapid feature development
- QuizWeaver uses `dict` for config, JSON data, and quiz data throughout -- would
  need TypedDict or dataclasses to get real value from typing

**References:**
- [SQLAlchemy 2.0 Mypy documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html)
- [Pyright guide (DataCamp)](https://www.datacamp.com/tutorial/pyright)

---

## 3. Pre-commit Framework

**What it does:** A framework that manages and maintains multi-language pre-commit
hooks. Hooks run automatically before each git commit to enforce code quality.

**Why it helps QuizWeaver:**
- QuizWeaver already has a custom bash pre-commit hook for secret detection
- The `pre-commit` framework is more maintainable, auto-updates hooks, and
  supports dozens of hook types (ruff, trailing whitespace, YAML lint, etc.)
- Single `.pre-commit-config.yaml` replaces the custom bash script
- Can include the secret detection patterns via `detect-secrets` hook

**Effort:** LOW-MEDIUM
- Install: `pip install pre-commit`
- Create `.pre-commit-config.yaml`
- Migrate secret patterns from custom hook
- Run `pre-commit install` to activate

**Priority:** P2 (adopt after Ruff, bundle them together)

**Downsides:**
- Another tool to install (though `pre-commit install` is a one-time setup)
- Custom secret detection patterns would need mapping to `detect-secrets` or
  a custom hook within the framework
- First run on existing files may take a moment to download hook environments
- Teachers installing QuizWeaver may not need/want pre-commit (dev-only tool)

**Recommended config (.pre-commit-config.yaml):**
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0  # pin to latest stable
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: detect-private-key
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

**References:**
- [pre-commit.com](https://pre-commit.com/)
- [Ruff pre-commit hook](https://github.com/astral-sh/ruff-pre-commit)
- [detect-secrets](https://github.com/Yelp/detect-secrets)

---

## 4. Test Coverage: pytest-cov

**What it does:** Measures which lines of source code are executed during tests.
Reports uncovered lines, branches, and generates HTML reports.

**Why it helps QuizWeaver:**
- 1,381 tests is impressive, but without coverage data there is no way to know
  which code paths are untested
- Likely to reveal gaps in error handling, edge cases, and rarely-used code paths
- HTML reports make it easy to visually identify untested code
- Branch coverage catches cases where only one side of an `if/else` is tested
- Useful for prioritizing future test writing

**Effort:** LOW
- Install: `pip install pytest-cov`
- Run: `pytest --cov=src --cov-report=html --cov-report=term-missing`
- Add to pytest config in `pyproject.toml`

**Priority:** P1

**Downsides:**
- Coverage slows test execution by ~20-30% (only enable when needed, not every run)
- 100% coverage is not a useful goal -- it leads to testing trivial code
- Coverage numbers can be misleading (high coverage does not mean good tests)
- HTML report files should be gitignored

**Recommended config (pyproject.toml):**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.coverage.run]
source = ["src"]
branch = true
omit = ["src/migrations.py", "src/image_gen.py"]

[tool.coverage.report]
show_missing = true
skip_covered = true
fail_under = 0  # Start with no threshold, increase over time
```

**Estimated outcome:** Based on the test file names vs source files, likely
coverage in the 70-85% range. Expected gaps: `src/ingestion.py`, `src/output.py`,
`src/image_gen.py`, `src/review.py` (interactive/file-dependent modules).

**References:**
- [pytest-cov GitHub](https://github.com/pytest-dev/pytest-cov)
- [Coverage.py docs](https://coverage.readthedocs.io/)
- [Flask testing with coverage](https://flask.palletsprojects.com/en/stable/tutorial/tests/)

---

## 5. Dependency Management: uv vs poetry vs pip-tools

**What they do:** Tools for managing Python dependencies with lockfiles,
reproducible builds, and virtual environments.

**Current state:** QuizWeaver uses a flat `requirements.txt` with 13 unpinned
dependencies (e.g., `flask` not `flask==3.1.0`). This means builds are not
reproducible -- different installs may get different versions.

### Comparison

| Factor | requirements.txt (current) | pip-tools | poetry | uv |
|--------|---------------------------|-----------|--------|-----|
| Lockfile | No | Yes (requirements.lock) | Yes (poetry.lock) | Yes (uv.lock) |
| Speed | Baseline | ~1x | ~1x | 10-100x faster |
| Learning curve | None | Low | Medium | Low |
| Virtual env mgmt | Manual | Manual | Automatic | Automatic |
| Python version mgmt | No | No | No | Yes |
| pyproject.toml | No | Optional | Required | Required |
| Maturity | Standard | Mature | Mature | Newer (2024+) |

**Recommendation:** **uv**

uv is the clear winner for QuizWeaver because:
- Fastest install times (matters for teacher onboarding -- `run.bat` runs pip install)
- Manages Python versions (could simplify `run.bat` by removing Python detection)
- Lockfile ensures reproducible installs
- Simple migration from requirements.txt: `uv init --from requirements.txt`
- Single binary, no Python dependency to bootstrap
- Astral (same team as Ruff) maintains both tools

**Effort:** MEDIUM
- Install uv, run `uv init` to generate pyproject.toml
- Move dependencies from requirements.txt to pyproject.toml
- Generate lockfile: `uv lock`
- Update `run.bat` / `run.sh` to use `uv sync` instead of `pip install -r requirements.txt`
- Update INSTALLATION.md

**Priority:** P2

**Downsides:**
- uv is newer (2024) -- less community knowledge than poetry
- Teachers who already have pip may be confused by a new tool
- Could keep requirements.txt alongside for pip fallback
- uv on Windows requires separate installer

**References:**
- [uv documentation](https://docs.astral.sh/uv/)
- [uv PyPI](https://pypi.org/project/uv/)
- [Poetry vs UV comparison](https://medium.com/@hitorunajp/poetry-vs-uv-which-python-package-manager-should-you-use-in-2025-4212cb5e0a14)

---

## 6. Documentation Generation: MkDocs vs Sphinx

**What they do:** Generate browsable documentation websites from Markdown
(MkDocs) or reStructuredText (Sphinx) files.

**Current state:** QuizWeaver has 9 markdown docs in `docs/` plus CLAUDE.md,
INSTALLATION.md, and README.md. These are readable on GitHub but not searchable
or navigable as a site.

### Comparison

| Factor | MkDocs + Material | Sphinx |
|--------|-------------------|--------|
| Source format | Markdown | reStructuredText (or MyST Markdown) |
| Setup | Simple YAML | Complex conf.py |
| Theme quality | Material is excellent | Varies |
| API docs from docstrings | mkdocstrings plugin | autodoc (built-in) |
| Search | Built-in | Built-in |
| Learning curve | Low | High |

**Recommendation:** **Defer to P3.** QuizWeaver is a teacher-facing app, not a
developer library. The existing markdown docs are sufficient. If documentation
becomes important (e.g., for community contributions), use **MkDocs + Material**
theme because:
- Existing docs are already Markdown (zero conversion needed)
- Material theme looks professional out of the box
- `mkdocstrings` can auto-generate API docs from Python docstrings
- GitHub Pages deployment is trivial

**Effort:** LOW (basic setup), MEDIUM (with API docs and deployment)

**Priority:** P3

**Downsides:**
- Another tool to maintain
- Docs need to stay in sync with code (can go stale)
- For a local-first app, web docs may be overkill

**References:**
- [MkDocs](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfundamentals.com/mkdocs-material/)
- [mkdocstrings](https://mkdocstrings.github.io/)

---

## 7. Database Migrations: Alembic vs Current Runner

**What they do:** Manage database schema changes over time with versioned
migration scripts.

**Current state:** QuizWeaver has a custom migration runner (`src/migrations.py`)
that:
- Reads `.sql` files from `migrations/` sorted alphabetically
- Executes each statement with error handling for "duplicate column" etc.
- Has 11 migration files (001-009, with three 009 files)
- Is idempotent -- safe to re-run
- Works directly with raw SQLite connections (not SQLAlchemy)

### Trade-offs

| Factor | Current Custom Runner | Alembic / Flask-Migrate |
|--------|----------------------|------------------------|
| Complexity | Simple (~100 lines) | Complex (200+ lines config) |
| Auto-generation | No | Yes (compares models to DB) |
| Version tracking | File sort order | Dedicated version table |
| Rollback | No | Yes (downgrade scripts) |
| Multi-DB support | SQLite only | Any SQLAlchemy dialect |
| Team collaboration | Numbered files sort naturally | DAG-based version chain |
| Learning curve | None (already built) | Medium |

**Recommendation:** **Keep the current runner.** Here is why:

1. The custom runner works, is battle-tested across 11 migrations, and is understood
2. QuizWeaver uses SQLite exclusively (no multi-DB need)
3. Alembic's auto-generation would require refactoring ORM models to use
   SQLAlchemy 2.0 `Mapped[]` annotations
4. The numbered-file approach (001, 002, ...) is actually recommended by teams
   that have outgrown Alembic's DAG model
5. Adding Alembic now would require migrating the existing version history
6. The "three 009 files" pattern is unusual but works -- Alembic would reject this

**If migrating later (P3):** Consider Flask-Migrate (wraps Alembic with Flask
integration) only if QuizWeaver needs PostgreSQL support (BL-015).

**Effort:** HIGH (migration of existing schema history), LOW (keep as-is)

**Priority:** P3 (only revisit if PostgreSQL becomes a requirement)

**Downsides of keeping current runner:**
- No rollback capability
- No auto-generation of migration scripts
- Manual SQL writing required

**References:**
- [Flask-Migrate](https://flask-migrate.readthedocs.io/)
- [Alembic documentation](https://alembic.sqlalchemy.org/)

---

## 8. CI/CD: GitHub Actions

**What it does:** Automated workflows that run on push/PR to test, lint, and
validate code in a clean environment.

**Why it helps QuizWeaver:**
- Currently zero automated checks -- all quality depends on local developer discipline
- Tests could silently break without anyone noticing
- GitHub Actions is free for public repos and generous for private repos
- Catches platform-specific issues (tests run on Linux by default; QuizWeaver
  developed on Windows)
- Can run coverage and publish reports

**Recommended workflows:**

### Workflow 1: Test + Lint (on every push/PR)
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.12", "3.14"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt
      - run: pip install ruff pytest-cov
      - run: ruff check .
      - run: pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v4  # optional
```

### Workflow 2: Security scan (weekly)
```yaml
name: Security
on:
  schedule:
    - cron: '0 9 * * 1'  # Monday 9am
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install bandit pip-audit
      - run: bandit -r src/ -ll
      - run: pip-audit
```

**Effort:** LOW-MEDIUM
- Create `.github/workflows/ci.yml`
- May need to fix tests that rely on Windows-specific paths
- SQLite temp file handling may differ on Linux

**Priority:** P1

**Downsides:**
- Some tests may fail on Linux (Windows path separators, file locking behavior)
- Need to verify all 1,381 tests pass in CI environment
- Free tier has limited minutes (2,000/month for private repos)
- Matrix testing across 3 Python versions triples CI time

**References:**
- [GitHub Actions Python testing](https://github.com/ericsalesdeandrade/pytest-github-actions-example)
- [pytest with GitHub Actions](https://pytest-with-eric.com/integrations/pytest-github-actions/)

---

## 9. Security Scanning: Bandit + pip-audit

### Bandit (static analysis)

**What it does:** Scans Python source code for common security issues using AST
analysis. Detects SQL injection, hardcoded passwords, use of `eval()`, insecure
hash functions, and more.

**Why it helps QuizWeaver:**
- Flask app with user input (login, settings, quiz generation) needs security review
- Custom SQL in migrations may have injection risks
- 47 built-in security checks
- New in 2026: B614/B615 checks for unsafe ML model loading (relevant since
  QuizWeaver integrates with LLM providers)

**Effort:** LOW
- Install: `pip install bandit`
- Run: `bandit -r src/ -ll` (medium and high severity only)
- Expected findings: likely some `subprocess` calls, broad `except` clauses,
  possible hardcoded temp paths

**Priority:** P2

### pip-audit (dependency vulnerabilities)

**What it does:** Checks installed packages against the Python Packaging Advisory
Database for known vulnerabilities.

**Why it helps QuizWeaver:**
- 13 dependencies (plus transitive deps) could have CVEs
- `anthropic`, `google-genai`, `reportlab`, `pillow` are frequently updated
  with security patches
- One-command check: `pip-audit`

**Effort:** LOW
- Install: `pip install pip-audit`
- Run: `pip-audit`
- Can integrate into CI (see workflow above)

**Priority:** P2

**Downsides:**
- Bandit may produce false positives (e.g., flagging `yaml.safe_load` which is
  already safe, or `os.path.join` as path traversal)
- pip-audit requires pinned versions to be most useful (circles back to lockfile need)

**References:**
- [Bandit documentation](https://bandit.readthedocs.io/)
- [Bandit GitHub](https://github.com/PyCQA/bandit)
- [pip-audit PyPI](https://pypi.org/project/pip-audit/)

---

## 10. Editor/IDE Tools

QuizWeaver development uses Claude Code as the primary tool, but VS Code is the
underlying editor. Recommended extensions:

### Must-have (P1)

| Extension | What it does |
|-----------|-------------|
| **Ruff (charliermarsh.ruff)** | Inline linting + format-on-save, matches CLI Ruff |
| **Python (ms-python.python)** | Debugging, IntelliSense, venv management |
| **SQLite Viewer** | View quiz_warehouse.db without external tools |
| **GitLens** | Inline blame, branch comparison, history |

### Nice-to-have (P2)

| Extension | What it does |
|-----------|-------------|
| **Better Jinja** | Syntax highlighting for templates/*.html |
| **YAML** | Validation for config.yaml, GitHub Actions |
| **Error Lens** | Inline error display (no need to hover) |
| **Thunder Client** | REST API testing for Flask routes |

### Recommended VS Code settings (.vscode/settings.json)

```json
{
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  },
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"],
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true
  }
}
```

**Effort:** LOW (install extensions, drop settings file)

**Priority:** P1 for Ruff extension, P2 for others

---

## 11. Claude Code Tools

### MCP Servers

Claude Code already has Playwright and GitHub MCP servers connected. Additional
useful servers:

| MCP Server | What it does | Priority |
|------------|-------------|----------|
| **SQLite MCP** | Query quiz_warehouse.db directly from Claude | P2 |
| **filesystem** (already active) | File operations | Already active |
| **GitHub** (already active) | PR/issue management | Already active |

**Note:** Avoid enabling too many MCP servers. Each server's tool definitions
consume context window. The current setup (filesystem, GitHub, Playwright, memory)
is already using significant context. Only add servers when there is a clear use
case.

### Hooks

Claude Code hooks run shell commands at specific points in the agent loop. Useful
hooks for QuizWeaver:

| Hook | Trigger | What it does |
|------|---------|-------------|
| **Lint on file edit** | PostToolUse (Write/Edit) | Run `ruff check --fix` on edited files |
| **Test on save** | PostToolUse (Write/Edit) | Run related test file after editing source |
| **Secret check** | PreToolUse (Write) | Scan file content for API key patterns |

Example hook config (`.claude/hooks.json`):
```json
{
  "hooks": [
    {
      "event": "PostToolUse",
      "tools": ["Write", "Edit"],
      "command": "ruff check --fix $FILE_PATH"
    }
  ]
}
```

**Effort:** LOW

**Priority:** P2 (after Ruff is installed)

### CLAUDE.md Improvements

The existing CLAUDE.md is comprehensive (650+ lines). Suggested additions:
- Add a "Quick Commands" section with common test/lint commands
- Document the pyproject.toml tool config locations
- Add a "Do NOT modify" list for generated files

**References:**
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
- [Claude Code hooks and plugins](https://github.com/anthropics/claude-code/blob/main/plugins/README.md)
- [Everything Claude Code configs](https://github.com/affaan-m/everything-claude-code)

---

## 12. Python Packaging: pyproject.toml

**What it does:** A single configuration file (PEP 621) that replaces setup.py,
setup.cfg, requirements.txt, and tool-specific config files (pytest.ini, .flake8,
etc.).

**Why it helps QuizWeaver:**
- Consolidates tool configs: Ruff, pytest, coverage, project metadata
- Modern Python standard (recommended by PyPA since 2023)
- Required by uv and poetry
- Makes the project installable via `pip install .` or `pip install -e .`
- Required if QuizWeaver ever publishes to PyPI or distributes as a package

**Current state:** QuizWeaver has no pyproject.toml. Configuration is spread across:
- `requirements.txt` (dependencies)
- `config.yaml` (runtime config -- keep separate)
- No pytest config file
- No linter config

**Recommended pyproject.toml:**
```toml
[project]
name = "quizweaver"
version = "0.12.0"
description = "A language-model-assisted teaching platform"
readme = "README.md"
requires-python = ">=3.9"
license = {text = "MIT"}
dependencies = [
    "flask",
    "sqlalchemy",
    "pyyaml",
    "python-dotenv",
    "reportlab",
    "python-docx",
    "pillow",
    "google-genai",
    "openai",
    "anthropic[vertex]",
    "gunicorn",
    "PyMuPDF",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-cov",
    "ruff",
    "bandit",
    "pip-audit",
    "pre-commit",
]

[tool.ruff]
target-version = "py39"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-x -q"

[tool.coverage.run]
source = ["src"]
branch = true

[tool.coverage.report]
show_missing = true
skip_covered = true
```

**Effort:** LOW-MEDIUM
- Create pyproject.toml with above content
- Keep requirements.txt as a generated/parallel file for pip users
- Update INSTALLATION.md to reference both methods

**Priority:** P1 (foundation for Ruff, pytest-cov, and uv adoption)

**Downsides:**
- Two sources of dependency truth if requirements.txt is kept alongside
- Teachers following INSTALLATION.md may be confused by pyproject.toml
- Does not replace config.yaml (runtime config stays separate)

**References:**
- [Python Packaging User Guide: pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [Migrating from requirements.txt](https://pydevtools.com/handbook/how-to/migrate-requirements.txt/)

---

## 13. Summary Matrix

| Tool | What | Effort | Priority | Adopt? |
|------|------|--------|----------|--------|
| **Ruff** | Linting + formatting | LOW | **P1** | Yes, immediately |
| **pyproject.toml** | Centralized config | LOW | **P1** | Yes, immediately |
| **pytest-cov** | Test coverage | LOW | **P1** | Yes, immediately |
| **GitHub Actions** | CI/CD | LOW-MED | **P1** | Yes, after Ruff |
| **pre-commit** | Hook framework | LOW-MED | **P2** | Yes, bundle with Ruff |
| **Bandit + pip-audit** | Security scanning | LOW | **P2** | Yes, add to CI |
| **uv** | Dependency mgmt | MEDIUM | **P2** | Yes, when ready |
| **VS Code settings** | Editor config | LOW | **P1-P2** | Yes, drop-in |
| **Claude Code hooks** | Dev workflow | LOW | **P2** | After Ruff |
| **Type checking** | mypy/pyright | HIGH | **P3** | Defer |
| **MkDocs** | Documentation site | MEDIUM | **P3** | Defer |
| **Alembic** | Migration framework | HIGH | **P3** | Keep current |

---

## 14. Recommended Adoption Order

### Phase A: Quick Wins (1-2 hours)

1. Create `pyproject.toml` with project metadata and tool configs
2. Install and run Ruff (`ruff check --fix . && ruff format .`)
3. Install pytest-cov, run coverage report, identify gaps
4. Add `.vscode/settings.json` with format-on-save

### Phase B: Automation (2-3 hours)

5. Create `.github/workflows/ci.yml` (test + lint on push)
6. Replace custom pre-commit hook with `pre-commit` framework
7. Add Bandit + pip-audit to CI workflow
8. Fix any tests that fail on Linux CI

### Phase C: Modernization (3-4 hours)

9. Migrate to uv (lockfile, faster installs)
10. Update `run.bat` / `run.sh` to use uv
11. Add Claude Code lint-on-edit hook
12. Update INSTALLATION.md and README.md

### Phase D: Future (defer)

13. Gradual type annotations on new code
14. MkDocs documentation site (if community grows)
15. Alembic migration (only if PostgreSQL needed)

---

*This document was researched and written on 2026-02-12 as part of a QuizWeaver
repository audit. All tool versions and recommendations should be re-evaluated
periodically as the Python ecosystem evolves rapidly.*
