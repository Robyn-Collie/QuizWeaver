# Pedagogical Evaluation Rubric

**Version:** 1.0
**Status:** In Draft

---

## 1. Purpose

This document defines the criteria for evaluating the pedagogical quality of AI-generated quizzes. It serves as the formal specification for the **Critic Agent**, transforming subjective "quality" into a set of measurable, enforceable rules. The goal is to ensure every generated assessment is fair, accurate, and educationally valuable.

---

## 2. Evaluation Criteria

| **Category** | **Criteria** | **Enforcement Rule (for Critic Agent)** |
| :--- | :--- | :--- |
| **1. Curriculum Alignment** | **1.1 Standard Adherence:** All questions must directly map to the provided `Lesson Context` and any specified `SOL Standards`. | **REJECT** if a question introduces external information or fails to address a specified standard. |
| | **1.2 Content Accuracy:** All information presented in the question stem and the correct answer must be factually correct according to the `Lesson Context`. | **REJECT** if any factual inaccuracies are detected. |
| | | |
| **2. Question Quality** | **2.1 Clarity & Unambiguity:** The question (stem) must be written in clear, simple language, free of grammatical errors, and should pose a single, focused problem. | **REJECT** for convoluted phrasing, typos, or questions that ask multiple things at once. |
| | **2.2 Grade Level Appropriateness:** Vocabulary and sentence structure must be suitable for the specified `grade_level`. | **REJECT** if language is overly complex (e.g., college-level vocabulary) or overly simplistic for the target grade. |
| | **2.3 Plausible Distractors:** For multiple-choice questions, incorrect answers (distractors) must be plausible yet clearly wrong based on the context. They should represent common misconceptions. | **REJECT** if distractors are nonsensical, obviously wrong, or tricky. All options should be homogenous in structure. |
| | **2.4 No "Fill-in-the-Blank":** The application explicitly forbids "fill-in-the-blank" or "cloze" style questions. | **REJECT** if the `type` is `fib` or if the question text contains "____". |
| | | |
| **3. Structural Integrity** | **3.1 Style Profile Adherence:** The generated quiz must match the target `Style Profile` in terms of question count, type distribution (e.g., % MC vs. % TF), and image ratio. | **REJECT** if the number of questions or the ratio of question types deviates significantly from the profile. |
| | **3.2 Image Relevance:** If a question includes an image, the image must be directly relevant and necessary for answering the question. | **REJECT** if an image is purely decorative or irrelevant to the problem being posed. |
| | | |
| **4. Fairness & Bias** | **4.1 Neutral Language:** Questions must be free of cultural, gender, or any other form of bias. | **REJECT** if any biased, stereotypical, or non-inclusive language is detected. |

---

## 3. Critic Agent Implementation

The `Critic Agent` will receive the generated quiz (in JSON format) and the above rubric as its primary context. Its system prompt will instruct it to act as a meticulous QA inspector, and its sole task is to return either:
*   **"APPROVED"** if all criteria are met.
*   **"REJECTED:"** followed by a list of specific violations, referencing the rubric categories (e.g., "REJECTED: Violation 2.3 - Distractors are not plausible; Violation 3.1 - Question count does not match Style Profile.").

This formal rubric ensures a consistent and defensible quality assurance process.
