# CLI Audit Report

**Date:** 2026-02-12
**Auditor:** cli-auditor agent
**Scope:** All CLI commands in `main.py` vs. all web routes in `src/web/routes.py`

---

## Executive Summary

QuizWeaver's CLI (`main.py`) provides **8 commands** covering class management, lesson tracking, quiz generation, and cost reporting. The web UI (`src/web/routes.py`) exposes **75+ routes** covering 25+ distinct feature areas. This means roughly **70% of features are web-only** with no CLI equivalent.

The CLI is sufficient for the original core workflow (ingest content, generate quiz, manage classes, log lessons), but the platform has grown far beyond that. Major feature categories -- study materials, rubrics, variants, performance analytics, lesson plans, templates, question bank, and all export formats -- have no CLI access at all.

**Could a teacher use QuizWeaver entirely from terminal?** Not today. They could create classes, log lessons, and generate quizzes, but could not export quizzes (CSV/DOCX/PDF/GIFT), generate study materials, create rubrics, import performance data, view analytics, generate lesson plans, or manage templates.

**Test coverage is strong.** All core modules have standalone pytest tests that run without Flask. The e2e test (`test_e2e_multi_class.py`) covers class creation, lesson logging, and knowledge isolation, but does not cover quiz generation, export, or the newer feature modules end-to-end.

---

## Feature Coverage Matrix

| # | Feature | Web UI | CLI | Standalone Tests | Notes |
|---|---------|--------|-----|------------------|-------|
| **Core Workflow** |||||
| 1 | Content ingestion | -- | `ingest` | test_database_schema | CLI only; no web route |
| 2 | Quiz generation (from content) | `/classes/<id>/generate` | `generate` | test_quiz_generator | Both |
| 3 | Quiz generation (from topics) | `/generate/topics` | -- | test_topic_generator | Web only |
| 4 | Interactive quiz review | -- | `generate --no-interactive` | -- | CLI only (terminal) |
| **Class Management** |||||
| 5 | Create class | `/classes/new` | `new-class` | test_classroom | Both |
| 6 | List classes | `/classes` | `list-classes` | test_classroom | Both |
| 7 | Set active class | -- | `set-class` | -- | CLI only |
| 8 | View class detail | `/classes/<id>` | -- | -- | Web only |
| 9 | Edit class | `/classes/<id>/edit` | -- | test_classroom | Web only |
| 10 | Delete class | `/classes/<id>/delete` | -- | test_classroom | Web only |
| **Lesson Tracking** |||||
| 11 | Log lesson | `/classes/<id>/lessons/new` | `log-lesson` | test_lesson_tracker | Both |
| 12 | List lessons | `/classes/<id>/lessons` | `list-lessons` | test_lesson_tracker | Both |
| 13 | Delete lesson | `/classes/<id>/lessons/<id>/delete` | -- | test_lesson_tracker | Web only |
| **Quiz Management** |||||
| 14 | List all quizzes | `/quizzes` | -- | -- | Web only |
| 15 | View quiz detail | `/quizzes/<id>` | -- | -- | Web only |
| 16 | Edit quiz title | `PUT /api/quizzes/<id>/title` | -- | test_quiz_editing | Web only |
| 17 | Edit question | `PUT /api/questions/<id>` | -- | test_quiz_editing | Web only |
| 18 | Delete question | `DELETE /api/questions/<id>` | -- | test_quiz_editing | Web only |
| 19 | Reorder questions | `PUT /api/quizzes/<id>/reorder` | -- | test_quiz_editing | Web only |
| 20 | Regenerate question | `POST /api/questions/<id>/regenerate` | -- | -- | Web only |
| 21 | Upload question image | `POST /api/questions/<id>/image` | -- | -- | Web only |
| **Quiz Export** |||||
| 22 | Export CSV | `/quizzes/<id>/export/csv` | -- | test_export | Web only |
| 23 | Export DOCX | `/quizzes/<id>/export/docx` | -- | test_export | Web only |
| 24 | Export GIFT | `/quizzes/<id>/export/gift` | -- | test_export | Web only |
| 25 | Export PDF | `/quizzes/<id>/export/pdf` | -- | test_export | Web only |
| 26 | Export QTI | `/quizzes/<id>/export/qti` | -- | test_export | Web only |
| **Study Materials** |||||
| 27 | List study sets | `/study` | -- | test_study_generator | Web only |
| 28 | Generate study material | `/study/generate` | -- | test_study_generator | Web only |
| 29 | View study set | `/study/<id>` | -- | -- | Web only |
| 30 | Export study (TSV/CSV/PDF/DOCX) | `/study/<id>/export/<fmt>` | -- | test_study_export | Web only |
| 31 | Edit study card | `PUT /api/study-cards/<id>` | -- | test_study_editing | Web only |
| 32 | Delete study set/card | `DELETE /api/study-sets/<id>` | -- | -- | Web only |
| **Variants** |||||
| 33 | Generate reading-level variant | `/quizzes/<id>/generate-variant` | -- | test_variant_generator | Web only |
| 34 | List quiz variants | `/quizzes/<id>/variants` | -- | test_web_variants | Web only |
| **Rubrics** |||||
| 35 | Generate rubric | `/quizzes/<id>/generate-rubric` | -- | test_rubric_generator | Web only |
| 36 | View rubric | `/rubrics/<id>` | -- | -- | Web only |
| 37 | Export rubric (CSV/DOCX/PDF) | `/rubrics/<id>/export/<fmt>` | -- | test_rubric_export | Web only |
| 38 | Delete rubric | `DELETE /api/rubrics/<id>` | -- | -- | Web only |
| **Performance Analytics** |||||
| 39 | Analytics dashboard | `/classes/<id>/analytics` | -- | test_performance_analytics | Web only |
| 40 | Import CSV performance data | `/classes/<id>/analytics/import` | -- | test_performance_import | Web only |
| 41 | Manual score entry | `/classes/<id>/analytics/manual` | -- | test_web_analytics | Web only |
| 42 | Quiz score entry | `/classes/<id>/analytics/quiz-scores` | -- | test_web_analytics | Web only |
| 43 | Reteach suggestions | `/classes/<id>/analytics/reteach` | -- | test_reteach_generator | Web only |
| 44 | Gap analysis API | `/api/classes/<id>/analytics` | -- | test_performance_analytics | Web only |
| 45 | Trend data API | `/api/classes/<id>/analytics/trends` | -- | test_performance_analytics | Web only |
| **Question Bank** |||||
| 46 | View question bank | `/question-bank` | -- | test_question_bank | Web only |
| 47 | Add/remove from bank | `POST /api/question-bank/add` | -- | test_question_bank | Web only |
| **Standards** |||||
| 48 | Browse standards | `/standards` | -- | test_standards | Web only |
| 49 | Search standards API | `/api/standards/search` | -- | test_standards_picker | Web only |
| 50 | Change standard set | `POST /settings/standards` | -- | test_standards_expansion | Web only |
| **Lesson Plans** |||||
| 51 | List lesson plans | `/lesson-plans` | -- | test_web_lesson_plans | Web only |
| 52 | Generate lesson plan | `/lesson-plans/generate` | -- | test_lesson_plan_generator | Web only |
| 53 | View lesson plan | `/lesson-plans/<id>` | -- | -- | Web only |
| 54 | Edit lesson plan section | `POST /lesson-plans/<id>/edit` | -- | -- | Web only |
| 55 | Export lesson plan (PDF/DOCX) | `/lesson-plans/<id>/export/<fmt>` | -- | test_lesson_plan_export | Web only |
| 56 | Delete lesson plan | `POST /lesson-plans/<id>/delete` | -- | -- | Web only |
| **Templates** |||||
| 57 | List quiz templates | `/quiz-templates` | -- | -- | Web only |
| 58 | Export quiz as template | `/quizzes/<id>/export-template` | -- | test_template_manager | Web only |
| 59 | Import quiz template | `/quiz-templates/import` | -- | test_template_manager | Web only |
| 60 | Validate template | `POST /api/quiz-templates/validate` | -- | test_template_manager | Web only |
| **Cost & Settings** |||||
| 61 | Cost dashboard | `/costs` | `cost-summary` | test_cost_tracking | Both (limited CLI) |
| 62 | Set monthly budget | `POST /costs` | -- | test_cost_improvements | Web only |
| 63 | Provider settings | `/settings` | -- | test_web_settings | Web only |
| 64 | Test provider connection | `POST /api/settings/test-provider` | -- | test_session7_provider | Web only |
| 65 | Provider setup wizard | `/settings/wizard` | -- | test_provider_wizard | Web only |
| **Auth & System** |||||
| 66 | Login / Logout | `/login`, `/logout` | -- | test_auth | Web only (N/A for CLI) |
| 67 | First-time setup | `/setup` | -- | test_auth | Web only |
| 68 | Change password | `/settings/password` | -- | test_auth | Web only |
| 69 | Dashboard | `/dashboard` | -- | test_session7_dashboard | Web only |
| 70 | Onboarding wizard | `/onboarding` | -- | test_onboarding | Web only |
| 71 | Health check | `/health` | -- | -- | Web only (monitoring) |
| 72 | Help page | `/help` | -- | test_session7_help | Web only |
| 73 | API audit log | `/api/audit-log` | -- | -- | Web only |

---

## Current CLI Commands (8 total)

| Command | Module(s) Called | Working | Notes |
|---------|-----------------|---------|-------|
| `ingest` | `src/ingestion.py` | Yes | Reads from Content_Summary directory |
| `generate` | `src/agents.py`, `src/output.py` | Yes | Full pipeline, interactive review optional |
| `new-class` | `src/classroom.py` | Yes | --name required, prompts to set active |
| `list-classes` | `src/classroom.py` | Yes | Shows table with active marker |
| `set-class` | `src/classroom.py` | Yes | Updates config.yaml |
| `log-lesson` | `src/lesson_tracker.py` | Yes | --text or --file, with --topics override |
| `list-lessons` | `src/lesson_tracker.py` | Yes | Filters: --last, --from, --to, --topic |
| `cost-summary` | `src/cost_tracking.py` | Yes | Prints formatted report |

All 8 commands respond correctly to `--help` and have proper argument definitions.

---

## Missing CLI Commands (Prioritized Proposals)

### P1 -- Essential (core teacher workflow without browser)

#### 1. `export-quiz`
```
python main.py export-quiz <quiz_id> --format {csv,docx,gift,pdf,qti} [--output FILE]
```
- **Module:** `src/export.py` (export_csv, export_docx, export_gift, export_pdf, export_qti)
- **Rationale:** Teachers cannot get their quizzes out of the system without the web UI. This is the single biggest gap.

#### 2. `list-quizzes`
```
python main.py list-quizzes [--class CLASS_ID] [--status STATUS] [--search TEXT]
```
- **Module:** `src/database.py` (Quiz model queries)
- **Rationale:** Without this, teachers cannot find quiz IDs needed for export, variant, or rubric commands.

#### 3. `view-quiz`
```
python main.py view-quiz <quiz_id> [--show-answers]
```
- **Module:** `src/database.py` (Quiz + Question queries)
- **Rationale:** View quiz content without opening a browser. Essential companion to list-quizzes.

#### 4. `generate-study`
```
python main.py generate-study --class CLASS_ID --type {flashcard,study_guide,vocabulary,review_sheet} [--quiz QUIZ_ID] [--topic TOPIC] [--title TITLE]
```
- **Module:** `src/study_generator.py` (generate_study_material)
- **Rationale:** Study materials are a key teacher workflow that should be accessible offline.

#### 5. `export-study`
```
python main.py export-study <study_set_id> --format {tsv,csv,pdf,docx} [--output FILE]
```
- **Module:** `src/study_export.py`
- **Rationale:** Companion to generate-study for getting materials out.

### P2 -- Nice to Have (advanced features)

#### 6. `generate-variant`
```
python main.py generate-variant <quiz_id> --level {ell,below_grade,on_grade,advanced} [--title TITLE]
```
- **Module:** `src/variant_generator.py` (generate_variant)
- **Rationale:** Reading-level variants are important for differentiated instruction.

#### 7. `generate-rubric`
```
python main.py generate-rubric <quiz_id> [--title TITLE]
```
- **Module:** `src/rubric_generator.py` (generate_rubric)
- **Rationale:** Rubrics complement quiz generation.

#### 8. `export-rubric`
```
python main.py export-rubric <rubric_id> --format {csv,docx,pdf} [--output FILE]
```
- **Module:** `src/rubric_export.py`
- **Rationale:** Teachers need to print/share rubrics.

#### 9. `import-performance`
```
python main.py import-performance --class CLASS_ID --file data.csv [--quiz QUIZ_ID]
```
- **Module:** `src/performance_import.py` (parse_performance_csv, import_csv_data)
- **Rationale:** CSV import is a natural CLI task.

#### 10. `analytics`
```
python main.py analytics --class CLASS_ID [--format {text,json}]
```
- **Module:** `src/performance_analytics.py` (compute_gap_analysis, get_class_summary)
- **Rationale:** View gap analysis and mastery data in terminal.

#### 11. `generate-lesson-plan`
```
python main.py generate-lesson-plan --class CLASS_ID --topics "topic1,topic2" [--standards "STD1,STD2"] [--duration 50]
```
- **Module:** `src/lesson_plan_generator.py` (generate_lesson_plan)
- **Rationale:** Lesson planning is a core teaching workflow.

#### 12. `export-lesson-plan`
```
python main.py export-lesson-plan <plan_id> --format {pdf,docx} [--output FILE]
```
- **Module:** `src/lesson_plan_export.py`
- **Rationale:** Companion to lesson plan generation.

#### 13. `generate-topics`
```
python main.py generate-topics --class CLASS_ID --topics "topic1,topic2" --type {quiz,flashcard,study_guide,vocabulary,review_sheet} [--count 20]
```
- **Module:** `src/topic_generator.py` (generate_from_topics)
- **Rationale:** Topic-based generation is a frequently used alternate path.

#### 14. `edit-class`
```
python main.py edit-class <class_id> [--name NAME] [--grade GRADE] [--subject SUBJECT] [--standards STANDARDS]
```
- **Module:** `src/classroom.py` (update_class)
- **Rationale:** Completes CRUD for classes in CLI.

#### 15. `delete-class`
```
python main.py delete-class <class_id> [--confirm]
```
- **Module:** `src/classroom.py` (delete_class)
- **Rationale:** Completes CRUD for classes in CLI.

### P3 -- Low Priority (advanced/niche features)

#### 16. `export-template` / `import-template`
```
python main.py export-template <quiz_id> [--output FILE]
python main.py import-template --file template.json --class CLASS_ID [--title TITLE]
```
- **Module:** `src/template_manager.py`
- **Rationale:** Template sharing is niche; JSON files are already portable.

#### 17. `reteach`
```
python main.py reteach --class CLASS_ID [--topics "topic1,topic2"] [--max 5]
```
- **Module:** `src/reteach_generator.py`
- **Rationale:** Reteach suggestions are useful but less frequently needed from CLI.

#### 18. `browse-standards`
```
python main.py browse-standards [--set {sol,ccss_ela,ccss_math,ngss,teks}] [--search TEXT] [--subject SUBJECT]
```
- **Module:** `src/standards.py`
- **Rationale:** Browsing standards is more natural in a UI.

#### 19. `delete-lesson`
```
python main.py delete-lesson <lesson_id> [--confirm]
```
- **Module:** `src/lesson_tracker.py` (delete_lesson)
- **Rationale:** Minor gap; lesson deletion is rare.

---

## Test Coverage Assessment

### Modules Testable Without Flask (via pytest)

| Module | Test File | Standalone? | Count |
|--------|-----------|-------------|-------|
| classroom.py | test_classroom.py | Yes | ~20 |
| lesson_tracker.py | test_lesson_tracker.py | Yes | ~25 |
| quiz_generator.py | test_quiz_generator.py | Yes | ~15 |
| agents.py | test_agents.py | Yes | ~12 |
| cost_tracking.py | test_cost_tracking.py | Yes | ~30 |
| export.py | test_export.py | Mostly (some web tests) | ~40 |
| study_generator.py | test_study_generator.py | Yes | ~20 |
| study_export.py | test_study_export.py | Yes | ~15 |
| variant_generator.py | test_variant_generator.py | Yes | ~15 |
| rubric_generator.py | test_rubric_generator.py | Yes | ~15 |
| rubric_export.py | test_rubric_export.py | Yes | ~10 |
| performance_import.py | test_performance_import.py | Yes | ~15 |
| performance_analytics.py | test_performance_analytics.py | Yes | ~20 |
| reteach_generator.py | test_reteach_generator.py | Yes | ~10 |
| standards.py | test_standards.py | Yes | ~25 |
| deterministic_layers.py | test_deterministic_layers.py | Yes | ~42 |
| lesson_plan_generator.py | test_lesson_plan_generator.py | Yes | ~54 |
| lesson_plan_export.py | test_lesson_plan_export.py | Yes | ~10 |
| template_manager.py | test_template_manager.py | Yes | ~26 |
| topic_generator.py | test_topic_generator.py | Yes | ~15 |
| llm_provider.py | test_anthropic_provider.py, test_mock_provider.py | Yes | ~28+ |
| database.py | test_database_schema.py | Yes | ~20 |
| cognitive_frameworks.py | test_cognitive_frameworks.py | Yes | ~10 |
| auth.py | test_auth.py | Mixed (uses Flask client) | ~15 |

**Verdict:** All core business logic modules have standalone tests. Tests run successfully with `python -m pytest` without starting the Flask server. The web-specific tests use `create_app()` with test config and Flask's test client but still run via pytest.

### Missing Test Coverage

1. **No CLI integration tests** -- There are no tests that invoke `main.py` subcommands (e.g., via subprocess or by calling `main()` directly). The CLI handlers in `main.py` are untested.
2. **No full pipeline e2e test** -- `test_e2e_multi_class.py` covers create class -> log lesson -> verify knowledge, but does NOT cover: generate quiz -> export -> verify output.
3. **Question regeneration** -- `src/question_regenerator.py` has no dedicated test file (tested indirectly via web tests).

---

## Recommended Improvements (Prioritized)

### Immediate (P1)

1. **Add `export-quiz` and `list-quizzes` CLI commands.** These two commands alone would make the CLI usable for the most common teacher workflow: generate a quiz and get it as a PDF/DOCX. Every export function already exists in `src/export.py` and just needs CLI wiring.

2. **Add CLI integration tests.** Create `tests/test_cli.py` that imports `main.py` functions (`handle_new_class`, `handle_generate`, etc.) and tests them with mock args and temp databases. This would catch argument parsing bugs and handler logic without subprocess overhead.

### Short-term (P2)

3. **Add `generate-study` and `export-study` commands.** Study materials are the second most-used feature after quizzes.

4. **Add `generate-variant`, `generate-rubric`, and their export companions.** These complete the assessment workflow from the command line.

5. **Add `import-performance` and `analytics` commands.** Performance CSV import is inherently a CLI-friendly task (piping data files).

6. **Add a full pipeline e2e test** covering: create class -> log lesson -> generate quiz (mock) -> export quiz -> verify output file.

### Long-term (P3)

7. **Add lesson plan CLI commands.** Lesson plan generation and export.

8. **Add template import/export CLI commands.** Low-usage but ensures feature parity.

9. **Add `delete-class`, `edit-class`, `delete-lesson` for CRUD completeness.**

10. **Consider a `serve` command** (`python main.py serve [--port 5000]`) as an explicit way to start the web UI, consolidating `run.bat`/`run.sh` functionality into the main CLI.

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| CLI commands available | 8 |
| Web routes | 75+ |
| Distinct feature areas | ~25 |
| Features with CLI access | 8 (~32%) |
| Features web-only | 17+ (~68%) |
| Core modules with standalone tests | 22/22 (100%) |
| CLI handler tests | 0 |
| Full pipeline e2e tests | 0 (partial: class+lesson only) |
| Proposed P1 CLI additions | 5 |
| Proposed P2 CLI additions | 10 |
| Proposed P3 CLI additions | 4 |
