# QuizWeaver E2E Test Report

**Date:** 2026-02-12
**Tester:** Automated (Playwright MCP + Claude Code)
**Environment:** Windows 11, Python 3.x, Flask dev server (port 5099)
**Database:** Temporary SQLite (isolated test DB)
**LLM Providers Tested:** Gemini 2.5 Flash, Gemini 2.5 Pro, Gemini 3 Flash (preview), Gemini 3 Pro (preview)

---

## 1. Test Scenario

**Class:** 7th Grade Life Science - Block A
**Standards:** SOL 3.6E, SOL 7.2E, SOL BIO.3
**Lessons Logged:**
1. Plant cell structure: plant cells, cell structure, chloroplasts, photosynthesis, cell wall, microscope lab
2. Photosynthesis and plant reproduction: photosynthesis, Calvin cycle, plant reproduction, pollination, seed dispersal, flower anatomy

**Quiz Configuration:** 5 questions, Bloom's Taxonomy (1 per level: Remember through Evaluate), difficulty 3/5, multiple-choice only

---

## 2. Quiz Generation Results

### Quiz 1: Gemini 2.5 Flash

| Metric | Value |
|--------|-------|
| Model | gemini-2.5-flash |
| API Calls | 2 (1 generate + 1 critique) |
| Total Time | ~25s |
| Critic Result | APPROVED on 1st attempt |
| Input Tokens | 3,201 (1,165 gen + 2,036 crit) |
| Output Tokens | 834 (833 gen + 1 crit) |

**Assessment:** Fastest provider. Approved on first try. Questions covered plant cells, photosynthesis, cell structure. Good quality, appropriate grade level.

### Quiz 2: Gemini 2.5 Pro

| Metric | Value |
|--------|-------|
| Model | gemini-2.5-pro |
| API Calls | 6 (3 generate + 3 critique cycles) |
| Total Time | ~125s |
| Critic Result | REJECTED x2, APPROVED on 3rd attempt |
| Input Tokens | 10,353 |
| Output Tokens | 3,105 |

**Rejection Reasons:**
- Cycle 1: Difficulty mismatch — Evaluate question too advanced for depth-1 knowledge on plant reproduction
- Cycle 2: Off-topic content, grade level concerns

**Assessment:** Strictest critic among all providers. Generates more detailed content but the critic catches valid issues (depth mismatch). 5x more expensive than Flash due to retries.

### Quiz 3: Gemini 3 Flash (Preview)

| Metric | Value |
|--------|-------|
| Model | gemini-3-flash-preview |
| API Calls | 6 (3 generate + 3 critique cycles) |
| Total Time | ~84s |
| Critic Result | REJECTED all 3 times — used best available draft |
| Input Tokens | 10,209 |
| Output Tokens | 3,151 |

**Rejection Reasons (all 3 cycles):**
- Empty reference content (no source document provided)
- Content validity: questions use outside information not in source text
- Grade level/rigor inconsistency

**Assessment:** Critic is overly strict about "Reference Content Summary" being empty. The current workflow uses lesson topics (not uploaded documents) as context, but the critic prompt expects source material. This is a prompt engineering issue, not a model issue. Final questions were good quality.

### Quiz 4: Gemini 3 Pro (Preview)

| Metric | Value |
|--------|-------|
| Model | gemini-2.5-pro (BUG — see Section 5) |
| API Calls | 4 (2 generate + 2 critique cycles) |
| Total Time | ~91s |
| Critic Result | REJECTED x1, APPROVED on 2nd attempt |
| Input Tokens | 7,337 |
| Output Tokens | 2,471 |

**Rejection Reason:** Difficulty mismatch on Evaluate question for depth-1 reproduction knowledge.

**Assessment:** Due to the alias bug (Section 5), this quiz actually used gemini-2.5-pro instead of gemini-3-pro-preview. Results are consistent with Quiz 2's behavior. Bug has been fixed.

---

## 3. Timing Summary

| Quiz | Provider | API Calls | Total Time | Retries | Cost Class |
|------|----------|-----------|------------|---------|------------|
| 1 | Gemini 2.5 Flash | 2 | ~25s | 0 | Low |
| 2 | Gemini 2.5 Pro | 6 | ~125s | 2 | High |
| 3 | Gemini 3 Flash | 6 | ~84s | 3 (max) | Medium |
| 4 | Gemini 2.5 Pro* | 4 | ~91s | 1 | Medium |

**Totals:**
- Total API Calls: 18
- Total Input Tokens: ~31,100
- Total Output Tokens: ~9,561
- Total Generation Time: ~325s (~5.4 minutes)
- Estimated Cost: ~$0.05-0.15 (Gemini pricing as of Feb 2026)

---

## 4. Export Testing Results

All 4 quizzes tested across 6 export formats — **24/24 successful (HTTP 200)**.

| Format | MIME Type | Avg Size | Verified |
|--------|-----------|----------|----------|
| Word (DOCX) | application/vnd.openxmlformats-officedocument.wordprocessingml.document | ~36 KB | Content structure confirmed |
| PDF | application/pdf | ~4 KB | Valid PDF |
| CSV | text/csv | ~2.5 KB | Headers, A/B/C/D options, Bloom's levels |
| GIFT (Moodle) | text/plain | ~2 KB | Valid syntax (=correct, ~distractor) |
| QTI (Canvas) | application/zip | ~2 KB | Valid IMS QTI ZIP package |
| Template (JSON) | application/json | ~4 KB | 9 keys, 5 questions, round-trip capable |

---

## 5. Bugs Found

### BUG-1: Model Alias Mismatch (CRITICAL — FIXED)

**Issue:** `_PROVIDER_ALIASES` in `llm_provider.py` mapped `"gemini-3-pro"` to `"gemini-pro"`, causing the factory to use `gemini-2.5-pro` instead of `gemini-3-pro-preview`.

**Impact:** Teacher's UI displayed "gemini-3-pro" but the actual API call went to the wrong model. Violates Glass Box (transparency) and Cost Transparency principles.

**Fix:** Removed the incorrect alias. Each provider now resolves to its own registry entry with the correct `default_model`.

### BUG-2: Standards Display Garbled (FIXED)

**Issue:** Quiz detail page showed `[`, `E`, `O`, `L`, etc. instead of `SOL 3.6E, SOL 7.2E` because `style_profile.sol_standards` was a JSON string, and Jinja2's `|join` iterated individual characters.

**Fix:** Added `|ensure_list` filter before `|join` in `detail.html`.

### BUG-3: Generate Menu 404 (FIXED)

**Issue:** "Generate > Quiz" nav link pointed to `/generate` which had no route.

**Fix:** Added a `/generate` redirect route that sends to the first class's generate page, or to `/classes/new` if no classes exist.

### BUG-4: Critic Prompt — Empty Reference Content

**Issue:** The Critic Agent flags "empty reference content" on nearly every attempt across all providers. The critic prompt expects a source document, but QuizWeaver's lesson-based workflow provides topic keywords, not documents.

**Status:** Not yet fixed — requires prompt engineering. Added to backlog as BL-045.

---

## 6. Data Sent to External APIs

### Sent to LLM Providers

| Data Type | Included | Example |
|-----------|----------|---------|
| Teacher role description | Yes | "7th Grade teacher and curriculum designer" |
| SOL standards codes | Yes | "SOL 3.6E, SOL 7.2E, SOL BIO.3" |
| Lesson topic keywords | Yes | "plant cells, photosynthesis, Calvin cycle" |
| Assumed knowledge depths | Yes | "topic: depth 1-5" ratings |
| Cognitive framework rules | Yes | "Bloom's Taxonomy" level instructions |
| Question count/difficulty | Yes | "5 questions, difficulty 3/5" |
| Generated quiz JSON (critic) | Yes | Full question set for QA review |

### NOT Sent to LLM Providers

| Data Type | Status |
|-----------|--------|
| Student names or IDs | NEVER sent |
| Student work, essays, answers | NEVER sent |
| Grades or performance data | NEVER sent |
| Teacher personal information | NEVER sent |
| School or district identifiers | NEVER sent |
| Login credentials or tokens | NEVER sent |
| API keys (in prompt content) | NEVER sent |

---

## 7. Principles Analysis

### Principle 1: Human-in-the-Loop — PASS

- "AI-Generated Content" banner on every quiz with dismiss option
- Warning tooltip: "AI-generated questions are drafts"
- Edit, Regenerate, Delete controls on every question
- Quiz status shows "generated" (not "approved" or "final")
- No auto-distribution to students — teacher must manually export

### Principle 2: Glass Box, Not Black Box — PARTIAL PASS

**Passing:**
- Class context (lessons, standards, framework) shown on generate form
- Provider name displayed on quiz detail page
- Cognitive levels visible per question
- Standards alignment shown

**Gaps:**
- No visibility into what prompts were sent to the LLM
- No visibility into critic feedback (rejection reasons not shown to teacher)
- No cost-per-quiz display on quiz detail page
- API audit log exists only as dev endpoint (`/api/audit-log`), not in teacher-facing UI

### Principle 3: Deterministic Layers — PASS

- Bloom's Taxonomy levels are rule-based (set by form checkboxes)
- Question distribution (per cognitive level) is deterministic
- Standards alignment is database-driven (SOL registry)
- Difficulty level is a numeric constraint (1-5)
- The AI operates within these constraints, not outside them

### Principle 4: Verification Over Trust — PASS

- Quiz labeled "generated" not "ready" or "approved"
- Edit/Regen/Delete controls on every question
- AI-Generated Content banner is prominent and informative
- "Learn more: Understanding AI in QuizWeaver" link provided
- No one-click "send to students" — export requires deliberate action

### Principle 5: Privacy by Design — PASS

- Zero student PII sent to APIs (verified via audit log capture)
- Only lesson topic keywords sent — no student work
- Local SQLite database — no cloud storage dependency
- API keys stored locally, never transmitted to QuizWeaver servers
- No analytics, telemetry, or tracking

### Principle 6: Cost Transparency — PARTIAL PASS

**Passing:**
- Provider name shown on quiz detail page
- Settings page warns "Real AI providers charge per request"
- Mock mode available for zero-cost exploration
- Multiple price-tier providers offered (Flash vs Pro)

**Gaps:**
- No per-quiz cost shown after generation
- No running cost total visible to teacher
- No cost estimate shown BEFORE generating
- Retry cycles (up to 3x) can multiply costs unpredictably

### Principle 7: Equity & Access — PASS

- Multiple provider options spanning free (Mock) to premium (Pro)
- Accessibility features: dyslexia font, color blind mode, TTS, screen reader support
- 6 export formats for different LMS platforms (Canvas, Moodle, generic)
- Works offline with Mock provider
- Mobile responsive design

### Principle 8: Student Data Protection — PASS

- No student data in any API call (verified via full audit log capture)
- No feature path for student work to reach cloud APIs
- Teacher-facing tool only — students never interact with the system
- FERPA compliant by design

---

## 8. New Backlog Items

| ID | Title | Principle | Priority |
|----|-------|-----------|----------|
| BL-040 | Show prompt summary to teacher after generation | Glass Box | P2 |
| BL-041 | Show critic feedback/rejection reasons in UI | Glass Box | P2 |
| BL-042 | Display per-quiz token usage and estimated cost | Cost Transparency | P2 |
| BL-043 | Show pre-generation cost estimate on form | Cost Transparency | P3 |
| BL-044 | Fix Generate menu navigation (done this session) | UX | P1 — DONE |
| BL-045 | Improve critic prompt for lesson-based workflows | Quality | P2 |
| BL-046 | Add model verification (actual vs displayed) | Trust/Glass Box | P2 |

---

## 9. Recommendations

1. **Default to Gemini 2.5 Flash** for most teachers — fastest, cheapest, approved on first try
2. **Fix the critic prompt** (BL-045) — the "empty reference content" rejection wastes tokens and time across all providers
3. **Add cost visibility** (BL-042/043) before any public release — teachers need to understand costs before they generate
4. **Add prompt transparency** (BL-040) — even a summary helps teachers understand and trust the system
5. **Consider retry cost caps** — if critic rejects 3 times, the cost is 3x. Teachers should be warned about this possibility
