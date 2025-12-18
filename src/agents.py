import os
import json
from typing import Dict, List, Any, Optional
from src.llm_provider import get_provider


def load_prompt(filename: str) -> str:
    """Helper to load a prompt from the prompts/ directory."""
    path = os.path.join("prompts", filename)
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Prompt file {filename} not found.")
        return ""


def get_qa_guidelines() -> str:
    """Reads the QA guidelines from the specified file."""
    try:
        with open("qa_guidelines.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        print("Warning: qa_guidelines.txt not found.")
        return ""


class GeneratorAgent:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = get_provider(config)
        self.base_prompt = load_prompt("generator_prompt.txt")

    def generate(
        self, context: Dict[str, Any], feedback: Optional[str] = None
    ) -> List[Dict[str, Any]]:
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
            structured_content_text = (
                "**Structured Content Analysis (Headings, Diagrams, Layout):**\n"
            )
            structured_content_text += json.dumps(structured_data, indent=2)
            structured_content_text += "\n---\n"

        qa_guidelines_content = get_qa_guidelines()  # Get content here
        feedback_section = ""
        if feedback:
            feedback_section = f"\n**CRITICAL FEEDBACK FROM PREVIOUS ATTEMPT:**\n{feedback}\nYou must revise your output to address this feedback.\n"

        # Prepare base prompt text
        prompt_text = self.base_prompt.replace("{grade_level}", str(grade_level))
        prompt_text = prompt_text.replace("{sol_section}", sol_section)

        full_prompt = f"""
{prompt_text}

**CRITICAL INSTRUCTIONS:**
{qa_guidelines_content}

{feedback_section}

**Task:**
Generate {num_questions} unique quiz questions.
Image Ratio Target: {int(image_ratio * 100)}%

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
                    if "question_text" in q:
                        q["text"] = q["question_text"]
                    elif "question" in q:
                        q["text"] = q["question"]

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

        except json.JSONDecodeError:
            print(f"Error parsing Generator response: {response_text}")
            return []


class CriticAgent:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = get_provider(config)
        self.base_prompt = load_prompt("critic_prompt.txt")

    def critique(
        self,
        questions: List[Dict[str, Any]],
        guidelines: str,
        content_summary: str,
    ) -> Dict[str, Any]:
        prompt_text = self.base_prompt

        questions_json = json.dumps(questions, indent=2)

        full_prompt = f"""
{prompt_text}

**QA Guidelines:**
{guidelines}

**Reference Content Summary:**
{content_summary}

**Quiz Draft:**
{questions_json}
"""
        response_text = self.provider.generate([full_prompt], json_mode=False)

        if "APPROVED" in response_text:
            return {"status": "APPROVED", "feedback": None}

        return {"status": "REJECTED", "feedback": response_text}


class Orchestrator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.generator = GeneratorAgent(config)
        self.critic = CriticAgent(config)
        self.max_retries = config.get("agent_loop", {}).get("max_retries", 3)

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        feedback = None
        guidelines = get_qa_guidelines()

        for attempt in range(self.max_retries):
            print(f"   [Agent Loop] Attempt {attempt + 1}/{self.max_retries}...")
            questions = self.generator.generate(context, feedback)

            if not questions:
                print(
                    "   [Agent Loop] Generator failed to produce questions. Retrying..."
                )
                feedback = "Your previous response was empty or invalid JSON. Please generate a valid JSON list of questions."
                continue

            print("   [Agent Loop] Critiquing draft...")
            content_summary = context.get("content_summary", "")
            critique_result = self.critic.critique(
                questions, guidelines, content_summary
            )

            if critique_result["status"] == "APPROVED":
                print("   [Agent Loop] Draft APPROVED.")
                return questions

            print(
                f"   [Agent Loop] Draft REJECTED. Feedback: {critique_result["feedback"][:100]}..."
            )
            feedback = critique_result["feedback"]

        print("   [Agent Loop] Max retries reached. Returning last draft with warning.")
        return questions


def run_agentic_pipeline(config, context):
    orch = Orchestrator(config)
    return orch.run(context)
