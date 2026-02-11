"""
Study material generator for QuizWeaver.

Generates flashcards, study guides, vocabulary lists, and review sheets
using the LLM pipeline. Uses MockLLMProvider by default for zero-cost development.
"""

import copy
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.classroom import get_class
from src.database import Quiz, Question, StudySet, StudyCard

logger = logging.getLogger(__name__)

VALID_MATERIAL_TYPES = ("flashcard", "study_guide", "vocabulary", "review_sheet")

# Card type mapping: material_type -> default card_type for each item
CARD_TYPE_MAP = {
    "flashcard": "flashcard",
    "study_guide": "section",
    "vocabulary": "term",
    "review_sheet": "fact",
}

# Prompts for each material type
MATERIAL_PROMPTS = {
    "flashcard": (
        "Generate a set of flashcards for studying the following topic. "
        "Return a JSON array of objects with keys: front (term/question), "
        "back (definition/answer), tags (array of topic tags). "
        "Generate 10 flashcards."
    ),
    "study_guide": (
        "Generate a structured study guide for the following topic. "
        "Return a JSON array of section objects with keys: heading (section title), "
        "content (detailed explanation), key_points (array of bullet points). "
        "Generate 4 sections covering the main concepts."
    ),
    "vocabulary": (
        "Generate a vocabulary list for the following topic. "
        "Return a JSON array of objects with keys: term, definition, "
        "example (usage in context), part_of_speech. "
        "Generate 8 vocabulary terms."
    ),
    "review_sheet": (
        "Generate a condensed review sheet for the following topic. "
        "Return a JSON array of objects with keys: heading (item title), "
        "content (the formula/fact/concept), type (one of: formula, fact, concept). "
        "Generate 6 items covering key formulas, facts, and concepts."
    ),
}


def _build_context(session, class_id, quiz_id=None, topic=None):
    """Build context string from class info, quiz questions, and topic."""
    parts = []

    class_obj = get_class(session, class_id)
    if class_obj:
        parts.append(f"Class: {class_obj.name}")
        if class_obj.grade_level:
            parts.append(f"Grade Level: {class_obj.grade_level}")
        if class_obj.subject:
            parts.append(f"Subject: {class_obj.subject}")

    if quiz_id:
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if quiz:
            parts.append(f"\nSource Quiz: {quiz.title}")
            questions = (
                session.query(Question)
                .filter_by(quiz_id=quiz_id)
                .order_by(Question.sort_order, Question.id)
                .all()
            )
            for q in questions:
                parts.append(f"- {q.text}")

    if topic:
        parts.append(f"\nTopic: {topic}")

    return "\n".join(parts)


def _parse_items(response_text, material_type):
    """Parse JSON response into list of item dicts."""
    try:
        items = json.loads(response_text)
        if isinstance(items, list):
            return items
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to extract JSON array from response
    import re
    match = re.search(r'\[.*\]', response_text, re.DOTALL)
    if match:
        try:
            items = json.loads(match.group())
            if isinstance(items, list):
                return items
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning("Failed to parse study material response")
    return None


def generate_study_material(
    session: Session,
    class_id: int,
    material_type: str,
    config: dict,
    quiz_id: Optional[int] = None,
    topic: Optional[str] = None,
    title: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> Optional[StudySet]:
    """Generate a StudySet with StudyCards using the LLM pipeline.

    Args:
        session: SQLAlchemy session.
        class_id: ID of the class to generate for.
        material_type: One of flashcard, study_guide, vocabulary, review_sheet.
        config: Application config dict (must include llm.provider).
        quiz_id: Optional quiz ID to use as source material.
        topic: Optional free-text topic to generate about.
        title: Optional title for the study set.

    Returns:
        StudySet ORM object with cards attached, or None on failure.
    """
    # Apply provider override if specified
    if provider_name:
        config = copy.deepcopy(config)
        config.setdefault("llm", {})["provider"] = provider_name

    if material_type not in VALID_MATERIAL_TYPES:
        logger.warning("generate_study_material: invalid material_type=%s", material_type)
        return None

    # Validate class exists
    class_obj = get_class(session, class_id)
    if class_obj is None:
        logger.warning("generate_study_material: class_id=%s not found", class_id)
        return None

    # Validate quiz_id if provided
    if quiz_id is not None:
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if quiz is None:
            logger.warning("generate_study_material: quiz_id=%s not found", quiz_id)
            return None

    # Build title
    if not title:
        type_label = material_type.replace("_", " ").title()
        topic_label = topic or (class_obj.subject or "Study")
        title = f"{type_label}: {topic_label}"

    # Create study set record
    study_set = StudySet(
        class_id=class_id,
        quiz_id=quiz_id,
        title=title,
        material_type=material_type,
        status="generating",
        config=json.dumps({
            "material_type": material_type,
            "quiz_id": quiz_id,
            "topic": topic,
            "provider": config.get("llm", {}).get("provider", "mock"),
        }),
    )
    session.add(study_set)
    session.commit()

    # Build prompt
    context = _build_context(session, class_id, quiz_id, topic)
    base_prompt = MATERIAL_PROMPTS[material_type]
    full_prompt = f"{base_prompt}\n\nContext:\n{context}"

    # Get LLM response
    try:
        from src.llm_provider import get_provider
        provider = get_provider(config, web_mode=True)

        # Check if mock provider — use specialized mock response
        provider_name = config.get("llm", {}).get("provider", "mock")
        if provider_name == "mock":
            from src.mock_responses import get_study_material_response, SCIENCE_TOPICS
            # Extract keywords from context
            context_lower = context.lower()
            keywords = [t for t in SCIENCE_TOPICS if t in context_lower]
            response_text = get_study_material_response(
                [full_prompt], material_type, keywords or None
            )
        else:
            response_text = provider.generate([full_prompt], json_mode=True)

    except Exception as e:
        logger.error("generate_study_material: LLM call failed: %s", e)
        study_set.status = "failed"
        session.commit()
        return None

    # Parse response
    items = _parse_items(response_text, material_type)
    if not items:
        study_set.status = "failed"
        session.commit()
        return None

    # Create StudyCard records
    card_type = CARD_TYPE_MAP.get(material_type, "flashcard")
    for idx, item in enumerate(items):
        if material_type == "flashcard":
            front = item.get("front", "")
            back = item.get("back", "")
            extras = {"tags": item.get("tags", [])}
        elif material_type == "study_guide":
            front = item.get("heading", "")
            back = item.get("content", "")
            extras = {"key_points": item.get("key_points", [])}
        elif material_type == "vocabulary":
            front = item.get("term", "")
            back = item.get("definition", "")
            extras = {
                "example": item.get("example", ""),
                "part_of_speech": item.get("part_of_speech", ""),
            }
        elif material_type == "review_sheet":
            front = item.get("heading", "")
            back = item.get("content", "")
            extras = {"type": item.get("type", "")}
        else:
            front = item.get("front", "")
            back = item.get("back", "")
            extras = {}

        card = StudyCard(
            study_set_id=study_set.id,
            card_type=card_type,
            sort_order=idx,
            front=front,
            back=back,
            data=json.dumps(extras),
        )
        session.add(card)

    study_set.status = "generated"
    session.commit()
    session.refresh(study_set)

    return study_set
