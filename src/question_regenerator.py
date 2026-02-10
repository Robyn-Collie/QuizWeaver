"""
Single-question regeneration service for QuizWeaver.

Regenerates one question at a time using the LLM, preserving quiz context
and allowing teacher notes to guide the new question.
"""

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.database import Question, Quiz
from src.llm_provider import get_provider

logger = logging.getLogger(__name__)


def normalize_question_data(q: dict) -> dict:
    """Normalize a raw LLM question dict into our standard shape.

    Handles common key variations returned by different LLM providers.
    """
    # Map alternative text keys
    if "text" not in q:
        for key in ["question_text", "question", "stem", "prompt", "body"]:
            if key in q:
                q["text"] = q[key]
                break

    if "title" not in q and "question_title" in q:
        q["title"] = q["question_title"]

    if "correct_answer" not in q and "answer" in q:
        q["correct_answer"] = q["answer"]

    # Handle dict-style options -> list
    if isinstance(q.get("options"), dict):
        opts_map = q["options"]
        sorted_keys = sorted(opts_map.keys())
        q["options"] = [opts_map[k] for k in sorted_keys]
        if "correct_answer" in q:
            ans = str(q["correct_answer"]).upper()
            if ans in sorted_keys:
                q["correct_index"] = sorted_keys.index(ans)
    elif isinstance(q.get("options"), list):
        if "correct_index" not in q and "correct_answer" in q:
            ans = q["correct_answer"]
            if isinstance(ans, str) and len(ans) == 1 and ans.isalpha():
                idx = ord(ans.upper()) - ord("A")
                if 0 <= idx < len(q["options"]):
                    q["correct_index"] = idx
            elif ans in q["options"]:
                q["correct_index"] = q["options"].index(ans)

    # Infer type if missing
    if "type" not in q:
        if "options" in q:
            q["type"] = "ma" if "correct_indices" in q else "mc"
        elif "is_true" in q:
            q["type"] = "tf"
        elif "text" in q:
            q["type"] = "mc"

    return q


def regenerate_question(
    session: Session,
    question_id: int,
    teacher_notes: str,
    config: dict,
) -> Optional[Question]:
    """Regenerate a single question using the LLM.

    Args:
        session: SQLAlchemy session
        question_id: ID of the Question to regenerate
        teacher_notes: Optional guidance from the teacher
        config: Application config dict

    Returns:
        Updated Question ORM object, or None on failure
    """
    question = session.query(Question).filter_by(id=question_id).first()
    if not question:
        logger.warning("regenerate_question: question_id=%s not found", question_id)
        return None

    quiz = session.query(Quiz).filter_by(id=question.quiz_id).first()
    if not quiz:
        logger.warning("regenerate_question: quiz not found for question %s", question_id)
        return None

    # Parse existing data
    old_data = question.data
    if isinstance(old_data, str):
        old_data = json.loads(old_data)
    if not isinstance(old_data, dict):
        old_data = {}

    # Parse style profile for context
    style_profile = quiz.style_profile
    if isinstance(style_profile, str):
        try:
            style_profile = json.loads(style_profile)
        except (json.JSONDecodeError, ValueError):
            style_profile = {}
    if not isinstance(style_profile, dict):
        style_profile = {}

    grade_level = style_profile.get("grade_level", "7th Grade")
    q_type = question.question_type or old_data.get("type", "mc")

    notes_section = ""
    if teacher_notes:
        notes_section = f"\n**Teacher Notes:** {teacher_notes}\n"

    prompt = f"""Generate exactly ONE quiz question as a JSON object (not an array).
The question should be appropriate for {grade_level} students.
Question type: {q_type}
{notes_section}
Original question for reference (create a NEW different question, do not copy):
{json.dumps(old_data, indent=2)}

Return a JSON object with these fields:
- "text": question text
- "type": "{q_type}"
- "options": array of answer choices (for mc/ma)
- "correct_index": index of correct answer (for mc)
- "correct_answer": text of correct answer (for tf: "True" or "False")
- "points": {question.points or 1}

Return ONLY the JSON object, no markdown.
"""

    try:
        provider = get_provider(config, web_mode=True)
        response_text = provider.generate([prompt], json_mode=True)
    except Exception as e:
        logger.error("regenerate_question: LLM call failed: %s", e)
        return None

    # Parse response
    try:
        cleaned = response_text.strip()
        # Remove markdown code blocks if present
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        # Try to parse as single object first, then as array
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            if len(parsed) == 0:
                logger.warning("regenerate_question: empty array response")
                return None
            new_q = parsed[0]
        elif isinstance(parsed, dict):
            new_q = parsed
        else:
            logger.warning("regenerate_question: unexpected JSON type")
            return None

    except json.JSONDecodeError as e:
        logger.error("regenerate_question: JSON parse error: %s", e)
        return None

    new_q = normalize_question_data(new_q)

    # Update the question ORM object
    question.text = new_q.get("text", question.text)
    question.question_type = new_q.get("type", question.question_type)
    question.points = float(new_q.get("points", question.points or 1))

    # Preserve certain fields from old data (image_ref, cognitive fields)
    for keep_key in ("image_ref", "image_description", "cognitive_level",
                     "cognitive_framework", "cognitive_level_number"):
        if keep_key in old_data and keep_key not in new_q:
            new_q[keep_key] = old_data[keep_key]

    question.data = new_q
    flag_modified(question, "data")
    session.commit()

    return question
