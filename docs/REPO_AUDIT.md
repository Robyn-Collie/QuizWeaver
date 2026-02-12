# Repository Audit Report

**Date:** 2026-02-12
**Auditor:** repo-auditor agent (Claude Opus 4.6)
**Scope:** Full repository layout, tracked files, naming, dead code, redundancies

---

## Executive Summary

QuizWeaver has **260 tracked files** across **6.3 MB** of tracked content. The codebase is functional and well-tested (1381 tests), but 12 sessions of rapid development have left organizational debt:

1. **4.3 MB of binary files** (PDFs, DOCX) committed to git that should be in `.gitignore`
2. **44 orphan screenshot PNGs** on disk (correctly gitignored but cluttering the repo)
3. **Duplicate utility functions** copied across 3 export modules
4. **`src/output.py` superseded** by `src/export.py` but still tracked (CLI-only legacy)
5. **Stale planning directories** (`Project_Planning/`, `openspec/`, `agent_prompts/`) from early sessions
6. **`config.yaml` committed with temp file path** (contains absolute path to a temp DB)
7. **Root directory clutter** -- 22 non-code files at the repo root
8. **`src/web/routes.py` at 2,974 lines** -- the single largest source file, growing each session
9. **No `conftest.py`** -- 69 test files likely duplicate fixture setup
10. **Empty bogus directory** `CUsersandreprojectsQuizWeaverdocs/` (Windows path artifact)

**Priority:** Items 1, 6, and 10 should be fixed immediately. Items 2-5 and 7-8 are medium priority. Item 9 is a longer-term refactor.

---

## 1. Files to Remove (from git tracking)

### HIGH PRIORITY -- Binary Files in Git History

These binary files are tracked in git, bloating the repository. They were added in early commits and are sample teaching content, not source code.

| File | Size | Justification |
|------|------|---------------|
| `Content_Summary/Change Over Time Content Summary.pdf` | 899 KB | Sample content; should be gitignored or in a separate data repo |
| `Content_Summary/life_science mt.docx` | 960 KB | Sample content; same |
| `Retake/Change Over Time Test.pdf` | 2.4 MB | Sample quiz; same |

**Combined: 4.3 MB of binary files** -- over 68% of total tracked content.

**Action:** Add `Content_Summary/` and `Retake/` to `.gitignore`. Remove from tracking with `git rm --cached`. The files remain on disk for local use. Consider `git filter-repo` to purge from history if repo size matters.

### MEDIUM PRIORITY -- Stale Tracked Files

| File | Size | Justification |
|------|------|---------------|
| `SETUP_STATUS.md` | ~2 KB | One-time setup report from 2026-02-06; not maintained |
| `implementation_plan.md` | ~2 KB | Early generator-critic implementation plan; superseded by actual code |
| `qa_guidelines.txt` | ~1 KB | Original 7th-grade QA guidelines; hardcoded assumptions now replaced by configurable cognitive frameworks |
| `nul` | 0 bytes | Windows artifact (`> nul` redirect created a file); empty, untracked but on disk |

### LOW PRIORITY -- Consider Archiving

| Directory | Size | Justification |
|-----------|------|---------------|
| `Project_Planning/` (5 files, 442 lines) | 40 KB | Early planning from pre-Session 1; superseded by `docs/` and `openspec/` |
| `agent_prompts/` (4 txt + README, 1060 lines) | 56 KB | Multi-agent orchestration prompts from Session 7; one-time use, not referenced by code |
| `openspec/` (8 files) | 81 KB | OpenSpec change spec from Phase 1; all tasks completed; should be archived |
| `demo_script.md` (509 lines) | 20 KB | Workshop demo script; could move to `docs/` |
| `demo_video_script.md` (564 lines) | 17 KB | Video script; could move to `docs/` |
| `workshop_slides.md` (1359 lines) | 49 KB | Marp slide deck; could move to `docs/` |

---

## 2. Files to Move (current -> proposed location)

| Current Location | Proposed Location | Reason |
|-----------------|-------------------|--------|
| `demo_script.md` | `docs/DEMO_SCRIPT.md` | Consolidate docs at root |
| `demo_video_script.md` | `docs/DEMO_VIDEO_SCRIPT.md` | Same |
| `workshop_slides.md` | `docs/WORKSHOP_SLIDES.md` | Same |
| `reset_demo.sh` | `scripts/reset_demo.sh` | Group utility scripts |
| `run.bat` | `scripts/run.bat` | Same |
| `run.sh` | `scripts/run.sh` | Same |
| `gunicorn.conf.py` | `deploy/gunicorn.conf.py` | Group deployment config |
| `Dockerfile` | `deploy/Dockerfile` | Same |
| `docker-compose.yml` | `deploy/docker-compose.yml` | Same |
| `.dockerignore` | `deploy/.dockerignore` | Same (or keep at root if Docker requires it) |
| `INSTALLATION.md` | `docs/INSTALLATION.md` | Consolidate docs |

**Note:** `.dockerignore` must be at the repo root for Docker builds. If moving Docker files to `deploy/`, keep `.dockerignore` at root or adjust build context.

---

## 3. Directories to Restructure

### 3.1 Root Directory Cleanup

The repo root has **22 non-code, non-config files** (markdown docs, scripts, screenshots). This creates clutter. After moving files per Section 2, the root would contain only:

```
QuizWeaver/
  .claude/          # Claude tooling (keep)
  .env.example      # Template (keep)
  .gitignore        # Keep
  .pre-commit-config.yaml  # Keep
  CLAUDE.md         # Keep (project instructions)
  config.yaml       # Keep (app config)
  LICENSE           # Keep
  main.py           # Keep (CLI entry point)
  README.md         # Keep
  requirements.txt  # Keep
  data/             # Standards JSON (keep)
  demo_data/        # Demo setup (keep)
  docs/             # All documentation
  migrations/       # SQL migrations (keep)
  prompts/          # Agent prompts (keep -- referenced by code)
  scripts/          # Launcher and utility scripts
  src/              # Source code
  static/           # CSS/JS/fonts
  templates/        # Jinja2 HTML
  tests/            # Test suite
```

### 3.2 `src/web/routes.py` -- Needs Splitting

At **2,974 lines**, `routes.py` is the single largest source file. It contains every Flask route for the entire application. Consider splitting into route blueprints:

- `src/web/routes_quiz.py` -- Quiz CRUD, generation, export
- `src/web/routes_class.py` -- Class management
- `src/web/routes_study.py` -- Study materials
- `src/web/routes_analytics.py` -- Performance analytics
- `src/web/routes_settings.py` -- Settings, provider config
- `src/web/routes_lesson.py` -- Lessons and lesson plans
- `src/web/routes.py` -- Dashboard, auth, health, shared routes

This is a larger refactor but would significantly improve maintainability.

### 3.3 Test Organization

The `tests/` directory has **69 test files** in a flat structure with no `conftest.py`. Many test files are named by session/feature ticket rather than by module:

- `test_bl024_autofill.py`, `test_bl025_lesson_value.py`, etc. (ticket-based names)
- `test_session7_dashboard.py`, `test_session7_help.py`, etc. (session-based names)

**Recommendations:**
- Add a `tests/conftest.py` with shared fixtures (temp DB setup, Flask test client, mock provider)
- Consider subdirectories: `tests/web/`, `tests/export/`, `tests/generators/`
- Rename ticket-based files to descriptive names (e.g., `test_bl024_autofill.py` -> `test_form_autofill.py`)

---

## 4. .gitignore Additions Needed

Current `.gitignore` is mostly good. Add these:

```gitignore
# --- Sample Content (not source code) ---
Content_Summary/
Retake/

# --- Stale Planning (archived) ---
# Project_Planning/    # Uncomment after archiving
# agent_prompts/       # Uncomment after archiving
# openspec/            # Uncomment after archiving

# --- Windows Artifacts ---
nul

# --- API Cost Logs (runtime data) ---
api_costs.log

# --- Backup Directories ---
backups/

# --- Empty bogus directory ---
CUsersandreprojectsQuizWeaverdocs/
```

**Already correctly gitignored:** `*.png`, `*.log`, `quiz_warehouse.db`, `generated_images/`, `Quiz_Output/`, `.playwright-mcp/`, `test_server.py`, `test_e2e_config.yaml`, `Audits/`, `UAT_SYSTEM_OVERVIEW.md`

---

## 5. Dead Code / Unused Modules

### 5.1 `prompts/analyst_prompt.txt` -- Never Referenced

- `prompts/generator_prompt.txt` is loaded by `src/agents.py:GeneratorAgent`
- `prompts/critic_prompt.txt` is loaded by `src/agents.py:CriticAgent`
- `prompts/analyst_prompt.txt` is **never imported or referenced** by any Python code

The original 3-agent design (Analyst, Generator, Critic) was simplified to 2 agents. The analyst prompt is dead.

**Action:** Remove `prompts/analyst_prompt.txt` or mark it as deprecated.

### 5.2 `src/output.py` -- Superseded by `src/export.py`

- `src/output.py` (429 lines): Original CLI-era PDF/QTI export (reportlab-based)
- `src/export.py` (1,048 lines): Web-era export with CSV, DOCX, GIFT, PDF, QTI support

Both generate PDFs and QTI packages, but `export.py` is the comprehensive version used by the web app. `output.py` is only imported by:
- `main.py` (CLI commands `generate` and `ingest`)
- `src/review.py` (CLI interactive review)

**Action:** Migrate `main.py` CLI to use `src/export.py` functions, then remove `src/output.py` and `src/review.py`.

### 5.3 `src/ingestion.py` -- CLI-Only Module

- Only imported by `main.py` (CLI `ingest` command)
- Not used by the web app at all
- References old `Content_Summary/` directory and `fitz` (PyMuPDF) for PDF extraction
- The web app generates quizzes from topics/lessons, not from ingested PDFs

**Status:** Not dead code per se -- it serves the CLI pipeline. But if the CLI ingest workflow is deprecated in favor of the web app, this module and its dependencies (`PyMuPDF`, `python-docx` for ingestion) could be removed.

### 5.4 `src/image_gen.py` -- Vertex AI Image Generation

- Only imported by `main.py` (CLI pipeline)
- Not used by web app
- Depends on Vertex AI SDK and PIL

**Status:** Similar to `ingestion.py` -- serves the CLI pipeline only.

---

## 6. Duplicate Code / Redundancies

### 6.1 `_sanitize_filename()` -- Copied 3 Times

Identical function in three files with only the fallback string differing:

| File | Line | Fallback |
|------|------|----------|
| `src/export.py` | 182 | `"quiz"` |
| `src/lesson_plan_export.py` | 58 | `"lesson_plan"` |
| `src/study_export.py` | 33 | `"study"` |

**Action:** Extract to a shared utility (e.g., `src/utils.py`) with a `default` parameter:
```python
def sanitize_filename(title: str, default: str = "export") -> str:
    clean = re.sub(r"[^\w\s\-]", "", title)
    clean = re.sub(r"\s+", "_", clean.strip())
    return clean[:80] or default
```

### 6.2 `_pdf_wrap_text()` -- Copied 2 Times (Identical)

**Byte-for-byte identical** in:
- `src/lesson_plan_export.py:69-92`
- `src/study_export.py:276-299`

**Action:** Extract to shared utility.

### 6.3 `_build_prompt()` -- Similar Pattern

Defined in both `src/lesson_plan_generator.py:47` and `src/reteach_generator.py:120`. These build LLM prompts from templates with different content, so they are not identical -- but the pattern could be unified.

### 6.4 `src/output.py` vs `src/export.py`

Both contain PDF generation and QTI export logic. `export.py` is the newer, more comprehensive version. See Section 5.2.

---

## 7. Naming Inconsistencies

### 7.1 Directory Names -- Mixed Conventions

| Directory | Convention | Issue |
|-----------|-----------|-------|
| `Content_Summary` | PascalCase with underscore | Should be `content_summary` or move to gitignore |
| `Quiz_Output` | PascalCase with underscore | Already gitignored, but inconsistent |
| `Project_Planning` | PascalCase with underscore | Should be `project_planning` or removed |
| `Retake` | PascalCase | Should be `retake` or move to gitignore |
| `Audits` | PascalCase | Already gitignored |
| `data` | lowercase | Correct |
| `demo_data` | snake_case | Correct |
| `docs` | lowercase | Correct |
| `src` | lowercase | Correct |

**Preferred:** All-lowercase snake_case for directories (Python convention).

### 7.2 Test File Names -- Mixed Strategies

Three naming patterns coexist in `tests/`:

1. **Module-based:** `test_classroom.py`, `test_export.py` (mirrors `src/` modules)
2. **Ticket-based:** `test_bl024_autofill.py`, `test_bl025_lesson_value.py` (backlog ticket numbers)
3. **Session-based:** `test_session7_dashboard.py`, `test_session7_help.py`

Patterns 2 and 3 make it hard to find tests by feature. A developer looking for "autofill tests" would not guess `test_bl024_autofill.py`.

**Recommendation:** Rename to descriptive names:
- `test_bl024_autofill.py` -> `test_form_autofill.py`
- `test_bl025_lesson_value.py` -> `test_lesson_form_defaults.py`
- `test_session7_dashboard.py` -> `test_dashboard_redesign.py`
- etc.

### 7.3 Config File -- Committed with Temp Path

`config.yaml` is committed with:
```yaml
paths:
  database_file: C:\Users\andre\AppData\Local\Temp\tmptr33ibc1.db
```

This is a local temp path that will break on any other machine. It should either:
- Use a relative path (e.g., `quiz_warehouse.db`)
- Be gitignored and generated from a template
- Use environment variables with a default

---

## 8. Large Files / Context Window Impact

Files that consume significant context window when read by AI tools:

| File | Lines | Size | Impact |
|------|-------|------|--------|
| `src/web/routes.py` | 2,974 | 111 KB | **Very high** -- nearly fills a context window alone |
| `static/css/style.css` | ~2,200 | 79 KB | High |
| `docs/COMPETITIVE_ANALYSIS.md` | 1,035 | 57 KB | Medium (rarely needed for coding) |
| `workshop_slides.md` | 1,359 | 49 KB | Medium |
| `tests/test_web.py` | 1,203 | 46 KB | Medium |
| `src/export.py` | 1,048 | 35 KB | Medium |
| `src/llm_provider.py` | 898 | 34 KB | Medium |
| `src/mock_responses.py` | 676 | 33 KB | Medium |
| `src/agents.py` | 706 | 33 KB | Medium |

**Key concern:** `src/web/routes.py` at 2,974 lines is the #1 bottleneck. Splitting it into Flask blueprints (see Section 3.2) would be the highest-impact refactor for both developer and AI productivity.

---

## 9. Stale Directories Assessment

| Directory | Status | Last Modified | Recommendation |
|-----------|--------|---------------|----------------|
| `openspec/` | **Stale** | Session 1 (commit `bf85167`) | Archive or remove; Phase 1 is complete |
| `Project_Planning/` | **Stale** | Pre-Session 1 (commit `13a61af`) | Archive or remove; superseded by `docs/` |
| `agent_prompts/` | **Stale** | Session 7 (commit `5ea7fec`) | Archive; one-time multi-agent prompts |
| `prompts/` | **Active** | Session 7 | Keep; referenced by `src/agents.py` (2 of 3 files) |
| `Content_Summary/` | **Stale** | Session 1 (commit `44a2b16`) | Gitignore; sample content only |
| `Retake/` | **Stale** | Session 1 (commit `44a2b16`) | Gitignore; sample content only |
| `data/` | **Active** | Session 10 | Keep; standards JSON files used by `src/standards.py` |
| `demo_data/` | **Active** | Session 7 | Keep; demo setup scripts |
| `migrations/` | **Active** | Session 10 | Keep; SQL migration files |
| `CUsersandreprojectsQuizWeaverdocs/` | **Bogus** | N/A | Delete; empty directory from Windows path artifact |

---

## 10. Recommendations (Prioritized)

### P0 -- Fix Immediately (< 15 minutes)

1. **Delete `CUsersandreprojectsQuizWeaverdocs/`** -- Empty bogus directory (Windows path artifact)
2. **Delete `nul`** -- Empty Windows artifact file
3. **Fix `config.yaml`** -- Replace absolute temp path with relative `quiz_warehouse.db`
4. **Add to `.gitignore`:** `Content_Summary/`, `Retake/`, `api_costs.log`, `backups/`
5. **Remove from git tracking:** `git rm --cached -r Content_Summary/ Retake/`

### P1 -- Do This Session (30-60 minutes)

6. **Remove stale tracked files:** `SETUP_STATUS.md`, `implementation_plan.md`, `qa_guidelines.txt`
7. **Remove `prompts/analyst_prompt.txt`** -- dead code, never referenced
8. **Move root-level docs** to `docs/` (demo_script.md, demo_video_script.md, workshop_slides.md)
9. **Extract shared utilities:** `_sanitize_filename()` and `_pdf_wrap_text()` to `src/export_utils.py`
10. **Clean up 44 orphan PNG screenshots** from repo root (already gitignored, just delete from disk)

### P2 -- Do Next Session (1-2 hours)

11. **Archive `openspec/`** -- Phase 1 complete; move to `archive/openspec/` or remove
12. **Archive `Project_Planning/`** -- Superseded by `docs/`
13. **Archive `agent_prompts/`** -- One-time use from Session 7
14. **Create `tests/conftest.py`** with shared fixtures (temp DB, Flask client, mock provider)
15. **Rename ticket-based test files** to descriptive names
16. **Group scripts:** Create `scripts/` for `run.sh`, `run.bat`, `reset_demo.sh`

### P3 -- Longer Term (multi-session)

17. **Split `src/web/routes.py`** into Flask blueprints (highest-impact refactor)
18. **Consolidate `src/output.py` into `src/export.py`** and update CLI
19. **Evaluate `src/ingestion.py` and `src/image_gen.py`** -- CLI-only; deprecate if web-only future
20. **Consider `git filter-repo`** to purge binary files from git history (saves ~4 MB)
21. **Split `static/css/style.css`** into component stylesheets if it keeps growing

---

## Appendix: Full File Inventory

### Tracked Files by Category (260 total)

| Category | Count | Size |
|----------|-------|------|
| Python source (`src/`) | 32 | 511 KB |
| Tests (`tests/`) | 69 | 785 KB |
| Templates (`templates/`) | 31 | 232 KB |
| Static assets (`static/`) | 14 | 121 KB |
| Migrations (`migrations/`) | 11 | 15 KB |
| Documentation (`docs/`) | 9 | 111 KB |
| Data files (`data/`) | 5 | 89 KB |
| Binary content (`Content_Summary/`, `Retake/`) | 3 | 4,317 KB |
| OpenSpec (`openspec/`) | 8 | 81 KB |
| Claude tooling (`.claude/`) | 21 | 48 KB |
| Project planning (`Project_Planning/`) | 5 | 40 KB |
| Agent prompts (`agent_prompts/`) | 5 | 56 KB |
| Root config/docs/scripts | ~47 | ~237 KB |

### Git Object Store

- Total objects: 950 (unpacked) + 150 (packed)
- Unpacked size: 1.85 MB
- Pack size: 3.30 MB
- Total `.git/` size: 7.8 MB
- Largest blobs: `Retake/Change Over Time Test.pdf` (2.4 MB), `Content_Summary/life_science mt.docx` (960 KB)
