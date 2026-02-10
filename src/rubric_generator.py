"""
Rubric generator for QuizWeaver.

Generates scoring rubrics aligned to a quiz's questions, cognitive levels,
and standards. Uses MockLLMProvider by default for zero-cost development.
"""

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.database import Quiz, Question, Rubric, RubricCriterion

logger = logging.getLogger(__name__)

PROFICIENCY_LEVELS = ["Beginning", "Developing", "Proficient", "Advanced"]


def _load_quiz_context(session, quiz_id):
    """Load quiz metadata and questions for rubric generation."""
    quiz = session.query(Quiz).filter_by(id=quiz_id).first()
    if not quiz:
        return None, None, None

    questions = (
        session.query(Question)
        .filter_by(quiz_id=quiz_id)
        .order_by(Question.sort_order, Question.id)
        .all()
    )

    # Parse style_profile
    style_profile = quiz.style_profile
    if isinstance(style_profile, str):
        try:
            style_profile = json.loads(style_profile)
        except (json.JSONDecodeError, ValueError):
            style_profile = {}
    if not isinstance(style_profile, dict):
        style_profile = {}

    # Build question summaries
    q_data_list = []
    for q in questions:
        data = q.data
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                data = {}
        if not isinstance(data, dict):
            data = {}

        q_data_list.append({
            "type": q.question_type or data.get("type", "mc"),
            "text": q.text or data.get("text", ""),
            "points": q.points or data.get("points", 5),
            "cognitive_level": data.get("cognitive_level"),
            "cognitive_framework": data.get("cognitive_framework"),
        })

    return quiz, style_profile, q_data_list


def _parse_criteria(response_text):
    """Parse JSON response into list of criterion dicts."""
    try:
        items = json.loads(response_text)
        if isinstance(items, list):
            return items
    except (json.JSONDecodeError, ValueError):
        pass

    import re
    match = re.search(r'\[.*\]', response_text, re.DOTALL)
    if match:
        try:
            items = json.loads(match.group())
            if isinstance(items, list):
                return items
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning("Failed to parse rubric response")
    return None


def generate_rubric(
    session: Session,
    quiz_id: int,
    config: dict,
    title: Optional[str] = None,
) -> Optional[Rubric]:
    """Generate a scoring rubric aligned to a quiz's questions and standards.

    Args:
        session: SQLAlchemy session.
        quiz_id: ID of the quiz to generate a rubric for.
        config: Application config dict (must include llm.provider).
        title: Optional title for the rubric.

    Returns:
        Rubric ORM object with criteria, or None on failure.
    """
    quiz, style_profile, q_data_list = _load_quiz_context(session, quiz_id)
    if quiz is None:
        logger.warning("generate_rubric: quiz_id=%s not found", quiz_id)
        return None

    if not q_data_list:
        logger.warning("generate_rubric: no questions for quiz_id=%s", quiz_id)
        return None

    # Build title
    if not title:
        title = f"Rubric: {quiz.title or 'Quiz'}"

    # Create rubric record
    rubric = Rubric(
        quiz_id=quiz_id,
        title=title,
        status="generating",
        config=json.dumps({
            "quiz_id": quiz_id,
            "provider": config.get("llm", {}).get("provider", "mock"),
        }),
    )
    session.add(rubric)
    session.commit()

    # Build prompt
    framework = style_profile.get("cognitive_framework", "")
    standards = style_profile.get("sol_standards", [])
    if isinstance(standards, list):
        standards = ", ".join(standards)

    prompt = (
        f"Generate a scoring rubric for the following quiz.\n\n"
        f"Quiz: {quiz.title}\n"
    )
    if framework:
        prompt += f"Cognitive Framework: {framework}\n"
    if standards:
        prompt += f"Standards: {standards}\n"
    prompt += (
        f"\nQuestions ({len(q_data_list)} total):\n"
        f"{json.dumps(q_data_list, indent=2)}\n\n"
        f"Generate a JSON array of rubric criteria. Each criterion should have:\n"
        f"- criterion: what is being assessed\n"
        f"- description: detailed description\n"
        f"- max_points: maximum points\n"
        f"- levels: array of 4 proficiency levels (Beginning, Developing, Proficient, Advanced)\n"
        f"  each with: level (1-4), label, description\n"
    )

    # Get LLM response
    try:
        provider_name = config.get("llm", {}).get("provider", "mock")
        if provider_name == "mock":
            from src.mock_responses import get_rubric_response, SCIENCE_TOPICS
            context_lower = prompt.lower()
            keywords = [t for t in SCIENCE_TOPICS if t in context_lower]
            response_text = get_rubric_response(
                q_data_list, style_profile, keywords or None
            )
        else:
            from src.llm_provider import get_provider
            provider = get_provider(config, web_mode=True)
            response_text = provider.generate([prompt], json_mode=True)

    except Exception as e:
        logger.error("generate_rubric: LLM call failed: %s", e)
        rubric.status = "failed"
        session.commit()
        return None

    # Parse response
    criteria_data = _parse_criteria(response_text)
    if not criteria_data:
        rubric.status = "failed"
        session.commit()
        return None

    # Create RubricCriterion records
    for idx, c_data in enumerate(criteria_data):
        criterion = RubricCriterion(
            rubric_id=rubric.id,
            sort_order=idx,
            criterion=c_data.get("criterion", f"Criterion {idx + 1}"),
            description=c_data.get("description", ""),
            max_points=float(c_data.get("max_points", 5)),
            levels=json.dumps(c_data.get("levels", [])),
        )
        session.add(criterion)

    rubric.status = "generated"
    session.commit()
    session.refresh(rubric)

    return rubric
