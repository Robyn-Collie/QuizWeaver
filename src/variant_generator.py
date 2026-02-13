"""
Reading-level variant generator for QuizWeaver.

Generates reading-level variants of existing quizzes by rewriting questions
at a target reading level (ELL, Below Grade, On Grade, Advanced).
Uses MockLLMProvider by default for zero-cost development.
"""

import copy
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.database import Question, Quiz

logger = logging.getLogger(__name__)

READING_LEVELS = {
    "ell": "English Language Learner (simplified vocabulary, shorter sentences, visual cues)",
    "below_grade": "Below Grade Level (scaffolded, concrete examples, reduced complexity)",
    "on_grade": "On Grade Level (standard grade-appropriate language)",
    "advanced": "Advanced (higher-order thinking, complex vocabulary, extended reasoning)",
}


def _load_source_questions(session, quiz_id):
    """Load and serialize source quiz questions as dicts."""
    questions = session.query(Question).filter_by(quiz_id=quiz_id).order_by(Question.sort_order, Question.id).all()
    result = []
    for q in questions:
        data = q.data
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                data = {}
        if not isinstance(data, dict):
            data = {}

        q_dict = {
            "type": q.question_type or data.get("type", "mc"),
            "title": q.title or data.get("title", ""),
            "text": q.text or data.get("text", ""),
            "points": q.points or data.get("points", 5),
            "options": data.get("options", []),
            "correct_index": data.get("correct_index"),
            "correct_answer": data.get("correct_answer"),
            "image_ref": data.get("image_ref"),
            "is_true": data.get("is_true"),
            "expected_answer": data.get("expected_answer"),
            "acceptable_answers": data.get("acceptable_answers", []),
            "rubric_hint": data.get("rubric_hint", ""),
        }
        # Preserve cognitive fields
        for key in ("cognitive_level", "cognitive_framework", "cognitive_level_number"):
            if key in data:
                q_dict[key] = data[key]
        result.append(q_dict)
    return result


def _parse_variant_questions(response_text):
    """Parse JSON response into list of question dicts."""
    try:
        items = json.loads(response_text)
        if isinstance(items, list):
            return items
    except (json.JSONDecodeError, ValueError):
        pass

    import re

    match = re.search(r"\[.*\]", response_text, re.DOTALL)
    if match:
        try:
            items = json.loads(match.group())
            if isinstance(items, list):
                return items
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning("Failed to parse variant response")
    return None


def generate_variant(
    session: Session,
    quiz_id: int,
    reading_level: str,
    config: dict,
    title: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> Optional[Quiz]:
    """Generate a reading-level variant of an existing quiz.

    Args:
        session: SQLAlchemy session.
        quiz_id: ID of the source quiz to create a variant from.
        reading_level: Target reading level (ell, below_grade, on_grade, advanced).
        config: Application config dict (must include llm.provider).
        title: Optional title for the variant quiz.

    Returns:
        New Quiz ORM object with questions, or None on failure.
    """
    # Apply provider override if specified
    if provider_name:
        config = copy.deepcopy(config)
        config.setdefault("llm", {})["provider"] = provider_name

    if reading_level not in READING_LEVELS:
        logger.warning("generate_variant: invalid reading_level=%s", reading_level)
        return None

    # Load source quiz
    source_quiz = session.query(Quiz).filter_by(id=quiz_id).first()
    if source_quiz is None:
        logger.warning("generate_variant: quiz_id=%s not found", quiz_id)
        return None

    # Load source questions
    source_questions = _load_source_questions(session, quiz_id)
    if not source_questions:
        logger.warning("generate_variant: no questions for quiz_id=%s", quiz_id)
        return None

    # Build title
    if not title:
        level_label = reading_level.replace("_", " ").title()
        title = f"{source_quiz.title or 'Quiz'} ({level_label} Variant)"

    # Create variant quiz record
    variant = Quiz(
        title=title,
        class_id=source_quiz.class_id,
        parent_quiz_id=quiz_id,
        reading_level=reading_level,
        status="generating",
        style_profile=source_quiz.style_profile,
    )
    session.add(variant)
    session.commit()

    # Build prompt
    level_desc = READING_LEVELS[reading_level]
    prompt = (
        f"Rewrite the following quiz questions at the {level_desc} reading level. "
        f"Preserve the question structure, number of options, correct answers, and types. "
        f"Only modify the language, vocabulary, and scaffolding.\n\n"
        f"Questions:\n{json.dumps(source_questions, indent=2)}\n\n"
        f"Return a JSON array of rewritten question objects."
    )

    # Get LLM response
    try:
        provider_name = config.get("llm", {}).get("provider", "mock")
        if provider_name == "mock":
            from src.mock_responses import SCIENCE_TOPICS, get_variant_response

            context_lower = prompt.lower()
            keywords = [t for t in SCIENCE_TOPICS if t in context_lower]
            response_text = get_variant_response(source_questions, reading_level, keywords or None)
        else:
            from src.llm_provider import get_provider

            provider = get_provider(config, web_mode=True)
            response_text = provider.generate([prompt], json_mode=True)

    except Exception as e:
        logger.error("generate_variant: LLM call failed: %s", e)
        variant.status = "failed"
        session.commit()
        return None

    # Parse response
    new_questions = _parse_variant_questions(response_text)
    if not new_questions:
        variant.status = "failed"
        session.commit()
        return None

    # Create Question records
    for idx, q_data in enumerate(new_questions):
        q_type = q_data.get("type", "mc")
        text = q_data.get("text", "")
        points = q_data.get("points", 5)
        q_title = q_data.get("title", f"Question {idx + 1}")

        # Fall back to source question answers if the LLM omitted them
        if idx < len(source_questions):
            src = source_questions[idx]
            for answer_key in (
                "correct_answer", "correct_index", "is_true",
                "expected_answer", "acceptable_answers", "rubric_hint",
            ):
                if answer_key not in q_data and answer_key in src and src[answer_key]:
                    q_data[answer_key] = src[answer_key]

        # Build data dict (preserve all fields except text/title)
        data_dict = {}
        for key in (
            "type",
            "text",
            "options",
            "correct_index",
            "correct_answer",
            "is_true",
            "expected_answer",
            "acceptable_answers",
            "rubric_hint",
            "image_ref",
            "cognitive_level",
            "cognitive_framework",
            "cognitive_level_number",
        ):
            if key in q_data:
                data_dict[key] = q_data[key]
        data_dict["text"] = text
        data_dict["type"] = q_type

        question = Question(
            quiz_id=variant.id,
            question_type=q_type,
            title=q_title,
            text=text,
            points=points,
            sort_order=idx,
            data=json.dumps(data_dict),
        )
        session.add(question)

    variant.status = "generated"
    session.commit()
    session.refresh(variant)

    return variant
