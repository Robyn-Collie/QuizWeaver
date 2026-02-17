import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from src.cognitive_frameworks import BLOOMS_LEVELS, DOK_LEVELS, get_framework
from src.cost_tracking import check_rate_limit, estimate_cost, estimate_pipeline_cost, estimate_tokens
from src.critic_validation import pre_validate_questions
from src.database import Class, get_engine, get_session
from src.lesson_tracker import get_assumed_knowledge, get_recent_lessons
from src.llm_provider import get_api_audit_log, get_provider

logger = logging.getLogger(__name__)


class AgentMetrics:
    """Tracks performance metrics for a pipeline run."""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.generator_calls = 0
        self.critic_calls = 0
        self.errors = 0
        self.approved = False
        self.attempts = 0
        # New granular tracking
        self.pre_validation_failures = 0
        self.questions_approved = 0
        self.questions_rejected = 0
        # Token usage tracking
        self.input_tokens = 0
        self.output_tokens = 0

    def start(self):
        self.start_time = time.time()

    def stop(self):
        self.end_time = time.time()

    @property
    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    @property
    def total_calls(self):
        return self.generator_calls + self.critic_calls

    def report(self):
        return {
            "duration_seconds": round(self.duration, 3),
            "generator_calls": self.generator_calls,
            "critic_calls": self.critic_calls,
            "total_llm_calls": self.total_calls,
            "errors": self.errors,
            "attempts": self.attempts,
            "approved": self.approved,
            "pre_validation_failures": self.pre_validation_failures,
            "questions_approved": self.questions_approved,
            "questions_rejected": self.questions_rejected,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
        }


def load_prompt(filename: str) -> str:
    """Load a prompt file from the prompts/ directory.

    Args:
        filename: Name of the prompt file (e.g., "generator_prompt.txt").

    Returns:
        Prompt text content, or empty string if file not found.
    """
    path = os.path.join("prompts", filename)
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Prompt file {filename} not found.")
        return ""


def get_qa_guidelines() -> str:
    """Read QA guidelines from qa_guidelines.txt file.

    Returns:
        QA guidelines text content, or empty string if file not found.
    """
    try:
        with open("qa_guidelines.txt") as f:
            return f.read()
    except FileNotFoundError:
        logger.debug("qa_guidelines.txt not found, using empty guidelines")
        return ""


class GeneratorAgent:
    def __init__(self, config: Dict[str, Any], provider=None):
        """Initialize the Generator Agent.

        Args:
            config: Application configuration dictionary containing LLM provider settings
                   and prompt file paths.
            provider: Optional pre-created LLM provider instance. If None, creates one
                     via get_provider (which may trigger an approval prompt).
        """
        self.config = config
        self.provider = provider or get_provider(config)
        self.base_prompt = load_prompt("generator_prompt.txt")

    def generate(self, context: Dict[str, Any], feedback: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate quiz questions based on provided context and optional feedback.

        Args:
            context: Dictionary containing generation parameters including:
                - content_summary: Lesson content summary text
                - structured_data: Parsed structure from documents
                - retake_text: Original quiz text for style reference
                - num_questions: Number of questions to generate
                - images: List of image file paths
                - image_ratio: Target ratio of questions with images
                - grade_level: Target grade level (e.g., "7th Grade")
                - sol_standards: List of SOL standards to target
                - lesson_logs: Recent lesson logs for class context
                - assumed_knowledge: Student knowledge depth by topic
            feedback: Optional feedback from Critic agent to improve generation.

        Returns:
            List of question dictionaries with normalized fields including:
            - text: Question text
            - type: Question type ("mc", "ma", "tf", etc.)
            - options: List of answer options (for MC/MA)
            - correct_index: Index of correct answer
            - title: Optional question title
            - image_ref: Optional image reference
        """
        # Unpack context
        content_summary = context.get("content_summary", "")
        structured_data = context.get("structured_data", [])
        retake_text = context.get("retake_text", "")
        num_questions = context.get("num_questions", 10)
        images = context.get("images", [])
        image_ratio = context.get("image_ratio", 0.0)
        grade_level = context.get("grade_level", "7th Grade")
        sol_standards = context.get("sol_standards", [])

        sol_section = ""
        if sol_standards:
            sol_list = "\n".join([f"- {s}" for s in sol_standards])
            sol_section = f"**SOL Standards Focus:**\nYou must generate questions that specifically target the following SOL standards:\n{sol_list}\n"

        structured_content_text = ""
        if structured_data:
            structured_content_text = "**Structured Content Analysis (Headings, Diagrams, Layout):**\n"
            structured_content_text += json.dumps(structured_data, indent=2)
            structured_content_text += "\n---\n"

        qa_guidelines_content = get_qa_guidelines()  # Get content here
        feedback_section = ""
        if feedback:
            feedback_section = f"\n**CRITICAL FEEDBACK FROM PREVIOUS ATTEMPT:**\n{feedback}\nYou must revise your output to address this feedback.\n"

        # Build class context section
        class_context_section = _build_class_context_section(context)

        # Build cognitive framework section
        cognitive_section = _build_cognitive_section(context)

        # Prepare base prompt text
        prompt_text = self.base_prompt.replace("{grade_level}", str(grade_level))
        prompt_text = prompt_text.replace("{sol_section}", sol_section)
        prompt_text = prompt_text.replace("{class_context}", class_context_section)
        prompt_text = prompt_text.replace("{cognitive_section}", cognitive_section)

        full_prompt = f"""
{prompt_text}

**CRITICAL INSTRUCTIONS:**
{qa_guidelines_content}

{feedback_section}

**Task:**
Generate {num_questions} unique quiz questions.
Image Ratio Target: {int(image_ratio * 100)}%

**Image Policy:**
Do NOT include image URLs or links in your response — any URLs you generate will be fake.
Instead, if a question would benefit from a visual (diagram, chart, photo, etc.), include an
"image_description" field with a clear description of the ideal image, e.g.:
"image_description": "Simple diagram showing photosynthesis inputs (water, CO2, sunlight) and outputs (glucose, oxygen)"
The teacher will add or generate the actual image later. Do NOT include "image" or "image_url" fields.

---
**Content Summary:**
{content_summary}
---
{structured_content_text}
**Previous Test Questions (for style reference, do not copy):**
{retake_text}
---
"""

        prompt_parts = [full_prompt]

        # Add images
        for img_path in images:
            try:
                img_context = self.provider.prepare_image_context(img_path)
                prompt_parts.append(img_context)
                prompt_parts.append(f"Context for image: {os.path.basename(img_path)}")
            except Exception as e:
                print(f"Could not prepare image context for {img_path}: {e}")

        # Call LLM
        response_text = self.provider.generate(prompt_parts, json_mode=True)

        # Parse JSON
        try:
            cleaned_text = response_text.strip()
            # Remove markdown code blocks if present
            if cleaned_text.startswith("```"):
                lines = cleaned_text.splitlines()
                # Remove first line if it starts with ```
                if lines[0].startswith("```"):
                    lines = lines[1:]
                # Remove last line if it starts with ```
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                cleaned_text = "\n".join(lines)

            # Attempt to find list brackets
            start = cleaned_text.find("[")
            end = cleaned_text.rfind("]")
            if start != -1 and end != -1:
                cleaned_text = cleaned_text[start : end + 1]

            questions = json.loads(cleaned_text)

            if not isinstance(questions, list):
                print("Generator output is not a list.")
                return []

            valid_questions = []
            for q in questions:
                if not isinstance(q, dict):
                    continue

                # Normalization: Map keys if necessary
                if "text" not in q:
                    # Check for various common keys returned by LLMs
                    for key in ["question_text", "question", "stem", "prompt", "body"]:
                        if key in q:
                            q["text"] = q[key]
                            break

                # After all normalization attempts, if 'text' is still missing, log a warning
                if "text" not in q:
                    print(f"Warning: Question missing 'text' after normalization. Raw: {json.dumps(q)}")

                if "title" not in q and "question_title" in q:
                    q["title"] = q["question_title"]

                if "correct_answer" not in q and "answer" in q:
                    q["correct_answer"] = q["answer"]

                if "image_ref" not in q and "image_url" in q:
                    q["image_ref"] = q["image_url"]

                if "image_ref" not in q and "question_image" in q:  # New normalization
                    q["image_ref"] = q["question_image"]

                # Normalization: Handle Options (Dict -> List)
                if isinstance(q.get("options"), dict):
                    opts_map = q["options"]
                    sorted_keys = sorted(opts_map.keys())  # ["A", "B", "C", "D"]
                    q["options"] = [opts_map[k] for k in sorted_keys]

                    # Map correct_answer (e.g., "C") to index
                    if "correct_answer" in q:
                        ans = str(q["correct_answer"]).upper()
                        if ans in sorted_keys:
                            q["correct_index"] = sorted_keys.index(ans)

                # Normalization: Handle correct_answer if options is already a list
                elif isinstance(q.get("options"), list):
                    if "correct_index" not in q and "correct_answer" in q:
                        ans = q["correct_answer"]
                        # If answer is a string letter "A", "B"...
                        if isinstance(ans, str) and len(ans) == 1 and ans.isalpha():
                            idx = ord(ans.upper()) - ord("A")
                            if 0 <= idx < len(q["options"]):
                                q["correct_index"] = idx
                        # If answer is the text of the option
                        elif ans in q["options"]:
                            q["correct_index"] = q["options"].index(ans)

                # Normalize cognitive level fields
                if "cognitive_level" not in q:
                    for key in ["bloom_level", "blooms_level", "dok_level", "webb_level"]:
                        if key in q:
                            q["cognitive_level"] = q[key]
                            break
                if "cognitive_level" in q and "cognitive_framework" not in q:
                    # Infer framework from level name
                    level_name = str(q["cognitive_level"]).strip()
                    blooms_names = {lvl["name"].lower(): lvl for lvl in BLOOMS_LEVELS}
                    dok_names = {lvl["name"].lower(): lvl for lvl in DOK_LEVELS}
                    if level_name.lower() in blooms_names:
                        q["cognitive_framework"] = "blooms"
                        if "cognitive_level_number" not in q:
                            q["cognitive_level_number"] = blooms_names[level_name.lower()]["number"]
                    elif level_name.lower() in dok_names:
                        q["cognitive_framework"] = "dok"
                        if "cognitive_level_number" not in q:
                            q["cognitive_level_number"] = dok_names[level_name.lower()]["number"]

                # Map LLM-style question_type to internal type
                if "type" not in q and "question_type" in q:
                    _type_map = {
                        "multiple choice": "mc",
                        "multiple_choice": "mc",
                        "true/false": "tf",
                        "true false": "tf",
                        "short answer": "short_answer",
                        "short_answer": "short_answer",
                        "fill in the blank": "fill_in_blank",
                        "fill_in_blank": "fill_in_blank",
                        "matching": "matching",
                        "essay": "essay",
                        "ordering": "ordering",
                    }
                    mapped = _type_map.get(q["question_type"].lower().strip())
                    if mapped:
                        q["type"] = mapped

                if "type" not in q:
                    # Try to infer type from structure
                    if "options" in q:
                        if "correct_indices" in q:
                            q["type"] = "ma"
                        else:
                            q["type"] = "mc"
                    elif "is_true" in q:
                        q["type"] = "tf"
                    elif "text" in q:
                        q["type"] = "short_answer"

                if not q.get("points"):
                    q["points"] = 1
                valid_questions.append(q)

            return valid_questions

        except json.JSONDecodeError as e:
            print(f"Error parsing Generator response: {e}")
            print(f"Raw LLM Response: {response_text}")
            return []


class CriticAgent:
    def __init__(self, config: Dict[str, Any], provider=None):
        """Initialize the Critic Agent.

        Args:
            config: Application configuration dictionary containing LLM provider settings
                   and prompt file paths.
            provider: Optional pre-created LLM provider instance. If None, creates one
                     via get_provider (which may trigger an approval prompt).
        """
        self.config = config
        self.provider = provider or get_provider(config)
        self.base_prompt = load_prompt("critic_prompt.txt")

    def critique(
        self,
        questions: List[Dict[str, Any]],
        guidelines: str,
        content_summary: str,
        class_context: Optional[Dict[str, Any]] = None,
        cognitive_config: Optional[Dict[str, Any]] = None,
        teacher_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Critique generated questions for quality, alignment, and appropriateness.

        Returns a structured result with per-question verdicts.

        Args:
            questions: List of question dictionaries to review.
            guidelines: QA guidelines text from qa_guidelines.txt.
            content_summary: Original lesson content summary for reference.
            class_context: Optional dict with lesson_logs and assumed_knowledge.
            cognitive_config: Optional dict with cognitive_framework and distribution.
            teacher_config: Optional dict with allowed_types etc.

        Returns:
            Dictionary with:
            - status: "APPROVED" if all pass, "REJECTED" if any fail
            - feedback: Combined feedback text (None if all approved)
            - verdicts: List of per-question verdict dicts
            - passed_indices: List of indices that passed
            - failed_indices: List of indices that failed
            - overall_notes: General observations
        """
        prompt_text = self.base_prompt

        # Build cognitive validation section for critic
        cognitive_validation_section = ""
        if cognitive_config:
            cognitive_validation_section = _build_cognitive_validation_section(cognitive_config)
        prompt_text = prompt_text.replace("{cognitive_section}", cognitive_validation_section)

        questions_json = json.dumps(questions, indent=2)

        # Build class context section for critic
        class_context_section = ""
        if class_context:
            lesson_logs = class_context.get("lesson_logs", [])
            assumed_knowledge = class_context.get("assumed_knowledge", {})
            if lesson_logs or assumed_knowledge:
                class_context_section = "\n**Class Context:**\n"
                if lesson_logs:
                    class_context_section += "Recent lessons taught to this class:\n"
                    for log in lesson_logs[:10]:
                        topics = log.get("topics", [])
                        class_context_section += (
                            f"- {log.get('date', 'N/A')}: {', '.join(topics) if topics else 'general'}\n"
                        )
                if assumed_knowledge:
                    class_context_section += "\nAssumed student knowledge (topic: depth 1-5):\n"
                    for topic, data in assumed_knowledge.items():
                        depth = data.get("depth", 1)
                        label = {1: "introduced", 2: "reinforced", 3: "practiced", 4: "mastered", 5: "expert"}.get(
                            depth, "unknown"
                        )
                        class_context_section += f"- {topic}: depth {depth} ({label})\n"

        full_prompt = f"""
{prompt_text}

**QA Guidelines:**
{guidelines}

**Reference Content Summary:**
{content_summary}
{class_context_section}
**Quiz Draft:**
{questions_json}
"""
        response_text = self.provider.generate([full_prompt], json_mode=True)

        return _parse_critic_response(response_text, len(questions))


def _parse_critic_response(response_text: str, num_questions: int) -> Dict[str, Any]:
    """Parse the critic's response into a structured result.

    Tries structured JSON first, falls back to legacy ``"APPROVED" in text``
    detection for backward compatibility with providers that don't support
    JSON mode or return free-text.

    Args:
        response_text: Raw LLM response string.
        num_questions: Expected number of questions (for fallback).

    Returns:
        Structured dict with status, feedback, verdicts, indices, overall_notes.
    """
    # Try structured JSON parse
    try:
        cleaned = response_text.strip()
        # Strip markdown fences
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        # Find the JSON object
        brace_start = cleaned.find("{")
        brace_end = cleaned.rfind("}")
        if brace_start != -1 and brace_end != -1:
            cleaned = cleaned[brace_start : brace_end + 1]

        data = json.loads(cleaned)

        if isinstance(data, dict) and "questions" in data:
            verdicts = data["questions"]
            passed = []
            failed = []
            feedback_parts = []

            for v in verdicts:
                idx = v.get("index", 0)
                verdict = str(v.get("verdict", "")).upper()
                if verdict == "PASS":
                    passed.append(idx)
                else:
                    failed.append(idx)
                    issues = v.get("issues", [])
                    if issues:
                        feedback_parts.append(f"Q{idx}: {'; '.join(issues)}")
                    fact = v.get("fact_check", "PASS")
                    if fact in ("WARN", "FAIL"):
                        notes = v.get("fact_check_notes", "")
                        feedback_parts.append(f"Q{idx} fact-check {fact}: {notes}")

            overall = data.get("overall_notes", "")
            status = "APPROVED" if len(failed) == 0 else "REJECTED"
            feedback_text = "\n".join(feedback_parts) if feedback_parts else None

            return {
                "status": status,
                "feedback": feedback_text,
                "verdicts": verdicts,
                "passed_indices": passed,
                "failed_indices": failed,
                "overall_notes": overall,
            }

    except (json.JSONDecodeError, KeyError, TypeError):
        pass  # Fall through to legacy detection

    # Legacy fallback: plain-text "APPROVED" detection
    if "APPROVED" in response_text.upper():
        return {
            "status": "APPROVED",
            "feedback": None,
            "verdicts": [{"index": i, "verdict": "PASS", "issues": []} for i in range(num_questions)],
            "passed_indices": list(range(num_questions)),
            "failed_indices": [],
            "overall_notes": "",
        }

    return {
        "status": "REJECTED",
        "feedback": response_text,
        "verdicts": [{"index": i, "verdict": "FAIL", "issues": ["Rejected by critic"]} for i in range(num_questions)],
        "passed_indices": [],
        "failed_indices": list(range(num_questions)),
        "overall_notes": "",
    }


class Orchestrator:
    def __init__(self, config: Dict[str, Any], web_mode: bool = False):
        """Initialize the Orchestrator to coordinate Generator and Critic agents.

        Args:
            config: Application configuration dictionary containing agent loop settings,
                   LLM provider config, and retry limits.
            web_mode: If True, skip interactive input() approval gate (for web UI).
        """
        self.config = config
        # Create generator provider
        provider = get_provider(config, web_mode=web_mode)
        self.generator = GeneratorAgent(config, provider=provider)

        # Build critic config — may use a separate provider
        critic_config = _build_critic_config(config)
        if critic_config is config:
            # Same config, share the provider
            self.critic = CriticAgent(config, provider=provider)
        else:
            # Separate critic config — let CriticAgent create its own provider
            self.critic = CriticAgent(critic_config)

        self.max_retries = config.get("agent_loop", {}).get("max_retries", 3)
        self.last_metrics = None

    def run(self, context: Dict[str, Any]) -> tuple:
        """Run the generate-critique feedback loop with per-question granularity.

        New flow per attempt:
        1. Generate questions
        2. Pre-validate (deterministic) — remove structurally invalid questions
        3. LLM critique — get per-question verdicts
        4. Keep passed questions in accumulator
        5. If enough approved, stop early
        6. Otherwise regenerate only the still-needed count

        Args:
            context: Generation context dictionary.

        Returns:
            Tuple of (questions, metadata).
        """
        feedback = None
        guidelines = get_qa_guidelines()
        critic_history = []

        # Initialize metrics tracking
        metrics = AgentMetrics()
        metrics.start()

        # Extract teacher config for pre-validator
        teacher_config = _extract_teacher_config(context)
        target_count = max(context.get("num_questions", 10), 1)

        # Check rate limits before starting (skip for mock provider)
        provider_name = self.config.get("llm", {}).get("provider", "mock")
        if provider_name != "mock":
            is_exceeded, remaining_calls, remaining_budget = check_rate_limit(self.config)
            if is_exceeded:
                print("   [WARNING] Rate limit exceeded! No remaining API budget.")
                print("   Aborting pipeline. Check cost report with 'costs' command.")
                metrics.stop()
                self.last_metrics = metrics
                return [], self._build_metadata(context, metrics, critic_history)

            estimate = estimate_pipeline_cost(self.config, self.max_retries)
            if estimate["estimated_max_cost"] > 0:
                print(
                    f"   [Cost] Estimated max cost: ${estimate['estimated_max_cost']:.4f} "
                    f"({estimate['max_calls']} calls, {estimate['model']})"
                )
                if remaining_budget < estimate["estimated_max_cost"]:
                    print(
                        f"   [WARNING] Remaining budget (${remaining_budget:.4f}) may not "
                        f"cover worst-case cost (${estimate['estimated_max_cost']:.4f})"
                    )

        approved_questions: List[Dict[str, Any]] = []
        consecutive_errors = 0
        max_errors = 2  # Abort after this many consecutive transient failures

        for attempt in range(self.max_retries):
            still_needed = max(target_count - len(approved_questions), 0)
            if still_needed == 0:
                break

            print(f"   [Agent Loop] Attempt {attempt + 1}/{self.max_retries} (need {still_needed} more questions)...")

            # Update context for partial regeneration
            gen_context = dict(context)
            gen_context["num_questions"] = still_needed

            # Generate with error handling
            try:
                audit_before = len(get_api_audit_log())
                questions = self.generator.generate(gen_context, feedback)
                _accumulate_tokens(metrics, audit_before)
                metrics.generator_calls += 1
                metrics.attempts += 1
            except Exception as e:
                consecutive_errors += 1
                metrics.errors += 1
                metrics.generator_calls += 1
                metrics.attempts += 1
                print(f"   [Agent Loop] Generator error: {e}")
                if consecutive_errors >= max_errors:
                    print("   [Agent Loop] Too many consecutive errors. Aborting.")
                    metrics.stop()
                    self.last_metrics = metrics
                    # Return whatever we have so far
                    final = approved_questions if approved_questions else []
                    return final, self._build_metadata(context, metrics, critic_history)
                # Brief pause before retry (skip in mock mode)
                if provider_name != "mock":
                    time.sleep(min(2**consecutive_errors, 10))
                feedback = "Your previous response caused an error. Please try again with valid output."
                continue

            if not questions:
                consecutive_errors += 1
                print("   [Agent Loop] Generator failed to produce questions. Retrying...")
                if consecutive_errors >= max_errors:
                    print("   [Agent Loop] Too many consecutive failures. Aborting.")
                    metrics.stop()
                    self.last_metrics = metrics
                    final = approved_questions if approved_questions else []
                    return final, self._build_metadata(context, metrics, critic_history)
                feedback = (
                    "Your previous response was empty or invalid JSON. Please generate a valid JSON list of questions."
                )
                continue

            # Reset error counter on successful generation
            consecutive_errors = 0

            # --- Step 2: Pre-validate (deterministic) ---
            pre_results = pre_validate_questions(questions, teacher_config)
            structurally_valid = []
            pre_fail_feedback = []
            for r in pre_results:
                if r["passed"]:
                    structurally_valid.append(questions[r["index"]])
                else:
                    metrics.pre_validation_failures += 1
                    pre_fail_feedback.append(f"Q{r['index']}: {'; '.join(r['issues'])}")

            if pre_fail_feedback:
                print(f"   [Agent Loop] Pre-validation removed {len(pre_fail_feedback)} question(s)")

            if not structurally_valid:
                feedback = (
                    "All questions failed structural validation:\n"
                    + "\n".join(pre_fail_feedback)
                    + "\nPlease fix and regenerate."
                )
                continue

            # --- Step 3: LLM critique ---
            print("   [Agent Loop] Critiquing draft...")
            content_summary = context.get("content_summary", "")
            class_context = {
                "lesson_logs": context.get("lesson_logs", []),
                "assumed_knowledge": context.get("assumed_knowledge", {}),
            }
            cognitive_config = {
                "cognitive_framework": context.get("cognitive_framework"),
                "cognitive_distribution": context.get("cognitive_distribution"),
                "difficulty": context.get("difficulty", 3),
            }

            try:
                audit_before = len(get_api_audit_log())
                critique_result = self.critic.critique(
                    structurally_valid,
                    guidelines,
                    content_summary,
                    class_context=class_context,
                    cognitive_config=cognitive_config,
                    teacher_config=teacher_config,
                )
                _accumulate_tokens(metrics, audit_before)
                metrics.critic_calls += 1
            except Exception as e:
                print(f"   [Agent Loop] Critic error: {e}. Accepting pre-validated draft.")
                # On critic failure, accept all structurally-valid questions
                approved_questions.extend(structurally_valid)
                metrics.questions_approved += len(structurally_valid)
                metrics.stop()
                self.last_metrics = metrics
                final = approved_questions[:target_count]
                return final, self._build_metadata(context, metrics, critic_history)

            # --- Step 4: Collect passed questions ---
            passed_indices = critique_result.get("passed_indices", [])
            failed_indices = critique_result.get("failed_indices", [])

            for idx in passed_indices:
                if idx < len(structurally_valid):
                    approved_questions.append(structurally_valid[idx])
                    metrics.questions_approved += 1
            metrics.questions_rejected += len(failed_indices)

            # Record critic feedback in history
            critic_history.append(
                {
                    "attempt": attempt + 1,
                    "status": critique_result["status"],
                    "feedback": critique_result.get("feedback"),
                    "passed_count": len(passed_indices),
                    "failed_count": len(failed_indices),
                    "verdicts": critique_result.get("verdicts", []),
                }
            )

            if len(approved_questions) >= target_count:
                print(f"   [Agent Loop] Collected {len(approved_questions)} approved questions. Done.")
                metrics.stop()
                metrics.approved = True
                self.last_metrics = metrics
                final = approved_questions[:target_count]
                return final, self._build_metadata(context, metrics, critic_history)

            # Build specific feedback for next attempt
            feedback_parts = []
            if critique_result.get("feedback"):
                feedback_parts.append(critique_result["feedback"])
            if pre_fail_feedback:
                feedback_parts.append("Pre-validation failures:\n" + "\n".join(pre_fail_feedback))
            feedback_parts.append(
                f"You need to generate {target_count - len(approved_questions)} more questions. "
                f"Previously approved questions are kept; generate only NEW replacement questions."
            )
            feedback = "\n\n".join(feedback_parts)

            print(
                f"   [Agent Loop] {len(passed_indices)} passed, {len(failed_indices)} failed. "
                f"Total approved: {len(approved_questions)}/{target_count}"
            )

        # Max retries reached
        if approved_questions:
            print(f"   [Agent Loop] Max retries reached. Returning {len(approved_questions)} approved questions.")
        else:
            print("   [Agent Loop] Max retries reached. Returning last draft with warning.")

        metrics.stop()
        metrics.approved = len(approved_questions) >= target_count
        self.last_metrics = metrics
        final = approved_questions[:target_count] if approved_questions else questions if "questions" in dir() else []
        return final, self._build_metadata(context, metrics, critic_history)

    def _build_metadata(
        self,
        context: Dict[str, Any],
        metrics: AgentMetrics,
        critic_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build the generation metadata dict for Glass Box transparency.

        Args:
            context: The generation context dict.
            metrics: The AgentMetrics instance with pipeline stats.
            critic_history: List of critic feedback entries.

        Returns:
            Dict with prompt_summary, metrics, critic_history, provider, model,
            and optional critic_provider / critic_model.
        """
        # Extract topics from lesson logs if available
        topics_from_lessons = []
        for log in context.get("lesson_logs", []):
            topics_from_lessons.extend(log.get("topics", []))
        # Deduplicate while preserving order
        seen = set()
        unique_topics = []
        for t in topics_from_lessons:
            if t not in seen:
                seen.add(t)
                unique_topics.append(t)

        prompt_summary = {
            "grade_level": context.get("grade_level"),
            "num_questions": context.get("num_questions"),
            "standards": context.get("sol_standards", []),
            "cognitive_framework": context.get("cognitive_framework"),
            "difficulty": context.get("difficulty"),
            "topics_from_lessons": unique_topics[:20],
            "user_provided_content": context.get("user_provided_content", False),
            "question_types": context.get("question_types", []),
        }

        provider_name = self.config.get("llm", {}).get("provider", "unknown")
        model_name = self.config.get("llm", {}).get("model")

        # Calculate estimated cost from token usage
        report = metrics.report()
        estimated_cost = 0.0
        if model_name and report["total_tokens"] > 0:
            estimated_cost = estimate_cost(model_name, report["input_tokens"], report["output_tokens"])
        elif report["total_tokens"] > 0:
            # Fallback: use default pricing
            estimated_cost = estimate_cost("unknown", report["input_tokens"], report["output_tokens"])

        token_usage = {
            "input_tokens": report["input_tokens"],
            "output_tokens": report["output_tokens"],
            "total_tokens": report["total_tokens"],
            "estimated_cost": round(estimated_cost, 6),
            "is_mock": provider_name == "mock",
        }

        result = {
            "prompt_summary": prompt_summary,
            "metrics": report,
            "critic_history": critic_history,
            "provider": provider_name,
            "model": model_name,
            "token_usage": token_usage,
        }

        # Add critic provider info if it differs
        critic_cfg = self.config.get("llm", {}).get("critic", {})
        if critic_cfg and critic_cfg.get("provider"):
            result["critic_provider"] = critic_cfg["provider"]
            result["critic_model"] = critic_cfg.get("model_name")

        return result


# ------------------------------------------------------------------
# Helper functions (extracted from class methods for reuse)
# ------------------------------------------------------------------


def _accumulate_tokens(metrics: AgentMetrics, audit_log_len_before: int) -> None:
    """Sum token counts from new audit log entries added since *audit_log_len_before*.

    For mock providers the audit log is empty, so this estimates tokens from
    prompt/response character counts instead.
    """
    audit_log = get_api_audit_log()
    new_entries = audit_log[audit_log_len_before:]
    for entry in new_entries:
        in_tok = entry.get("input_tokens", 0)
        out_tok = entry.get("output_tokens", 0)
        if in_tok or out_tok:
            metrics.input_tokens += in_tok
            metrics.output_tokens += out_tok
        else:
            # Estimate from character counts when provider doesn't report tokens
            prompt_chars = len(entry.get("prompt_preview", ""))
            response_chars = entry.get("response_char_count", 0)
            metrics.input_tokens += estimate_tokens("x" * prompt_chars)
            metrics.output_tokens += estimate_tokens("x" * response_chars)


def _build_class_context_section(context: Dict[str, Any]) -> str:
    """Build the class context section for generator/critic prompts.

    If the teacher provided explicit content (topics or content_text), that
    takes priority. Lesson logs are included as supplementary context but
    the prompt makes clear the user-provided content is authoritative.
    """
    parts = []

    # User-provided content takes priority
    user_provided = context.get("user_provided_content", False)
    content_summary = context.get("content_summary", "")
    if user_provided and content_summary:
        parts.append(
            "**Teacher-Provided Content (PRIMARY -- generate questions ONLY about this):**\n" + content_summary
        )

    lesson_logs = context.get("lesson_logs", [])
    assumed_knowledge = context.get("assumed_knowledge", {})
    if lesson_logs or assumed_knowledge:
        if user_provided:
            parts.append(
                "**Supplementary Class Context (for background only, do NOT go beyond the teacher's content above):**"
            )
        else:
            parts.append("**Class Context:**")
        if lesson_logs:
            parts.append("Recent lessons taught to this class:")
            for log in lesson_logs[:10]:
                topics = log.get("topics", [])
                parts.append(f"- {log.get('date', 'N/A')}: {', '.join(topics) if topics else 'general'}")
        if assumed_knowledge:
            parts.append("\nAssumed student knowledge (topic: depth 1-5):")
            for topic, data in assumed_knowledge.items():
                depth = data.get("depth", 1)
                label = {1: "introduced", 2: "reinforced", 3: "practiced", 4: "mastered", 5: "expert"}.get(
                    depth, "unknown"
                )
                parts.append(f"- {topic}: depth {depth} ({label})")

    return "\n".join(parts)


def _build_cognitive_section(context: Dict[str, Any]) -> str:
    """Build the cognitive framework section for the generator prompt."""
    cognitive_section = ""
    cognitive_framework = context.get("cognitive_framework")
    cognitive_distribution = context.get("cognitive_distribution")
    difficulty = context.get("difficulty", 3)
    question_types = context.get("question_types", [])

    # Question types section (independent of cognitive framework)
    if question_types:
        type_labels = {
            "mc": "Multiple Choice",
            "tf": "True/False",
            "fill_in_blank": "Fill in the Blank",
            "short_answer": "Short Answer",
            "matching": "Matching",
            "ordering": "Ordering",
            "essay": "Essay",
        }
        type_names = [type_labels.get(t, t) for t in question_types]
        cognitive_section += f"**Allowed Question Types:** {', '.join(type_names)}\n"
        cognitive_section += f"Use ONLY these question types: {', '.join(question_types)}\n"
        cognitive_section += "Distribute them across questions as appropriate for the content.\n\n"

    if cognitive_framework:
        levels = get_framework(cognitive_framework)
        framework_label = "Bloom's Taxonomy" if cognitive_framework == "blooms" else "Webb's DOK"
        cognitive_section += f"**Cognitive Framework: {framework_label}**\n"
        cognitive_section += f"Difficulty Level: {difficulty}/5\n\n"
        if cognitive_distribution and levels:
            cognitive_section += "MANDATORY distribution by cognitive level (you MUST follow this exactly):\n"
            for lvl in levels:
                num = lvl["number"]
                entry = cognitive_distribution.get(str(num)) or cognitive_distribution.get(num)
                if entry is None:
                    continue
                count = entry.get("count", 0) if isinstance(entry, dict) else int(entry)
                if count > 0:
                    cognitive_section += f"- Level {num} ({lvl['name']}): {count} questions\n"
        cognitive_section += "\nIMPORTANT: Tag every question with these fields:\n"
        cognitive_section += '- "cognitive_level": the level name (e.g., "Remember", "Analyze")\n'
        cognitive_section += f'- "cognitive_framework": "{cognitive_framework}"\n'
        cognitive_section += '- "cognitive_level_number": the level number (integer)\n'
    return cognitive_section


def _build_cognitive_validation_section(cognitive_config: Dict[str, Any]) -> str:
    """Build the cognitive validation section for the critic prompt."""
    section = ""
    framework = cognitive_config.get("cognitive_framework")
    distribution = cognitive_config.get("cognitive_distribution")
    difficulty = cognitive_config.get("difficulty", 3)
    if framework:
        levels = get_framework(framework)
        framework_label = "Bloom's Taxonomy" if framework == "blooms" else "Webb's DOK"
        section = f"\n**Cognitive Framework Validation ({framework_label}):**\n"
        section += (
            "- Verify every question has cognitive_level, cognitive_framework, and cognitive_level_number fields\n"
        )
        section += f"- Target difficulty: {difficulty}/5\n"
        if distribution and levels:
            section += "- Verify distribution matches targets:\n"
            for lvl in levels:
                num = lvl["number"]
                entry = distribution.get(str(num)) or distribution.get(num)
                if entry is None:
                    continue
                if isinstance(entry, dict):
                    count = entry.get("count", 0)
                    types = entry.get("types", [])
                else:
                    count = int(entry)
                    types = []
                if count > 0:
                    section += f"  - Level {num} ({lvl['name']}): {count} questions\n"
                    if types:
                        type_counts = {}
                        for i in range(count):
                            t = types[i % len(types)]
                            type_counts[t] = type_counts.get(t, 0) + 1
                        type_req = ", ".join(f"{c}x {t}" for t, c in type_counts.items())
                        section += f"    REQUIRED question types: {type_req}\n"
            section += "- CRITICAL: Verify each level's question types EXACTLY match the required counts above. If a level requires 1x mc, 1x tf, 1x fill_in_blank, there must be exactly those types. Flag any mismatch as a FAIL.\n"
    return section


def _build_critic_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build a config dict for the critic agent.

    If ``config["llm"]["critic"]["provider"]`` is set, returns a new config
    dict with critic-specific LLM settings.  Otherwise returns the same
    config object (shared provider).
    """
    critic_section = config.get("llm", {}).get("critic", {})
    if not critic_section:
        return config
    critic_provider = critic_section.get("provider")
    if not critic_provider:
        return config

    # Build a separate config for the critic
    import copy

    critic_config = copy.deepcopy(config)
    critic_config["llm"]["provider"] = critic_provider
    if critic_section.get("model_name"):
        critic_config["llm"]["model"] = critic_section["model_name"]
    return critic_config


def _extract_teacher_config(context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract teacher configuration from the generation context.

    Pulls ``allowed_types`` from the context's question_types list (independent
    of cognitive distribution), falling back to per-level types from the
    cognitive distribution for backward compatibility.
    """
    # Prefer the independent question_types list
    question_types = context.get("question_types")
    if question_types:
        return {"allowed_types": list(question_types)}

    # Backward compat: pull from cognitive distribution if per-level types exist
    distribution = context.get("cognitive_distribution")
    if not distribution:
        return None

    allowed = set()
    for _key, entry in distribution.items():
        if isinstance(entry, dict):
            types = entry.get("types", [])
            for t in types:
                allowed.add(t)

    if allowed:
        return {"allowed_types": list(allowed)}
    return None


def run_agentic_pipeline(config, context, class_id=None, web_mode=False):
    """Run the agentic quiz generation pipeline with optional class context enrichment.

    Args:
        config: Application configuration dictionary.
        context: Generation context dictionary with content, images, and parameters.
        class_id: Optional class ID to load recent lessons and assumed knowledge for.
        web_mode: If True, skip interactive input() approval gate (for web UI).

    Returns:
        Tuple of (questions, metadata) from the Orchestrator.
    """
    # Enrich context with class data if class_id provided
    if class_id is not None:
        try:
            db_path = config.get("paths", {}).get("database_file", "quiz_warehouse.db")
            engine = get_engine(db_path)
            session = get_session(engine)

            # Load recent lessons
            recent = get_recent_lessons(session, class_id, days=14)
            lesson_logs = []
            for log in recent:
                import json as _json

                topics = _json.loads(log.topics) if isinstance(log.topics, str) else (log.topics or [])
                lesson_logs.append(
                    {
                        "date": str(log.date),
                        "topics": topics,
                        "notes": log.notes,
                    }
                )
            context["lesson_logs"] = lesson_logs

            # Load assumed knowledge
            knowledge = get_assumed_knowledge(session, class_id)
            context["assumed_knowledge"] = knowledge

            # Load class config
            class_obj = session.query(Class).filter_by(id=class_id).first()
            if class_obj:
                context["class_config"] = {
                    "name": class_obj.name,
                    "grade_level": class_obj.grade_level,
                    "subject": class_obj.subject,
                    "standards": class_obj.standards,
                }

            session.close()
        except Exception as e:
            print(f"Warning: Could not load class context: {e}")

    orch = Orchestrator(config, web_mode=web_mode)
    return orch.run(context)
