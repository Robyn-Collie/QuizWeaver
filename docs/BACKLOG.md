# QuizWeaver Backlog

> Feature requests, bugs, and refinements tracked for future planning sessions.
> Updated: 2026-02-11

## How This Works
- Items are categorized by area and prioritized (P1 = high, P2 = medium, P3 = nice-to-have)
- Each item has a unique ID (e.g., `BL-001`) for reference in commits and discussions
- Status: `[ ]` open, `[~]` in progress, `[x]` done
- When implementing, reference the backlog ID in your commit message

### Student Data Protection Principle
> **QuizWeaver is teacher-facing only.** No feature may send student work (essays, answers, writing samples) to cloud AI providers. No feature should create a path — even an accidental one — for student content to reach third-party APIs. Features that process student content must be constrained to local-only execution and must refuse to run with cloud providers. This protects teachers from FERPA violations, career harm, and loss of community trust.

---

## LLM Provider Configuration

### BL-001: LLM Provider Setup UI [P1] `[x] done (Session 8)`
- [x] Settings page where teachers can configure LLM providers (Gemini, Vertex AI, OpenAI-compatible)
- [x] API key entry with masked display
- [x] Connection test button ("Test Connection") that makes a minimal API call and reports success/failure
- [x] Provider selection dropdown with status indicators (configured, not configured, error)
- [x] Support for multiple configured providers with a "default" selection
- [x] Should be truly LLM-agnostic — any supported provider works seamlessly
- [ ] Clear error messages when configuration is wrong (invalid key, wrong endpoint, quota exceeded)

### BL-002: Per-Task Provider Selection [P2] `[x] done (Session 8)`
- [x] When generating quizzes, study materials, variants, etc., allow teacher to pick which LLM provider to use
- [x] Dropdown on generation forms showing only configured/tested providers
- [ ] Remember last-used provider per task type

### BL-018: Provider Setup Wizard [P1] `[x] done (Session 8)`
- [x] Guided step-by-step flow for configuring a real LLM provider
- [x] Steps: pick provider → get API key (with links to AI Studio / OpenAI / Ollama docs) → paste key → test → done
- [x] Inline help explaining what each provider is, cost implications, and privacy considerations
- [x] Contextual AI literacy: explain what an API key is, why local models (Ollama) are more private, what "tokens" mean
- [x] Accessible from "Setup needed" badges on providers and from the getting-started banner

---

## AI Literacy & Responsible AI

### BL-019: AI Literacy Tooltips & Contextual Education [P1] `[x] done (Session 8)`
- [x] Add `?` help tooltips throughout the UI that teach AI concepts in context
- [x] Key concepts surfaced where relevant (human-in-the-loop, verification, glass box, deterministic layers, cost, bias, privacy)
- [x] All tooltip text stored in central `src/web/tooltip_data.py` for easy updates
- [x] Context processor injects tooltips into all templates

### BL-020: Help Page — AI Literacy Section [P1] `[x] done (Session 8)`
- [x] Dedicated "Understanding AI in QuizWeaver" section on the help page
- [x] 6 collapsible accordion topics with cited sources
- [x] Links to UNESCO, US DOE, ISTE, Digital Promise, Khosravi et al.

### BL-021: AI Confidence & Limitation Indicators [P1] `[x] done (Session 8)`
- [x] Banners on every generated quiz, study material, variant, and rubric
- [x] Privacy notice on lesson logging form
- [x] Make banners dismissable per-session (sessionStorage)
- [x] Link to help page AI literacy section

---

## Standards & Curriculum

### BL-003: Deterministic Standards Database [P1] `[x] done (Session 8)`
- [x] Pre-loaded SOL (Standards of Learning) standards — 85 Virginia standards across Math, English, Science
- [x] Teachers can view, search, and browse standards by subject/grade
- [x] Standards data stored in database via `src/standards.py`
- [x] Auto-loaded from `data/sol_standards.json` on first access
- [x] `/standards` browse page with `/api/standards/search` endpoint

### BL-004: Better Standards Input UX [P1] `[x] done (Session 8)`
- [x] Searchable autocomplete with tag chips (`static/js/standards_picker.js`)
- [x] Debounced search, keyboard navigation, Enter for custom codes
- [x] Replaced plain text input on class forms and quiz generation
- [x] Graceful fallback to free-text if no standards DB loaded

### BL-022: Multi-State Standards Database [P1]
- [ ] Expand standards database beyond Virginia SOL to cover all 50 US states
- [ ] Support Common Core State Standards (CCSS) as a baseline
- [ ] Support Next Generation Science Standards (NGSS)
- [ ] Support state-specific standards (e.g., Texas TEKS, California CA-CCSS, Florida BEST)
- [ ] Allow teachers to select their state/standard set during onboarding or settings
- [ ] Standards versioning: track which year/edition of standards is loaded
- [ ] Import mechanism for teachers to upload custom standards (CSV/JSON)
- [ ] Consider standards alignment mapping (how state standards relate to CCSS)
- [ ] This is critical for the deterministic layer — standards must be rule-based, not AI-generated

### BL-023: Additional Deterministic Layers [P2]
- [ ] Grade-level reading complexity bands (Lexile, Flesch-Kincaid) as rule-based constraints
- [ ] Curriculum pacing guides (deterministic scope & sequence)
- [ ] Assessment blueprint templates (% of questions per standard/domain) as constraints
- [ ] All of these constrain AI output with predictable, auditable rules

---

## Help & Onboarding

### BL-005: Help Page — Clarify Mock Provider [P2] `[x] done (Session 7)`
- [x] Clarified that mock mode produces placeholder data, not real AI content

### BL-014: Teacher Onboarding Wizard [P3] `[x] done (Session 8)`
- [x] First-time setup flow: welcome → create class → start using tools
- [x] Dashboard redirects to onboarding when 0 classes exist
- [x] Skip button available at every step

---

## Cost Tracking

### BL-006: Cost Tracking Improvements [P2] `[x] done (Session 8)`
- [x] Time-period breakdown (daily, weekly, monthly)
- [x] Per-action and per-provider cost breakdowns
- [x] Budget threshold with warnings
- [x] Reset/clear cost history

---

## Study Materials

### BL-007: Study Material Inline Editing [P1] `[x] done (Session 8)`
- [x] Edit/delete/reorder individual items within study sets
- [x] Inline edit forms for all 5 material types
- [x] Keyboard shortcuts: Ctrl+Enter to save, Escape to cancel

### BL-008: Images in Study Materials [P2]
- [ ] Add images to flashcards (upload, search, or AI-generate)
- [ ] Add images to study guide sections
- [ ] Image support in study material exports (PDF, DOCX)

### BL-009: Source Quiz Dropdown — Show More Context [P2] `[x] done (Session 8)`
- [x] Quiz ID, class name, date in dropdown
- [x] Grouped by class with optgroup

---

## Topic-Based Generation

### BL-010: Topic Selection UI [P1] `[x] done (Session 8)`
- [x] Topic autocomplete from lesson history
- [x] Supports all 5 output types (quiz, flashcard, study guide, vocabulary, review sheet)
- [x] `/generate/topics` page with `/api/topics/search` endpoint
- [x] Tool card on dashboard

---

## Dashboard Redesign

### BL-017: Redesign Dashboard as Tool-Oriented Landing Page [P1] `[x] done (Session 7)`
- [x] Classes at top, tool cards grid, recent activity feed

---

## UI/UX Refinements

### BL-011: Loading Spinners / Progress Bars [P2] `[x] done (Session 8)`
- [x] Loading overlay during LLM generation on all forms
- [x] CSS-only spinner, no external deps

### BL-012: Question Bank [P3] `[x] done (Session 8)`
- [x] Save/favorite questions from quiz detail page
- [x] `/question-bank` browse page with search and type filter

### BL-013: Keyboard Shortcuts [P3] `[x] done (Session 8)`
- [x] Chord-based shortcuts (g+d, n+q, ? for help)
- [x] Help modal listing all shortcuts

### BL-024: Edge Autofill Prevention on Settings Fields [P1] `[x] done (Session 9)`
- [x] Microsoft Edge (and Chrome) autofills the model_name and api_key fields on settings/wizard pages with saved login credentials
- [x] Add `autocomplete="off"` or `autocomplete="new-password"` to API key and model name inputs
- [ ] Test across Edge, Chrome, Firefox, Safari

### BL-025: Lesson Logging Value Explanation [P1] `[x] done (Session 9)`
- [x] On the lesson log page (`/lessons/new`), explain WHY logging lessons helps QuizWeaver
- [x] Info banner with clear explanation of lessons → context → better AI output
- [x] Add tooltip on "Log Lesson" button in class view (`/classes/<id>`) explaining the value
- [x] Tooltip entry added to `src/web/tooltip_data.py`

### BL-026: Keyboard Shortcuts Discoverability [P1] `[x] done (Session 9)`
- [x] Show a persistent hint at the bottom of every page: "Press ? for keyboard shortcuts"
- [x] Small footer line with kbd styling, fades after first use
- [x] Store "seen" state in localStorage so it only shows prominently for new users

### BL-027: Responsive Navigation for Many Pages [P1] `[x] done (Session 9)`
- [x] Grouped nav links into "Generate" and "Tools" dropdown submenus
- [x] Hamburger menu on mobile with collapsible dropdowns
- [x] Username + logout moved to separate nav-user-section
- [x] All pages reachable on mobile viewport widths
- [ ] Test at common breakpoints: 320px, 375px, 768px, 1024px, 1440px

### BL-028: Mobile-First Responsive Design [P2]
- [ ] Full mobile optimization pass across all pages
- [ ] Touch-friendly buttons and form controls (min 44px tap targets)
- [ ] Responsive tables (horizontal scroll or card layout on mobile)
- [ ] Mobile-friendly modals and dropdowns
- [ ] Test on iOS Safari and Android Chrome
- [ ] Consider PWA (Progressive Web App) manifest for "Add to Home Screen"

### BL-029: Username Display Fix [P1] `[x] done (Session 9)`
- [x] Username moved to nav-user-section with user icon SVG
- [x] Proper truncation (max-width + ellipsis) for long names, correct alignment
- [x] Responsive: full width on mobile with horizontal separator

### BL-030: Dark Mode Tooltip Contrast Fix [P1] `[x] done (Session 9)`
- [x] Help tooltips (`?` icons) had text color too similar to background in dark mode
- [x] Added dark mode override: dark bg (#1a1e24) + light text (#f0ebe4) + subtle border
- [x] WCAG AA contrast ratio (4.5:1 minimum) met for all tooltip text

---

## Accessibility & Inclusion

### BL-031: Dyslexia-Friendly Font Toggle [P1]
- [ ] Add OpenDyslexic font as a user preference toggle in settings
- [ ] Apply font override to all quiz display, study material, and export preview pages
- [ ] Include OpenDyslexic in exported DOCX/PDF when enabled
- [ ] Add increased letter/word/line spacing option (WCAG SC 1.4.12)
- [ ] Store preference per user in database
- **Competitors**: Wayground ships dyslexia font as built-in accommodation; Texas STAAR uses it for standardized testing
- **Feasibility**: High — OpenDyslexic is free/open-source, CSS-only for web display, font embedding for exports
- **Sources**: [Wayground Accessibility](https://support.wayground.com/hc/en-us/articles/360055566272), [Best Fonts for Dyslexia](https://www.inclusiveweb.co/accessibility-resources/best-font-styles-for-dyslexia)

### BL-032: Text-to-Speech for Quiz Display [P2]
- [ ] Add "Read Aloud" button on quiz display and study material pages using browser Web Speech API
- [ ] Allow per-question TTS playback (not just whole-page)
- [ ] Configurable speech rate and voice selection
- [ ] Consider server-side TTS for exported audio versions of quizzes (stretch goal)
- [ ] TTS is a standard accommodation for state assessments (STAAR, NJSLA)
- **Competitors**: Wayground has read-aloud; ReadSpeaker integrates with multiple assessment platforms; Texas STAAR uses TTS as standard accommodation
- **Feasibility**: High for browser-based (Web Speech API is free, zero dependency); Medium for exported audio
- **Sources**: [TTS in Education (MDPI)](https://www.mdpi.com/2673-4591/112/1/4), [ReadSpeaker Assessments](https://www.readspeaker.com/sectors/education/assessments/)

### BL-033: Color Blind Safe Theme [P2]
- [ ] Add a color-blind-friendly theme option (in addition to light/dark mode)
- [ ] Use Wong color palette or viridis-based colors for all data visualizations (analytics charts)
- [ ] Ensure all color-coded information also has text/pattern indicators
- [ ] Audit existing UI for color-only information conveyance
- [ ] Meet WCAG AA contrast ratio (4.5:1) across all themes
- **Competitors**: Wayground includes accessibility supports; most competitors lag here
- **Feasibility**: High — CSS theme + audit, no external dependencies
- **Sources**: [WCAG and Dyslexia](https://wcagready.com/en/digital-accessibility-and-dyslexia/), [Harvard Digital Accessibility](https://accessibility.huit.harvard.edu/disabilities/dyslexia)

### BL-034: Screen Reader Optimization (ARIA/Semantic HTML) [P2]
- [ ] Audit all pages for proper semantic HTML (headings, landmarks, form labels)
- [ ] Add ARIA labels to interactive elements (modals, dropdowns, tag chips, tooltips)
- [ ] Ensure all images have alt text (including AI-generated quiz images)
- [ ] Add skip-navigation link
- [ ] Test with NVDA or VoiceOver
- **Feasibility**: High — incremental HTML improvements, no new dependencies
- **Sources**: [Harvard Digital Accessibility: Dyslexia](https://accessibility.huit.harvard.edu/disabilities/dyslexia)

---

## Lesson Planning

### BL-035: Lesson Plan Generator [P1]
- [ ] Generate standards-aligned lesson plans from class context + lesson history + topics
- [ ] Include: learning objectives, warm-up, direct instruction, guided practice, independent practice, assessment, closure
- [ ] Differentiation section: below-grade, on-grade, advanced activities in one plan
- [ ] Link generated lesson plans to subsequent quiz generation (teach-assess loop)
- [ ] Export lesson plans to PDF and DOCX
- [ ] Use existing standards database (BL-003) for alignment
- [ ] Human-in-the-loop: teacher reviews and edits before finalizing
- **Competitors**: MagicSchool, SchoolAI, Flint, PlanSpark, Microsoft Copilot Teach all offer this
- **Feasibility**: High — QuizWeaver already has lesson tracking, standards DB, class context, and LLM pipeline; this connects existing pieces
- **Sources**: [SchoolAI Lesson Plans](https://schoolai.com/blog/ai-lesson-plan-generator-standards-aligned), [10 Best AI Lesson Planners 2026](https://www.edcafe.ai/blog/ai-lesson-planners)

---

## Assessment Innovation

### ~~BL-036: Constructed Response Feedback Suggestions~~ [REJECTED]
> **Rejected per Student Data Protection Principle.** Sending student writing to cloud AI providers creates unacceptable FERPA risk. Even with human-in-the-loop review, the student's work has already left the device at the API call. This could harm teachers' careers and violate school data policies. If local-only grading assistance is ever needed, it would be a separate project constrained to local execution (spaCy, sentence-transformers, Ollama).

### ~~BL-037: Adaptive Practice Mode~~ [REJECTED]
> **Rejected: QuizWeaver is teacher-facing only.** Adaptive practice is a student-facing feature that would require student authentication, data retention policies, COPPA compliance, and a fundamentally different trust model. QuizWeaver generates materials for teachers; teachers deliver them however they choose.

### BL-038: Additional Question Types (Ordering, Short Answer) [P2]
- [ ] Ordering/sequencing questions: student arranges items in correct order
- [ ] Short answer (free text) for teacher-graded responses
- [ ] Represent in JSON structure for internal use and QTI export
- [ ] Support in DOCX/PDF export (numbered blanks for ordering, write-in lines for short answer)
- [ ] Consider drag-and-drop matching for web display (stretch goal)
- **Competitors**: Canvas New Quizzes (ordering, hotspot), Kahoot (slider, type answers), Wayground (multiple interactive types)
- **Feasibility**: Medium — JSON representation is straightforward; interactive web UI requires JavaScript; export support is incremental

---

## Community & Sharing

### BL-039: Quiz Template Export/Import [P2]
- [ ] Export quiz as a shareable JSON template (questions, metadata, standards, cognitive levels — no student data)
- [ ] Import JSON template to create a new quiz in any class
- [ ] Template includes: question text, options, correct answer, cognitive level, standards, difficulty
- [ ] Template excludes: student performance data, class-specific context, teacher identity
- [ ] Consider a `/templates` page for browsing imported templates
- [ ] Foundation for future community library feature
- **Competitors**: Wayground (public quiz library), Kahoot (template library), Gimkit (kit sharing)
- **Feasibility**: High — JSON export/import is straightforward with existing data models; no external infrastructure needed
- **Sources**: [Kahoot Template Library](https://kahoot.com/library/)

---

## Infrastructure

### BL-015: PostgreSQL Migration Option [P3]
- [ ] Support PostgreSQL as an alternative to SQLite for multi-user deployments
- [ ] Migration script from SQLite to PostgreSQL

---

## Research

### BL-016: Competitor Analysis Deep Dive [P2] `[x] done (existing doc)`
- [x] Comprehensive analysis in `docs/COMPETITIVE_ANALYSIS.md`

---

## Completed (Archive)

### Session 1: Bloom's/DOK + Question Distribution [DONE]
### Session 2: Export Formats + Quiz Editing [DONE]
### Session 3: Flashcards + Study Materials [DONE]
### Session 4: Scaffolded Variants + Rubric Generation [DONE]
### Session 5: Performance Analytics + Gap Analysis [DONE]
### Session 6: Auth, Dark Mode, Search, Docker [DONE]
### Session 7: Dashboard Redesign, Provider Test Connection, Help Clarification [DONE]
### Session 8: SDK Migration + Full Backlog Blitz (16 features) [DONE]
### Session 9: P1 UX Fixes (BL-024-030) + Competitor Research (BL-031-039) [DONE]
