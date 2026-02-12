"""
Quiz template export/import for QuizWeaver.

Exports quizzes as shareable JSON templates (stripping private/class-specific data)
and imports templates to create new quizzes in any class.

Template JSON includes question content, cognitive levels, and standards but
excludes student performance data, class context, teacher identity, and timestamps.
"""

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.database import Question, Quiz

logger = logging.getLogger(__name__)

TEMPLATE_VERSION = "1.0"


def export_quiz_template(session: Session, quiz_id: int) -> Optional[Dict[str, Any]]:
    """Export a quiz as a shareable JSON template.

    Includes: question text, options, correct answer, cognitive level,
    standards, difficulty, question_type.
    Excludes: student performance data, class-specific context, teacher
    identity, quiz ID, timestamps.

    Args:
        session: SQLAlchemy session.
        quiz_id: ID of the quiz to export.

    Returns:
        Template dict ready for JSON serialization, or None if quiz not found.
    """
    quiz = session.query(Quiz).filter_by(id=quiz_id).first()
    if not quiz:
        logger.warning("export_quiz_template: quiz_id=%s not found", quiz_id)
        return None

    questions = session.query(Question).filter_by(quiz_id=quiz_id).order_by(Question.sort_order, Question.id).all()

    # Parse style profile for metadata
    style_profile = quiz.style_profile
    if isinstance(style_profile, str):
        try:
            style_profile = json.loads(style_profile)
        except (json.JSONDecodeError, ValueError):
            style_profile = {}
    if not isinstance(style_profile, dict):
        style_profile = {}

    # Build question list
    template_questions = []
    for q in questions:
        data = q.data
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                data = {}
        if not isinstance(data, dict):
            data = {}

        tq = _build_template_question(q, data)
        template_questions.append(tq)

    # Build template
    template = {
        "template_version": TEMPLATE_VERSION,
        "title": quiz.title or "Untitled Quiz",
        "subject": style_profile.get("subject", ""),
        "grade_level": style_profile.get("grade_level", ""),
        "standards": style_profile.get("sol_standards", []),
        "cognitive_framework": style_profile.get("cognitive_framework", ""),
        "question_count": len(template_questions),
        "questions": template_questions,
        "metadata": {
            "created_by": "QuizWeaver",
            "export_date": date.today().isoformat(),
        },
    }

    return template


def _build_template_question(q: Question, data: dict) -> Dict[str, Any]:
    """Build a single template question dict from a Question ORM object."""
    q_type = q.question_type or data.get("type", "mc")

    tq = {
        "question_type": q_type,
        "text": q.text or data.get("text", ""),
        "points": q.points or data.get("points", 0),
    }

    # Type-specific fields
    if q_type in ("mc", "multiple_choice"):
        options = data.get("options", [])
        if options and isinstance(options[0], dict):
            options = [opt.get("text", str(opt)) for opt in options]
        tq["options"] = options
        tq["correct_answer"] = _resolve_answer(data, options)

    elif q_type in ("tf", "true_false"):
        tq["correct_answer"] = _resolve_answer(data, ["True", "False"])

    elif q_type == "matching":
        tq["matches"] = _resolve_template_matches(data)

    elif q_type == "ordering":
        tq["items"] = data.get("items", [])
        tq["correct_order"] = data.get("correct_order", [])
        tq["instructions"] = data.get("instructions", "")

    elif q_type == "short_answer":
        tq["expected_answer"] = data.get("expected_answer", data.get("correct_answer", ""))
        tq["acceptable_answers"] = data.get("acceptable_answers", [])
        tq["rubric_hint"] = data.get("rubric_hint", "")

    else:
        # Generic: include correct_answer if present
        tq["correct_answer"] = _resolve_answer(data, data.get("options", []))
        if data.get("options"):
            tq["options"] = data["options"]

    # Cognitive fields
    if data.get("cognitive_level"):
        tq["cognitive_level"] = data["cognitive_level"]
    if data.get("cognitive_framework"):
        tq["cognitive_framework"] = data["cognitive_framework"]

    # Difficulty
    difficulty = data.get("difficulty")
    if difficulty:
        tq["difficulty"] = difficulty

    # Standards at question level
    q_standards = data.get("standards", data.get("sol_standards"))
    if q_standards:
        tq["standards"] = q_standards

    return tq


def _resolve_answer(data: dict, options: list) -> str:
    """Resolve the correct answer string from data."""
    answer = data.get("correct_answer") or data.get("answer")
    if answer is not None:
        return str(answer)

    correct_index = data.get("correct_index")
    if correct_index is not None and options:
        try:
            idx = int(correct_index)
            if 0 <= idx < len(options):
                return str(options[idx])
        except (ValueError, TypeError):
            pass

    is_true = data.get("is_true")
    if is_true is not None:
        return "True" if is_true else "False"

    return ""


def _resolve_template_matches(data: dict) -> List[Dict[str, str]]:
    """Resolve matching pairs for template."""
    matches = data.get("matches")
    if matches and isinstance(matches, list):
        return [
            {"term": m.get("term", ""), "definition": m.get("definition", "")} for m in matches if isinstance(m, dict)
        ]

    prompts = data.get("prompt_items", [])
    responses = data.get("response_items", [])
    correct_matches = data.get("correct_matches", {})
    if prompts and responses:
        result = []
        for i, prompt in enumerate(prompts):
            match_idx = correct_matches.get(str(i), i)
            definition = responses[match_idx] if match_idx < len(responses) else ""
            result.append({"term": prompt, "definition": definition})
        return result

    return []


def import_quiz_template(
    session: Session,
    template_data: Dict[str, Any],
    class_id: int,
    title: Optional[str] = None,
) -> Optional[Quiz]:
    """Import a JSON template to create a new quiz in a class.

    Creates a new Quiz with status='imported' and populates questions from
    the template data.

    Args:
        session: SQLAlchemy session.
        template_data: Parsed template dict (already validated).
        class_id: Class to import the quiz into.
        title: Optional override title; defaults to template title.

    Returns:
        The new Quiz object, or None on failure.
    """
    is_valid, errors = validate_template(template_data)
    if not is_valid:
        logger.warning("import_quiz_template: validation failed: %s", errors)
        return None

    quiz_title = title or template_data.get("title", "Imported Quiz")

    # Build a style profile from template metadata
    style_profile = {}
    if template_data.get("standards"):
        style_profile["sol_standards"] = template_data["standards"]
    if template_data.get("cognitive_framework"):
        style_profile["cognitive_framework"] = template_data["cognitive_framework"]
    if template_data.get("grade_level"):
        style_profile["grade_level"] = template_data["grade_level"]
    if template_data.get("subject"):
        style_profile["subject"] = template_data["subject"]
    style_profile["provider"] = "template_import"

    quiz = Quiz(
        title=quiz_title,
        class_id=class_id,
        status="imported",
        style_profile=json.dumps(style_profile),
    )
    session.add(quiz)
    session.flush()  # Get quiz.id

    # Create questions
    for i, tq in enumerate(template_data.get("questions", [])):
        question = _create_question_from_template(tq, quiz.id, i)
        session.add(question)

    session.commit()
    return quiz


def _create_question_from_template(tq: Dict[str, Any], quiz_id: int, sort_order: int) -> Question:
    """Create a Question ORM object from a template question dict."""
    q_type = tq.get("question_type", "mc")
    text = tq.get("text", "")
    points = tq.get("points", 0)

    # Build data dict
    data = {"type": q_type}

    if q_type in ("mc", "multiple_choice"):
        data["options"] = tq.get("options", [])
        data["correct_answer"] = tq.get("correct_answer", "")
        # Also set correct_index if we can
        if data["correct_answer"] and data["options"]:
            try:
                data["correct_index"] = data["options"].index(data["correct_answer"])
            except ValueError:
                pass

    elif q_type in ("tf", "true_false"):
        data["correct_answer"] = tq.get("correct_answer", "True")

    elif q_type == "matching":
        data["matches"] = tq.get("matches", [])

    elif q_type == "ordering":
        data["items"] = tq.get("items", [])
        data["correct_order"] = tq.get("correct_order", [])
        data["instructions"] = tq.get("instructions", "")
        data["question_type"] = "ordering"

    elif q_type == "short_answer":
        data["expected_answer"] = tq.get("expected_answer", "")
        data["acceptable_answers"] = tq.get("acceptable_answers", [])
        data["rubric_hint"] = tq.get("rubric_hint", "")
        data["question_type"] = "short_answer"

    else:
        data["correct_answer"] = tq.get("correct_answer", "")
        if tq.get("options"):
            data["options"] = tq["options"]

    # Cognitive fields
    if tq.get("cognitive_level"):
        data["cognitive_level"] = tq["cognitive_level"]
    if tq.get("cognitive_framework"):
        data["cognitive_framework"] = tq["cognitive_framework"]
    if tq.get("difficulty"):
        data["difficulty"] = tq["difficulty"]
    if tq.get("standards"):
        data["standards"] = tq["standards"]

    return Question(
        quiz_id=quiz_id,
        question_type=q_type,
        text=text,
        points=float(points) if points else 0,
        sort_order=sort_order,
        data=json.dumps(data),
    )


def validate_template(template_data: Any) -> Tuple[bool, List[str]]:
    """Validate template JSON structure.

    Args:
        template_data: Parsed JSON data to validate.

    Returns:
        Tuple of (is_valid, list_of_error_strings).
    """
    errors = []

    if not isinstance(template_data, dict):
        return False, ["Template must be a JSON object"]

    # Required fields
    if "template_version" not in template_data:
        errors.append("Missing required field: template_version")

    if "questions" not in template_data:
        errors.append("Missing required field: questions")
    elif not isinstance(template_data["questions"], list):
        errors.append("'questions' must be an array")
    elif len(template_data["questions"]) == 0:
        errors.append("Template must contain at least one question")
    else:
        # Validate each question
        for i, q in enumerate(template_data["questions"]):
            if not isinstance(q, dict):
                errors.append(f"Question {i + 1}: must be a JSON object")
                continue
            if not q.get("text"):
                errors.append(f"Question {i + 1}: missing 'text' field")
            if not q.get("question_type"):
                errors.append(f"Question {i + 1}: missing 'question_type' field")

    # Version check
    version = template_data.get("template_version")
    if version and version != TEMPLATE_VERSION:
        errors.append(f"Unsupported template version: {version} (expected {TEMPLATE_VERSION})")

    return len(errors) == 0, errors
