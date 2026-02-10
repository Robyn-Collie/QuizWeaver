# QuizWeaver Backlog

> Feature requests, bugs, and refinements tracked for future planning sessions.
> Updated: 2026-02-10

## How This Works
- Items are categorized by area and prioritized (P1 = high, P2 = medium, P3 = nice-to-have)
- Each item has a unique ID (e.g., `BL-001`) for reference in commits and discussions
- Status: `[ ]` open, `[~]` in progress, `[x]` done
- When implementing, reference the backlog ID in your commit message

---

## LLM Provider Configuration

### BL-001: LLM Provider Setup UI [P1]
- [ ] Settings page where teachers can configure LLM providers (Gemini, Vertex AI, OpenAI-compatible)
- [ ] API key entry with masked display
- [ ] Connection test button ("Test Connection") that makes a minimal API call and reports success/failure
- [ ] Provider selection dropdown with status indicators (configured, not configured, error)
- [ ] Support for multiple configured providers with a "default" selection
- [ ] Clear error messages when configuration is wrong (invalid key, wrong endpoint, quota exceeded)
- [ ] Should be truly LLM-agnostic — any supported provider works seamlessly

### BL-002: Per-Task Provider Selection [P2]
- [ ] When generating quizzes, study materials, variants, etc., allow teacher to pick which LLM provider to use
- [ ] Dropdown on generation forms showing only configured/tested providers
- [ ] Remember last-used provider per task type

---

## Standards & Curriculum

### BL-003: Deterministic Standards Database [P1]
- [ ] Pre-loaded SOL (Standards of Learning) standards with full text and codes
- [ ] Track the version/date of loaded standards (e.g., "Virginia SOL 2024")
- [ ] Teachers can view, search, and browse standards by subject/grade
- [ ] Allow teacher edits or custom standards additions
- [ ] Support for updating standards when new versions are released
- [ ] Standards data stored in the database, not hardcoded

### BL-004: Better Standards Input UX [P1]
- [ ] Replace comma-separated text input for standards with a friendlier method
- [ ] Ideas: searchable checklist, tag-style bubbles, autocomplete from standards DB
- [ ] Teacher types a few characters → matching standards appear as clickable suggestions
- [ ] Selected standards shown as removable chips/tags
- [ ] Group standards by subject area or strand for browsing
- [ ] Works on quiz generation form, analytics filters, etc.

---

## Help & Onboarding

### BL-005: Help Page — Clarify Mock Provider [P2]
- [ ] Current help page makes mock provider sound like it generates real quizzes for free
- [ ] Clarify that mock mode produces test/placeholder data only — not real AI-generated content
- [ ] Explain when and why to use mock mode (development, demos, testing the UI)
- [ ] Guide teachers to configure a real provider for actual quiz generation

---

## Cost Tracking

### BL-006: Cost Tracking Improvements [P2]
- [ ] Current cost page shows a single cumulative number — needs more granularity
- [ ] Time-period breakdown (daily, weekly, monthly cost charts)
- [ ] Per-action cost breakdown (quiz generation, study materials, variants, reteach, etc.)
- [ ] Ability to reset/clear cost history or set a "billing period" start date
- [ ] Cost alerts/warnings when approaching a teacher-set budget threshold
- [ ] Make clear that costs reflect real API calls across the entire app, not just quiz generation

---

## Study Materials

### BL-007: Study Material Inline Editing [P1]
- [ ] Each flashcard, vocabulary item, study guide section, or review sheet item should be individually editable in the UI
- [ ] Regenerate individual items with teacher notes (like question regeneration)
- [ ] Delete/reorder items within a study set

### BL-008: Images in Study Materials [P2]
- [ ] Add images to flashcards (upload, search, or AI-generate)
- [ ] Add images to study guide sections
- [ ] Image support in study material exports (PDF, DOCX)

### BL-009: Source Quiz Dropdown — Show More Context [P2]
- [ ] Show quiz ID number in the dropdown (e.g., "Algebra Quiz #12") to disambiguate same-named quizzes
- [ ] Show additional metadata: topics, class name, date created
- [ ] Consider grouping by class in the dropdown

---

## Topic-Based Generation

### BL-010: Topic Selection UI [P1]
- [ ] Teachers can select topics for generation without needing a source quiz
- [ ] Typeahead/autocomplete: teacher starts typing → matching topics from lesson history appear
- [ ] Clickable topic bubbles/chips from a database of previously taught topics
- [ ] Topics sourced from lesson logs (what's been taught) and standards
- [ ] Generate quizzes, flashcards, or study materials from selected topics directly
- [ ] Useful when teacher wants to create assessments on taught concepts before a formal quiz exists

---

## Dashboard Redesign

### BL-017: Redesign Dashboard as Tool-Oriented Landing Page [P1]
- [ ] Current dashboard is not useful — stat cards (quizzes generated, LLM provider, etc.) are largely meaningless to teachers
- [ ] "Live LLM Provider: mock" is confusing/useless since teachers will have granular provider control (BL-001/BL-002)
- [ ] Classes are buried at the bottom requiring scroll — should be immediately accessible
- [ ] **New design goals:**
  - Orient teachers to the tools available (quiz generation, study materials, variants, rubrics, analytics)
  - Quick-access cards or tiles for each major workflow
  - Brief overview of what QuizWeaver does (especially for first-time users)
  - Prominent class list / class switcher near the top for fast navigation
  - Each tool card could show relevant context (e.g., "3 quizzes" for a class, recent activity)
- [ ] Per-class analytics overview could appear as a widget within class cards, not as the main page focus
- [ ] Follow dashboard UX best practices: action-oriented, not stat-heavy; guide users to their next task
- [ ] Consider: recent activity feed, "getting started" checklist for new users, contextual shortcuts

---

## UI/UX Refinements

### BL-011: Loading Spinners / Progress Bars [P2]
- [ ] Show progress indicators during LLM generation (quiz, study materials, variants, rubrics)
- [ ] Especially important for real API calls which can take 10-30 seconds

### BL-012: Question Bank [P3]
- [ ] Save/favorite individual questions for reuse across quizzes
- [ ] Search and filter saved questions by topic, type, cognitive level

### BL-013: Keyboard Shortcuts [P3]
- [ ] Common actions accessible via keyboard (navigate quizzes, toggle dark mode, etc.)

### BL-014: Teacher Onboarding Wizard [P3]
- [ ] First-time setup flow beyond just account creation
- [ ] Guide through: create first class → add lessons → generate first quiz
- [ ] Contextual help tooltips

---

## Infrastructure

### BL-015: PostgreSQL Migration Option [P3]
- [ ] Support PostgreSQL as an alternative to SQLite for multi-user deployments
- [ ] Migration script from SQLite to PostgreSQL

---

## Research

### BL-016: Competitor Analysis Deep Dive [P2]
- [ ] Research MagicSchool.ai, Quizizz, Kahoot, Gimkit, Formative, Socrative
- [ ] Identify features we're missing or could do better
- [ ] Focus on UX patterns, generation workflows, and export options
- [ ] Document findings for future session planning

---

## Completed (Archive)

### Session 1: Bloom's/DOK + Question Distribution [DONE]
### Session 2: Export Formats + Quiz Editing [DONE]
### Session 3: Flashcards + Study Materials [DONE]
### Session 4: Scaffolded Variants + Rubric Generation [DONE]
### Session 5: Performance Analytics + Gap Analysis [DONE]
### Session 6: Auth, Dark Mode, Search, Docker [DONE]
