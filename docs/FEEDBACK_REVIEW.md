# Teacher Feedback Review: QuizWeaver User Testing

> **Reviewed:** 2026-02-16
> **Source:** Transcript of user testing session with a Virginia life science teacher
> **Transcript:** ~1190 lines of conversation between developer (Speaker 1) and teacher (Speaker 2)

---

## Executive Summary

The teacher testing session uncovered **24 distinct feedback items** across quiz generation, export formatting, question types, standards, and workflow design.

| Category | Count |
|----------|-------|
| **ADDRESSED** (fixed/implemented) | 14 |
| **PARTIALLY ADDRESSED** | 3 |
| **PLANNED** (in backlog, not yet done) | 4 |
| **NEW GAP** (not addressed, not planned) | 3 |

**Overall:** 58% of feedback items are fully addressed, 71% at least partially addressed. The Session 16 commit (e9cdbaf) directly targeted this teacher's feedback and resolved the most critical issues. Three new gaps remain that warrant new backlog items.

---

## 1. ADDRESSED Items

### F1: Topics/Content text field on generate form
**Feedback:** Teacher had no way to specify what the quiz should be about. Pasting curriculum framework text into the form produced wrong results (cell organelles instead of osmosis/diffusion). Teacher wants to paste "enduring understandings" and "essential knowledge and practices" directly from Virginia SOL curriculum framework PDF.
**Status:** ADDRESSED (Session 16, BL-057)
**Evidence:** `templates/quizzes/generate.html` now has:
- A `topics` text input (line 24): comma-separated topics
- A `content_text` textarea (lines 28-32): large text area for pasting curriculum content with helpful placeholder text
- Form hint: "Paste specific content from your curriculum framework..."
- The content is passed through to the LLM prompt for generation

### F2: Standards search broken (couldn't find SOL LS2e)
**Feedback:** Teacher searched for "LS2" in the standards picker and it returned no results. The only way to specify content was through standards, which didn't work.
**Status:** ADDRESSED (Session 16)
**Evidence:** MEMORY.md notes "Standards search was limited to 20 results (now 50 with truncation message)." The `search_standards()` function in `src/standards.py` (line 214) searches across code, description, full_text, and strand fields.

### F3: Quiz generated wrong topic
**Feedback:** Teacher entered "cell transport, osmosis, diffusion" as topics but got a quiz on cell organelles. The `content_summary` was always empty.
**Status:** ADDRESSED (Session 16, BL-057)
**Evidence:** MEMORY.md confirms "CRITICAL finding: generate form had NO topics/content field (content_summary always '')" -- this was the root cause. Now the topics and content_text fields are wired through to the generator.

### F4: Question types should NOT be tied to Bloom's taxonomy levels
**Feedback:** "The question type does not correlate to level. That is not a fair correlation." Teacher wants to select question types independently, not per-Bloom's level.
**Status:** ADDRESSED (Session 16, BL-061)
**Evidence:** `templates/quizzes/generate.html` lines 60-69 show question types as independent checkboxes (MC, TF, Fill-in-blank, Short Answer, Matching, Ordering) in the "Quiz structure" section, completely separate from the cognitive framework section (lines 79-115). MEMORY.md confirms "BL-061: Question types decoupled from Bloom's [DONE, Session 16] (F6)."

### F5: Fill-in-the-blank needs word bank
**Feedback:** "Having kids come up with the word out of thin air, I think, is unfair." Teacher wants a word bank for fill-in-the-blank questions, like dropdown options in Canvas.
**Status:** ADDRESSED (Session 16, BL-060)
**Evidence:** `src/export.py` has word_bank support (lines 484-488 for DOCX, lines 908-912 for PDF). MEMORY.md confirms "BL-060: Fill-in-blank word bank [DONE, Session 16] (F7)."

### F6: Difficulty slider unclear
**Feedback:** "I'm not entirely sure what that difficulty level does. Does it control reading? Like, does it control text difficulty?"
**Status:** ADDRESSED (Session 16)
**Evidence:** `templates/quizzes/generate.html` line 73 shows descriptive difficulty labels: "1 = basic recall and recognition. 2 = below average. 3 = grade-level application. 4 = challenging analysis. 5 = evaluation and synthesis." MEMORY.md confirms "Difficulty slider was cosmetic (now has descriptive labels)."

### F7: Export should use A/B/C/D lettering, not bullets
**Feedback:** Teacher wants "A, B, C, D" answer labels, not bullet points.
**Status:** ADDRESSED (Session 16, BL-059)
**Evidence:** `src/export.py` has A/B/C/D lettering throughout:
- CSV: `letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"` (line 275)
- DOCX: `_add_docx_mc_options` uses letter labels (line 512)
- PDF: letter labels at line 889
- MEMORY.md confirms "BL-059: A/B/C/D lettering in exports [DONE, Session 16] (F11)."

### F8: Student-facing export (no highlighted answers, no Bloom's level)
**Feedback:** "It highlights the correct answer, which is not useful if you are trying to print it out." Teacher also doesn't want Bloom's levels shown on student copies.
**Status:** ADDRESSED (Session 16, BL-058)
**Evidence:** `src/export.py` has full `student_mode` parameter across CSV (line 198), DOCX (line 362), and PDF (line 744). In student mode:
- Correct answers not highlighted (DOCX line 523, PDF equivalent)
- Bloom's/cognitive level suppressed (DOCX line 459, PDF line 870)
- Suggested image text suppressed (DOCX line 471, PDF line 882)
- Answer key only for teacher copy (DOCX line 403, PDF line 800)
- Name/Date line added for student copies (DOCX line 390, PDF line 780)
- Export route: `?student=1` parameter (quizzes.py line 230)

### F9: Image upload broken
**Feedback:** Teacher tried to upload an image file and "it did not upload."
**Status:** ADDRESSED (Session 16, BL-062)
**Evidence:** MEMORY.md confirms "BL-062: Image upload CSRF fix [DONE, Session 16] (F14)." The upload endpoint exists at `api_question_image_upload` (quizzes.py line 431). The issue was a CSRF token not being sent with the JavaScript fetch request.

### F10: Suggested image text showing in export
**Feedback:** Teacher noticed the "suggested image" description (e.g., "side-by-side comparison diagram of plant cell and animal cell") appears in the printed export, which is not useful for students.
**Status:** ADDRESSED (Session 16, BL-058)
**Evidence:** In `student_mode`, image_description is suppressed (export.py line 471: `if not student_mode and nq.get("image_description")`). Teacher exports use `?student=1` to get clean student copies.

### F11: Cannot delete suggested image text from UI
**Feedback:** Teacher tried to remove the "suggested image" text from a question but couldn't.
**Status:** ADDRESSED (indirectly via student_mode)
**Evidence:** While direct deletion from the UI may still not be available, the student-facing export suppresses this text entirely, which is the teacher's actual need (clean printouts for students).

### F12: Lesson logging is extra work / privacy concern
**Feedback:** "I will not be doing this... I do not want to be giving large language models access to my lesson documents... logging a lesson for me is extra work."
**Status:** ADDRESSED (Session 16)
**Evidence:** `templates/quizzes/generate.html` line 12: "Lesson logging is optional. You can generate quizzes using topics and standards alone." The new topics + content_text fields make lesson logging unnecessary for quiz generation. MEMORY.md confirms "Teacher does NOT want lesson logging -- extra work, privacy concerns."

### F13: Standards on class creation not useful
**Feedback:** "Standards should not be part of class creation. If I am teaching a class on life science, it's going to be all the [standards]."
**Status:** ADDRESSED (design-level)
**Evidence:** Standards on class creation are already marked "optional" and pre-fill on the generate form only as a convenience. The generate form allows selecting specific standards per quiz, which is the teacher's actual workflow. The teacher can ignore standards at class creation and specify them at quiz generation time.

### F14: Teacher wants to specify content directly, not through lessons
**Feedback:** Teacher's workflow is: open curriculum framework PDF, copy specific enduring understandings and objectives, paste into quiz generation tool. Does not want to go through lessons.
**Status:** ADDRESSED (Session 16, BL-057)
**Evidence:** The `content_text` textarea on the generate form is designed exactly for this workflow. The placeholder text explicitly says "Paste specific content from your curriculum framework."

---

## 2. PARTIALLY ADDRESSED Items

### P1: Regeneration speed too slow
**Feedback:** "Regenerating is taking 10,000 years... as a person trying to make a quiz, I would be panicking about now." Teacher observed regeneration taking very long with no timeout indication.
**Status:** PARTIALLY ADDRESSED
**Evidence:** The regeneration endpoint exists (`api_question_regenerate`, quizzes.py line 527) and Session 16 fixed it to use the quiz's own LLM provider (commit e95943d). However, the speed issue is inherent to LLM API latency and there's no documented timeout or progress indicator specifically for single-question regeneration. The main quiz generation has a progress overlay with status messages (lines 145+), but individual question regeneration may lack similar UX feedback.
**Recommendation:** Add a loading spinner and timeout warning for single-question regeneration. Consider using a faster/cheaper model for single-question regeneration.

### P2: Fill-in-blank with dropdown/multiple options per blank
**Feedback:** Teacher wants Canvas-style fill-in-blank where each blank has a dropdown with 3 options (like a word bank inline). "Photosynthesis is the process by which [dropdown] is used to make [dropdown]."
**Status:** PARTIALLY ADDRESSED
**Evidence:** Word bank is implemented at the question level (export.py lines 484-488). However, the Canvas-style inline dropdown per blank (multiple blanks in one sentence, each with its own options) is a more advanced question type not yet implemented. The current fill-in-blank is a single blank per question with an overall word bank.
**Recommendation:** Consider adding a "cloze" question type with per-blank options as a P2 feature, or document that this is achieved through Canvas's native editor after QTI import.

### P3: Standards granularity (sub-sub-standard selection)
**Feedback:** Teacher needs to select content at a level MORE specific than the standard hierarchy. "LS3c is just... it covers an astronomical amount of content." Teacher wants to select specific enduring understandings and objectives within a sub-standard, not just the sub-standard code.
**Status:** PARTIALLY ADDRESSED
**Evidence:** The standards picker allows selecting standard codes (e.g., SOL LS.2e), and the content_text field allows pasting specific enduring understandings and objectives. Together these cover the teacher's workflow (select standard + paste specific content). However, the system doesn't have the curriculum framework's full enduring understandings/objectives hierarchy built in for drill-down selection.
**Recommendation:** The current two-field approach (standards picker + content textarea) adequately serves this need. A full curriculum framework drill-down UI would be a P3 stretch goal. Document the workflow: "Select the standard code, then paste the specific content you want assessed into the Content/Instructions box."

---

## 3. PLANNED Items (in backlog, not yet done)

### BL-063: Canvas interactive question types (hotspot, categorization, stimulus, drag-and-drop)
**Feedback:** Teacher demonstrated Canvas's question types: hotspot (click on image), categorization (sort items into categories), stimulus (one passage, multiple questions), drag-and-drop ordering. These are critical for SOL test preparation.
**Status:** PLANNED (BL-063, P3)
**Evidence:** MEMORY.md lists "BL-063: Canvas interactive question types (hotspot, categorization, stimulus) [P3]." Also referenced in BACKLOG.md BL-038 stretch goal for drag-and-drop matching.
**Recommendation:** Upgrade to P2. The teacher specifically said "What I need is something that can create interactive questions for Canvas" and "I can create multiple choice -- I need something for the tech-assisted questions." This is the primary differentiator the teacher is looking for.

### BL-064: TTS audio in QTI export for Canvas
**Feedback:** Teacher wants read-aloud audio files embedded in QTI exports so students can listen to questions in Canvas. "That would be magic." Teacher currently has to manually record audio for each question. Canvas supports per-question and per-answer audio uploads.
**Status:** PLANNED (BL-064, P3)
**Evidence:** MEMORY.md lists "BL-064: TTS audio in QTI export for Canvas [P3]." Web-based TTS exists (BL-032, Web Speech API), but server-side audio file generation for export is not implemented.
**Recommendation:** Upgrade to P2. The teacher described this as the single most time-saving feature ("I have had to record that audio myself"). Python TTS libraries (gTTS, pyttsx3) could generate MP3 files bundled into the QTI ZIP. Canvas supports audio in question/answer rich text.

### BL-032 stretch: Server-side TTS for exported audio
**Feedback:** Same as above -- teacher wants audio files that travel with the quiz export.
**Status:** PLANNED (GitHub #25, P3)
**Evidence:** Open issue. BL-064 is effectively the same ask.

### BL-008 stretch: Image upload from URL (not just file)
**Feedback:** Teacher mentioned wanting to insert images "from the web" (by URL) not just from local file upload. Referenced Canvas's ability to link images from web.
**Status:** PLANNED (GitHub #30, P3)
**Evidence:** Currently images are uploaded from local file only. Teacher's workflow includes finding images online and inserting them.
**Recommendation:** Low priority. The teacher can download and re-upload. Keep at P3.

---

## 4. NEW GAP Items

### GAP-1: Stimulus/passage-based question groups (NEW -- recommend BL-065)
**Feedback:** Teacher demonstrated "stimulus" questions in Canvas: one passage/image/diagram with 5-6 questions all referring to it. "Questions 8 through 13 are based on the image below." This is a new question format in Virginia SOL testing.
**Priority:** P2
**Rationale:** This is a distinct question *structure* (not just a type). One shared context with multiple sub-questions. The current data model treats each question independently. Supporting stimulus groups would require:
- A `question_group` or `stimulus` model linking questions
- Prompt engineering to generate grouped questions from one context
- Export support to render the shared context once, then list sub-questions
- QTI support for stimulus sections (Canvas supports this natively)
**Recommendation:** Create BL-065: "Stimulus/passage-based question groups." This is separate from BL-063's individual interactive question types.

### GAP-2: Multiple-answer / "select all that apply" question type (NEW -- recommend BL-066)
**Feedback:** Teacher showed "multiple answer" questions in Canvas and SOL practice tests -- students must select ALL correct answers from a list. This is distinct from multiple choice (one correct answer).
**Priority:** P2
**Rationale:** Current question types include MC (single correct), TF, fill-in-blank, short answer, matching, ordering. "Select all that apply" / multiple-answer is a common assessment format missing from the system. Canvas supports it natively. SOL tests use it.
**Recommendation:** Create BL-066: "Multiple-answer question type (select all that apply)." Requires changes to:
- Question data model (list of correct answers instead of single)
- Generator prompt to produce these
- Export formats to handle multiple correct answers
- QTI export to use `multiple_answers_question` type

### GAP-3: Cloze/inline-dropdown fill-in-blank (NEW -- recommend BL-067)
**Feedback:** Teacher showed a fill-in-blank question with MULTIPLE blanks in one sentence, each blank having its own dropdown with 3 options. "Photosynthesis is the process by which [blank] is used to make [blank]." This is different from the current single-blank-per-question with word bank.
**Priority:** P3
**Rationale:** This is a Canvas-native question type ("Fill in Multiple Blanks"). The current word_bank implementation handles a simpler case. Full cloze support would require:
- Data model: multiple blanks per question, each with its own option set
- Generator prompt: produce cloze-style questions
- QTI export: `fill_in_multiple_blanks_question` type
- PDF/DOCX export: render as word bank with per-blank options
**Recommendation:** Create BL-067: "Cloze / fill-in-multiple-blanks question type." Canvas calls this "Fill in Multiple Blanks." P3 because the current word bank partially addresses the need for printable quizzes, and this is primarily a Canvas-native feature.

---

## 5. Recommendations for Next Session

### Priority 1: Upgrade Canvas question types to P2
The teacher's core message was clear: **"I can create multiple choice myself. What I need is something for tech-assisted interactive questions."** The features that would save the most time are:
1. **TTS audio in QTI export** (BL-064) -- teacher currently manually records audio
2. **Stimulus/passage-based question groups** (GAP-1/BL-065) -- new SOL format
3. **Multiple-answer "select all"** (GAP-2/BL-066) -- common SOL format
4. **Canvas interactive types** (BL-063) -- hotspot, categorization

### Priority 2: Regeneration UX
Add loading indicator and timeout feedback for single-question regeneration. The teacher found the wait confusing.

### Priority 3: Verify existing fixes work end-to-end
The Session 16 fixes (topics field, content textarea, student-mode export, word bank, A/B/C/D lettering, difficulty labels, image upload CSRF) should be verified with the teacher in a follow-up session.

### Not Recommended
- **Full curriculum framework drill-down UI**: The two-field approach (standards + content textarea) matches the teacher's actual workflow of copy-pasting from the PDF. Building a full hierarchical browser of enduring understandings would be massive scope for limited additional value.
- **Lesson logging changes**: The teacher doesn't use this feature. Making it optional (already done) is sufficient. Don't invest further.

---

## Appendix: Feedback Item Index

| # | Feedback Item | Status | Reference |
|---|---------------|--------|-----------|
| F1 | Topics/content field on generate form | ADDRESSED | Session 16, BL-057 |
| F2 | Standards search broken | ADDRESSED | Session 16 |
| F3 | Quiz generated wrong topic | ADDRESSED | Session 16, BL-057 |
| F4 | Question types tied to Bloom's | ADDRESSED | Session 16, BL-061 |
| F5 | Fill-in-blank word bank | ADDRESSED | Session 16, BL-060 |
| F6 | Difficulty slider unclear | ADDRESSED | Session 16 |
| F7 | A/B/C/D lettering in exports | ADDRESSED | Session 16, BL-059 |
| F8 | Student-facing export mode | ADDRESSED | Session 16, BL-058 |
| F9 | Image upload broken | ADDRESSED | Session 16, BL-062 |
| F10 | Suggested image in export | ADDRESSED | Session 16, BL-058 |
| F11 | Cannot delete suggested image text | ADDRESSED | Via student_mode |
| F12 | Lesson logging extra work/privacy | ADDRESSED | Session 16 |
| F13 | Standards on class creation | ADDRESSED | Already optional |
| F14 | Specify content directly | ADDRESSED | Session 16, BL-057 |
| P1 | Regeneration speed | PARTIAL | Needs UX indicator |
| P2 | Inline dropdown per blank | PARTIAL | Word bank exists, not per-blank |
| P3 | Sub-standard granularity | PARTIAL | Content textarea covers workflow |
| BL-063 | Canvas interactive types | PLANNED | P3, recommend P2 |
| BL-064 | TTS audio in QTI export | PLANNED | P3, recommend P2 |
| BL-032s | Server-side TTS | PLANNED | GH #25, P3 |
| BL-008s | Image upload from URL | PLANNED | GH #30, P3 |
| GAP-1 | Stimulus question groups | NEW GAP | Recommend BL-065, P2 |
| GAP-2 | Multiple-answer "select all" | NEW GAP | Recommend BL-066, P2 |
| GAP-3 | Cloze/multi-blank fill-in | NEW GAP | Recommend BL-067, P3 |
