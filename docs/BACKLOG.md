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

### BL-001: LLM Provider Setup UI [P1] `[~] partially done`
- [x] Settings page where teachers can configure LLM providers (Gemini, Vertex AI, OpenAI-compatible)
- [x] API key entry with masked display
- [x] Connection test button ("Test Connection") that makes a minimal API call and reports success/failure
- [x] Provider selection dropdown with status indicators (configured, not configured, error)
- [ ] Support for multiple configured providers with a "default" selection
- [ ] Clear error messages when configuration is wrong (invalid key, wrong endpoint, quota exceeded)
- [x] Should be truly LLM-agnostic — any supported provider works seamlessly

### BL-002: Per-Task Provider Selection [P2]
- [ ] When generating quizzes, study materials, variants, etc., allow teacher to pick which LLM provider to use
- [ ] Dropdown on generation forms showing only configured/tested providers
- [ ] Remember last-used provider per task type

### BL-018: Provider Setup Wizard [P1]
- [ ] Guided step-by-step flow for configuring a real LLM provider
- [ ] Steps: pick provider → get API key (with links to AI Studio / OpenAI / Ollama docs) → paste key → test → done
- [ ] Inline help explaining what each provider is, cost implications, and privacy considerations
- [ ] Contextual AI literacy: explain what an API key is, why local models (Ollama) are more private, what "tokens" mean
- [ ] Accessible from "Setup needed" badges on providers and from the getting-started banner
- [ ] References: [UNESCO AI Competency Framework (2024)](https://www.unesco.org/en/articles/ai-competency-framework-teachers), [Digital Promise AI Literacy Framework (2024)](https://digitalpromise.org/2024/06/18/ai-literacy-a-framework-to-understand-evaluate-and-use-emerging-technology/)

---

## AI Literacy & Responsible AI

### BL-019: AI Literacy Tooltips & Contextual Education [P1]
- [ ] Add `?` help tooltips throughout the UI that teach AI concepts in context
- [ ] Key concepts to surface where relevant:
  - **Human-in-the-loop**: On quiz review page — "AI generated this draft. Review and edit before sharing with students."
  - **Verification**: On generated content — "Always check AI output for accuracy. AI can make mistakes."
  - **Glass box / transparency**: On generation forms — explain what data feeds the AI (lessons, standards, settings)
  - **Deterministic layers**: On cognitive framework selectors — "These levels are rule-based, not AI-chosen"
  - **Cost awareness**: On provider selection — "Real providers charge per request. Mock mode is free but uses placeholder content."
  - **Bias awareness**: On generated content — "AI-generated content may reflect biases. Review for fairness and inclusion."
  - **Data privacy**: On lesson logging — "Your lesson content is sent to the AI provider. No student names or PII should be included."
- [ ] Tooltips should cite sources (e.g., "Learn more: UNESCO AI Competency Framework")
- [ ] All tooltip text stored in a central config for easy updates and localization
- [ ] References:
  - [U.S. Dept. of Education (2023). AI and the Future of Teaching and Learning](https://www.ed.gov/sites/ed/files/documents/ai-report/ai-report.pdf)
  - [UNESCO (2024). AI Competency Framework for Teachers](https://www.unesco.org/en/articles/ai-competency-framework-teachers)
  - [Digital Promise (2024). AI Literacy Framework](https://digitalpromise.org/2024/06/18/ai-literacy-a-framework-to-understand-evaluate-and-use-emerging-technology/)
  - [ISTE (2024). Standards for Educators](https://iste.org/standards/educators)

### BL-020: Help Page — AI Literacy Section [P1]
- [ ] Dedicated "Understanding AI in QuizWeaver" section on the help page
- [ ] Explain in plain language:
  - What generative AI is and how it works (inputs → model → outputs)
  - Why human review matters (hallucinations, bias, accuracy)
  - What "glass box" means — QuizWeaver shows its work (which lessons, which standards, which framework)
  - How deterministic layers (Bloom's, DOK, rubric criteria) constrain AI output
  - Privacy: what data goes to the AI, what stays local
  - Cost: how token-based pricing works, why mock mode exists
- [ ] Include links to authoritative sources (UNESCO, US DOE, ISTE, Digital Promise)
- [ ] Tone: empowering, not intimidating — "You don't need to be a tech expert to use AI responsibly"
- [ ] References:
  - [UNESCO (2024). AI Competency Framework for Teachers](https://www.unesco.org/en/articles/ai-competency-framework-teachers)
  - [U.S. Dept. of Education (2023). AI and the Future of Teaching and Learning](https://www.ed.gov/sites/ed/files/documents/ai-report/ai-report.pdf)
  - [Khosravi et al. (2022). Explainable AI in Education](https://www.sciencedirect.com/science/article/pii/S2666920X22000297)

### BL-021: AI Confidence & Limitation Indicators [P1] `[~] partially done`
- [x] Show indicators on AI-generated content that communicate uncertainty
- [x] E.g., "This quiz was generated by AI. Please review all questions for accuracy before use."
- [x] Banner on every generated quiz, study material, variant, and rubric
- [x] Link to help page AI literacy section
- [x] Privacy notice on lesson logging form (data sent to AI provider, no PII)
- [ ] Make banners dismissable per-session (localStorage)
- [ ] References: [Springer (2024). Trust, Credibility and Transparency in Human-AI Interaction](https://link.springer.com/article/10.1007/s40593-025-00486-6)

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

### BL-005: Help Page — Clarify Mock Provider [P2] `[x] done (Session 7)`
- [x] Current help page makes mock provider sound like it generates real quizzes for free
- [x] Clarify that mock mode produces test/placeholder data only — not real AI-generated content
- [x] Explain when and why to use mock mode (development, demos, testing the UI)
- [x] Guide teachers to configure a real provider for actual quiz generation

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

### BL-017: Redesign Dashboard as Tool-Oriented Landing Page [P1] `[x] done (Session 7)`
- [x] Classes at top, tool cards grid, recent activity feed
- [x] Removed stat cards and Chart.js chart
- [x] Action-oriented layout guiding teachers to workflows
- [x] Getting-started banner for new users
- [x] Empty state when no classes exist

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
### Session 7: Dashboard Redesign, Provider Test Connection, Help Clarification [DONE]
