"""
Topic-based generation module for QuizWeaver.

Allows teachers to generate quizzes and study materials from selected topics
without needing a source quiz. Routes to the existing quiz_generator or
study_generator based on the requested output type.
"""

import json
import logging
from typing import Optional, List

from sqlalchemy.orm import Session

from src.classroom import get_class
from src.lesson_tracker import get_assumed_knowledge
from src.database import LessonLog
from src.quiz_generator import generate_quiz
from src.study_generator import generate_study_material, VALID_MATERIAL_TYPES

logger = logging.getLogger(__name__)

# All valid output types for topic-based generation
VALID_OUTPUT_TYPES = ("quiz",) + VALID_MATERIAL_TYPES


def get_class_topics(session: Session, class_id: int) -> List[str]:
    """
    Get all unique topics from a class's lesson history.

    Args:
        session: SQLAlchemy session
        class_id: ID of the class

    Returns:
        Sorted list of unique topic strings
    """
    lessons = (
        session.query(LessonLog)
        .filter(LessonLog.class_id == class_id)
        .all()
    )
    topics = set()
    for lesson in lessons:
        if lesson.topics:
            topic_list = lesson.topics
            if isinstance(topic_list, str):
                try:
                    topic_list = json.loads(topic_list)
                except (json.JSONDecodeError, TypeError):
                    topic_list = []
            if isinstance(topic_list, list):
                for t in topic_list:
                    if isinstance(t, str) and t.strip():
                        topics.add(t.strip())
    return sorted(topics)


def search_topics(session: Session, class_id: int, query: str) -> List[str]:
    """
    Search topics from class lesson history matching a query string.

    Args:
        session: SQLAlchemy session
        class_id: ID of the class
        query: Search string (case-insensitive substring match)

    Returns:
        List of matching topic strings
    """
    all_topics = get_class_topics(session, class_id)
    if not query:
        return all_topics
    query_lower = query.lower()
    return [t for t in all_topics if query_lower in t.lower()]


def generate_from_topics(
    session: Session,
    class_id: int,
    topics: List[str],
    output_type: str,
    config: dict,
    num_questions: int = 20,
    grade_level: Optional[str] = None,
    sol_standards: Optional[List[str]] = None,
    cognitive_framework: Optional[str] = None,
    cognitive_distribution: Optional[dict] = None,
    difficulty: int = 3,
    title: Optional[str] = None,
):
    """
    Generate quiz or study materials from topics without a source quiz.

    Args:
        session: SQLAlchemy session
        class_id: ID of the class
        topics: List of topic strings to generate content about
        output_type: "quiz", "flashcard", "study_guide", "vocabulary", or "review_sheet"
        config: Application config dict
        num_questions: Number of questions (for quiz output)
        grade_level: Override grade level
        sol_standards: Standards to target
        cognitive_framework: "blooms", "dok", or None
        cognitive_distribution: Dict mapping level -> count
        difficulty: 1-5 difficulty scale
        title: Optional title for the generated content

    Returns:
        Quiz or StudySet object, or None on failure
    """
    if output_type not in VALID_OUTPUT_TYPES:
        logger.warning("generate_from_topics: invalid output_type=%s", output_type)
        return None

    if not topics:
        logger.warning("generate_from_topics: no topics provided")
        return None

    # Build topic string for context injection
    topic_str = ", ".join(topics)

    # Inject topics into config for the pipeline
    # The quiz/study generators use config for context
    enriched_config = _enrich_config_with_topics(config, topics, class_id, session)

    if output_type == "quiz":
        auto_title = title or f"Quiz: {topic_str[:60]}"
        enriched_config.setdefault("generation", {})["quiz_title"] = auto_title
        return generate_quiz(
            session=session,
            class_id=class_id,
            config=enriched_config,
            num_questions=num_questions,
            grade_level=grade_level,
            sol_standards=sol_standards,
            cognitive_framework=cognitive_framework,
            cognitive_distribution=cognitive_distribution,
            difficulty=difficulty,
        )
    else:
        # Study material output
        auto_title = title or f"{output_type.replace('_', ' ').title()}: {topic_str[:60]}"
        return generate_study_material(
            session=session,
            class_id=class_id,
            material_type=output_type,
            config=enriched_config,
            topic=topic_str,
            title=auto_title,
        )


def _enrich_config_with_topics(config, topics, class_id, session):
    """
    Create an enriched config that includes topic context for the LLM.
    Does not mutate the original config.
    """
    import copy
    enriched = copy.deepcopy(config)

    # Inject topic context into the generation section
    topic_str = ", ".join(topics)
    enriched.setdefault("generation", {})["topic_context"] = topic_str

    # Include assumed knowledge depth for these topics
    knowledge = get_assumed_knowledge(session, class_id)
    relevant_knowledge = {}
    for topic in topics:
        topic_lower = topic.lower()
        for k, v in knowledge.items():
            if topic_lower in k.lower() or k.lower() in topic_lower:
                relevant_knowledge[k] = v
    if relevant_knowledge:
        enriched["generation"]["assumed_knowledge_context"] = relevant_knowledge

    return enriched
