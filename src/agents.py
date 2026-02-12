import json
import os
import time
from typing import Any, Dict, List, Optional

from src.cognitive_frameworks import BLOOMS_LEVELS, DOK_LEVELS, get_framework
from src.cost_tracking import check_rate_limit, estimate_pipeline_cost
from src.database import Class, get_engine, get_session
from src.lesson_tracker import get_assumed_knowledge, get_recent_lessons
from src.llm_provider import get_provider


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
        print("Warning: qa_guidelines.txt not found.")
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
        class_context_section = ""
        lesson_logs = context.get("lesson_logs", [])
        assumed_knowledge = context.get("assumed_knowledge", {})
        if lesson_logs or assumed_knowledge:
            class_context_section = "**Class Context:**\n"
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

        # Build cognitive framework section
        cognitive_section = ""
        cognitive_framework = context.get("cognitive_framework")
        cognitive_distribution = context.get("cognitive_distribution")
        difficulty = context.get("difficulty", 3)
        if cognitive_framework:
            levels = get_framework(cognitive_framework)
            framework_label = "Bloom's Taxonomy" if cognitive_framework == "blooms" else "Webb's DOK"
            cognitive_section = f"**Cognitive Framework: {framework_label}**\n"
            cognitive_section += f"Difficulty Level: {difficulty}/5\n\n"
            if cognitive_distribution and levels:
                cognitive_section += "MANDATORY distribution by cognitive level (you MUST follow this exactly):\n"
                for lvl in levels:
                    num = lvl["number"]
                    entry = cognitive_distribution.get(str(num)) or cognitive_distribution.get(num)
                    if entry is None:
                        continue
                    if isinstance(entry, dict):
                        count = entry.get("count", 0)
                        types = entry.get("types", [])
                    else:
                        count = int(entry)
                        types = []
                    if count > 0:
                        if types and len(types) > 0:
                            # Compute exact per-type counts via round-robin
                            type_counts = {}
                            for i in range(count):
                                t = types[i % len(types)]
                                type_counts[t] = type_counts.get(t, 0) + 1
                            type_breakdown = ", ".join(f"{c}x {t}" for t, c in type_counts.items())
                            cognitive_section += (
                                f"- Level {num} ({lvl['name']}): {count} questions — REQUIRED types: {type_breakdown}\n"
                            )
                        else:
                            cognitive_section += f"- Level {num} ({lvl['name']}): {count} questions, type: any\n"
                cognitive_section += (
                    "\nThe question type distribution above is a HARD REQUIREMENT from the teacher, not a suggestion.\n"
                )
                cognitive_section += 'Each question MUST have a "type" field matching one of: mc, tf, fill_in_blank, short_answer, matching, essay\n'
            cognitive_section += "\nIMPORTANT: Tag every question with these fields:\n"
            cognitive_section += '- "cognitive_level": the level name (e.g., "Remember", "Analyze")\n'
            cognitive_section += f'- "cognitive_framework": "{cognitive_framework}"\n'
            cognitive_section += '- "cognitive_level_number": the level number (integer)\n'

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

                if "type" not in q:
                    # Try to infer type
                    if "options" in q:
                        # Check if multiple correct answers (list of indices or boolean flags?)
                        # The prompt example for MC has "correct_index": 2
                        # If the model produces "correct_indices", it might be MA.
                        if "correct_indices" in q:
                            q["type"] = "ma"
                        else:
                            q["type"] = "mc"
                    elif "is_true" in q:
                        q["type"] = "tf"
                    else:
                        # Default or skip? LetS skip to be safe, or default to essay/mc?
                        # If we return it, we must ensure downstream can handle it.
                        print(f'Warning: Question missing "type" and cannot infer: {q}')
                        # Attempt to default to mc if text exists
                        if "text" in q:
                            q["type"] = "mc"
                            if "options" not in q:
                                q["options"] = ["True", "False"]  # Fallback
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
    ) -> Dict[str, Any]:
        """Critique generated questions for quality, alignment, and appropriateness.

        Args:
            questions: List of question dictionaries to review.
            guidelines: QA guidelines text from qa_guidelines.txt.
            content_summary: Original lesson content summary for reference.
            class_context: Optional dictionary containing:
                - lesson_logs: Recent lessons taught to the class
                - assumed_knowledge: Student knowledge depth by topic

        Returns:
            Dictionary with critique result:
            - status: "APPROVED" if questions pass, "REJECTED" if revisions needed
            - feedback: None if approved, or feedback text explaining issues
        """
        prompt_text = self.base_prompt

        # Build cognitive validation section for critic
        cognitive_validation_section = ""
        if cognitive_config:
            framework = cognitive_config.get("cognitive_framework")
            distribution = cognitive_config.get("cognitive_distribution")
            difficulty = cognitive_config.get("difficulty", 3)
            if framework:
                levels = get_framework(framework)
                framework_label = "Bloom's Taxonomy" if framework == "blooms" else "Webb's DOK"
                cognitive_validation_section = f"\n**Cognitive Framework Validation ({framework_label}):**\n"
                cognitive_validation_section += "- Verify every question has cognitive_level, cognitive_framework, and cognitive_level_number fields\n"
                cognitive_validation_section += f"- Target difficulty: {difficulty}/5\n"
                if distribution and levels:
                    cognitive_validation_section += "- Verify distribution matches targets:\n"
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
                            cognitive_validation_section += f"  - Level {num} ({lvl['name']}): {count} questions\n"
                            if types:
                                type_counts = {}
                                for i in range(count):
                                    t = types[i % len(types)]
                                    type_counts[t] = type_counts.get(t, 0) + 1
                                type_req = ", ".join(f"{c}x {t}" for t, c in type_counts.items())
                                cognitive_validation_section += f"    REQUIRED question types: {type_req}\n"
                    cognitive_validation_section += "- CRITICAL: Verify each level's question types EXACTLY match the required counts above. If a level requires 1x mc, 1x tf, 1x fill_in_blank, there must be exactly those types. Flag any mismatch as a FAIL.\n"
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
        response_text = self.provider.generate([full_prompt], json_mode=False)

        if "APPROVED" in response_text:
            return {"status": "APPROVED", "feedback": None}

        return {"status": "REJECTED", "feedback": response_text}


class Orchestrator:
    def __init__(self, config: Dict[str, Any], web_mode: bool = False):
        """Initialize the Orchestrator to coordinate Generator and Critic agents.

        Args:
            config: Application configuration dictionary containing agent loop settings,
                   LLM provider config, and retry limits.
            web_mode: If True, skip interactive input() approval gate (for web UI).
        """
        self.config = config
        # Create provider once to avoid duplicate approval prompts
        provider = get_provider(config, web_mode=web_mode)
        self.generator = GeneratorAgent(config, provider=provider)
        self.critic = CriticAgent(config, provider=provider)
        self.max_retries = config.get("agent_loop", {}).get("max_retries", 3)
        self.last_metrics = None

    def run(self, context: Dict[str, Any]) -> tuple:
        """Run the generate-critique feedback loop until approval or max retries.

        Args:
            context: Generation context dictionary containing all parameters needed
                    by the Generator agent (content, images, standards, etc.).

        Returns:
            Tuple of (questions, metadata) where questions is a list of approved
            question dictionaries (or last draft if max retries reached, or empty
            list on failure), and metadata is a dict with prompt_summary, metrics,
            critic_history, provider, and model info.
        """
        feedback = None
        guidelines = get_qa_guidelines()
        critic_history = []

        # Initialize metrics tracking
        metrics = AgentMetrics()
        metrics.start()

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

        questions = []
        consecutive_errors = 0
        max_errors = 2  # Abort after this many consecutive transient failures

        for attempt in range(self.max_retries):
            print(f"   [Agent Loop] Attempt {attempt + 1}/{self.max_retries}...")

            # Generate with error handling
            try:
                questions = self.generator.generate(context, feedback)
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
                    return [], self._build_metadata(context, metrics, critic_history)
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
                    return [], self._build_metadata(context, metrics, critic_history)
                feedback = (
                    "Your previous response was empty or invalid JSON. Please generate a valid JSON list of questions."
                )
                continue

            # Reset error counter on successful generation
            consecutive_errors = 0

            # Critique with error handling
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
                critique_result = self.critic.critique(
                    questions,
                    guidelines,
                    content_summary,
                    class_context=class_context,
                    cognitive_config=cognitive_config,
                )
                metrics.critic_calls += 1
            except Exception as e:
                print(f"   [Agent Loop] Critic error: {e}. Skipping critique, returning draft.")
                metrics.stop()
                self.last_metrics = metrics
                return questions, self._build_metadata(context, metrics, critic_history)

            # Record critic feedback in history
            critic_history.append(
                {
                    "attempt": attempt + 1,
                    "status": critique_result["status"],
                    "feedback": critique_result.get("feedback"),
                }
            )

            if critique_result["status"] == "APPROVED":
                print("   [Agent Loop] Draft APPROVED.")
                metrics.stop()
                metrics.approved = True
                self.last_metrics = metrics
                return questions, self._build_metadata(context, metrics, critic_history)

            print(f"   [Agent Loop] Draft REJECTED. Feedback: {critique_result['feedback'][:100]}...")
            feedback = critique_result["feedback"]

        print("   [Agent Loop] Max retries reached. Returning last draft with warning.")
        metrics.stop()
        self.last_metrics = metrics
        return questions, self._build_metadata(context, metrics, critic_history)

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
            Dict with prompt_summary, metrics, critic_history, provider, and model.
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
        }

        return {
            "prompt_summary": prompt_summary,
            "metrics": metrics.report(),
            "critic_history": critic_history,
            "provider": self.config.get("llm", {}).get("provider", "unknown"),
            "model": self.config.get("llm", {}).get("model"),
        }


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
