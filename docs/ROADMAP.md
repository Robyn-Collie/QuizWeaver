# QuizWeaver Feature Roadmap

> Persisted plan for multi-session implementation. Updated 2026-02-09.

## Vision
A free, open-source teaching tool that rivals paid platforms (MagicSchool.ai, Quizizz, Kahoot, Gimkit) by giving teachers full control over AI-generated assessments — without subscription fees. Teachers only need a Vertex AI / Gemini API billing account.

---

## Session 1 (Current): Bloom's/DOK + Question Distribution

### Core Feature: Cognitive Framework Integration
- [ ] **Framework toggle**: Bloom's Taxonomy (6 levels) OR Webb's DOK (4 levels)
- [ ] **Question type distribution table**: Teacher sets count per cognitive level
- [ ] **Question type checkboxes**: MC, T/F, fill-in-the-blank, short answer, matching, essay per level
- [ ] **Difficulty slider**: 1-5 scale controlling vocabulary complexity and question depth
- [ ] **Updated generate form UI**: Dynamic table that swaps based on framework choice
- [ ] **Generator prompt updates**: Pass framework + distribution to LLM
- [ ] **Agent pipeline updates**: Carry distribution through style_profile → context → prompt
- [ ] **Mock response updates**: Return framework-appropriate mock data
- [ ] **Question model tagging**: Store bloom_level / dok_level on each question
- [ ] **Quiz detail display**: Show cognitive level tags on question cards
- [ ] **Playwright UI tests**: Verify form interaction, generation flow, result display

---

## Session 2: Export Formats + Quiz Editing

### Export Expansion
- [ ] Word/DOCX export (python-docx) — printable classroom handouts
- [ ] CSV export — spreadsheet-friendly for data analysis
- [ ] GIFT format export — Moodle compatibility
- [ ] Improved QTI export — fix known Canvas bugs
- [ ] Download buttons on quiz detail page

### Quiz Editing in UI
- [ ] Edit individual questions (text, options, correct answer)
- [ ] Delete/reorder questions
- [ ] Change question type after generation
- [ ] **Per-question regeneration with teacher notes**: Teacher can regenerate any single question (keeping others) with a text box for guidance — e.g., "make this about mitosis instead", "add a diagram", "make it harder", "relate it to our field trip". The AI receives the original question + teacher notes as context, producing a replacement that matches the teacher's intent.
- [ ] Edit quiz title and metadata

### Question Images (Human-in-the-Loop)
- [ ] **Teacher image upload**: Upload custom images per question (classroom photos, diagrams, screenshots)
- [ ] **Programmatic image search**: Search free image APIs (Wikimedia Commons, Unsplash, Pixabay) using AI-generated `image_description` as search query — teacher picks from results
- [ ] **AI image generation**: Generate images via Vertex AI Imagen from `image_description` — teacher approves/rejects
- [ ] **Image management**: Replace, remove, or reorder images on any question
- [ ] **Image in prompt**: Teachers can attach images when requesting question regeneration (e.g., "make a question about this diagram")

---

## Session 3: Flashcards + Study Materials

### Companion Study Materials
- [ ] Flashcard generation from same lesson content
- [ ] Flashcard export (Anki-compatible, printable PDF)
- [ ] Study guide generation (topic summaries)
- [ ] Vocabulary list extraction
- [ ] Review sheet tied to quiz topics

---

## Session 4: Scaffolded Variants + Differentiation

### Reading Level Variants
- [ ] Generate same quiz at multiple reading levels (ELL, remediation, on-level, advanced)
- [ ] Simplified vocabulary mode
- [ ] Extended time accommodations flagging
- [ ] Side-by-side variant comparison in UI

### Rubric Generation
- [ ] Auto-generate scoring rubrics aligned to quiz standards
- [ ] Rubric export (Word, PDF)
- [ ] Rubric tied to Bloom's/DOK levels

---

## Session 5: Performance Analytics + Gap Analysis

### Student Performance Tracking
- [ ] Import class performance data (CSV upload)
- [ ] Populate PerformanceData table (already in schema)
- [ ] Dashboard: assumed knowledge vs. actual performance
- [ ] Topic-level gap identification
- [ ] Trend charts over time

### Re-teach Suggestions
- [ ] AI-generated lesson plan suggestions based on gaps
- [ ] Targeted quiz generation for weak areas
- [ ] Progress tracking toward standards mastery

---

## Session 6: Production Hardening + Polish

### Authentication & Security
- [ ] Proper user accounts (bcrypt passwords, session management)
- [ ] Multi-teacher support
- [ ] Role-based access (admin vs. teacher)

### UI Polish
- [ ] Loading spinners / progress bars for generation
- [ ] Toast notifications
- [ ] Search and filtering on all tables
- [ ] Dark mode
- [ ] Print-optimized CSS
- [ ] Question bank (save/reuse favorites)
- [ ] Keyboard shortcuts

### Deployment
- [ ] PostgreSQL migration option
- [ ] Docker containerization
- [ ] One-click setup script
- [ ] Teacher onboarding wizard

---

## Features Explicitly Out of Scope
- Live game delivery (Kahoot/Gimkit space)
- Full gradebook/LMS replacement
- 80+ generic AI tools (stay focused on assessment)
- Real-time multiplayer
- Student-facing accounts

---

## Competitive Reference
| Feature | MagicSchool | Quizizz | Kahoot | QuizWeaver |
|---------|-------------|---------|--------|------------|
| AI quiz generation | Yes ($8-13/mo) | Yes (paid) | Yes (paid) | Yes (free) |
| Bloom's/DOK control | No | No | No | **Session 1** |
| Question type distribution | Limited | Limited | No | **Session 1** |
| Export (QTI, Word, CSV) | Limited | 20+ formats | Limited | **Session 2** |
| Quiz editing | Yes | Yes | Yes | **Session 2** |
| Flashcards | No | Yes (paid) | Yes (paid) | **Session 3** |
| Scaffolded variants | No | No | No | **Session 4** |
| Performance analytics | No | Yes (paid) | Yes (paid) | **Session 5** |
| Privacy/local-first | No | No | No | **Always** |
| Cost | $8-13/mo | $8+/mo | $6+/mo | API costs only |
