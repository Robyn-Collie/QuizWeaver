"""
Lesson tracking module for QuizWeaver.

Tracks lessons taught to each class, extracts topics, and maintains
assumed knowledge depth for each class.
"""

import json
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from src.database import Class, LessonLog


# Known science topic keywords for simple extraction
KNOWN_TOPICS = [
    "photosynthesis", "cell division", "mitosis", "meiosis",
    "respiration", "cellular respiration", "genetics", "heredity",
    "evolution", "natural selection", "ecosystems", "ecology",
    "atomic structure", "atoms", "molecules",
    "chemical reactions", "chemical bonds",
    "forces", "motion", "newton", "gravity",
    "energy", "kinetic energy", "potential energy",
    "waves", "sound", "light", "electromagnetic",
    "electricity", "magnetism", "circuits",
    "plate tectonics", "earthquakes", "volcanoes",
    "weather", "climate", "atmosphere",
    "water cycle", "rock cycle", "carbon cycle",
    "cells", "organelles", "membrane",
    "dna", "rna", "protein synthesis",
    "classification", "taxonomy",
    "food web", "food chain",
    "adaptation", "biodiversity",
    "periodic table", "elements",
    "acids", "bases", "ph",
    "solar system", "planets", "stars",
    "change over time",
]


def extract_topics(text: str) -> List[str]:
    """
    Extract known science topics from text using keyword matching.

    Args:
        text: Lesson content text to search

    Returns:
        List of detected topic strings (lowercase)
    """
    text_lower = text.lower()
    found = []
    for topic in KNOWN_TOPICS:
        if topic in text_lower:
            found.append(topic)
    return found


def log_lesson(
    session: Session,
    class_id: int,
    content: str,
    topics: Optional[List[str]] = None,
    notes: Optional[str] = None,
    lesson_date: Optional[date] = None,
    standards_addressed: Optional[List[str]] = None,
) -> LessonLog:
    """
    Create a LessonLog record for a class and update assumed knowledge.

    Args:
        session: SQLAlchemy session
        class_id: Class to log lesson for
        content: Lesson content text
        topics: Override topics (if None, auto-extracted from content)
        notes: Teacher observations/notes
        lesson_date: Date of lesson (defaults to today)
        standards_addressed: Standards covered in this lesson

    Returns:
        The created LessonLog object
    """
    if topics is None:
        topics = extract_topics(content)

    lesson = LessonLog(
        class_id=class_id,
        date=lesson_date or date.today(),
        content=content,
        topics=json.dumps(topics),
        standards_addressed=json.dumps(standards_addressed or []),
        notes=notes,
    )
    session.add(lesson)
    session.commit()

    # Update assumed knowledge for the class
    if topics:
        update_assumed_knowledge(session, class_id, topics)

    return lesson


def get_recent_lessons(
    session: Session, class_id: int, days: int = 14
) -> List[LessonLog]:
    """
    Query lessons from the past N days for a class.

    Args:
        session: SQLAlchemy session
        class_id: Class ID to query
        days: Number of days to look back (default 14)

    Returns:
        List of LessonLog objects sorted by date DESC
    """
    threshold = date.today() - timedelta(days=days)
    return (
        session.query(LessonLog)
        .filter(LessonLog.class_id == class_id, LessonLog.date >= threshold)
        .order_by(LessonLog.date.desc())
        .all()
    )


def list_lessons(
    session: Session, class_id: int, filters: Optional[Dict[str, Any]] = None
) -> List[LessonLog]:
    """
    Query lessons with optional filters.

    Args:
        session: SQLAlchemy session
        class_id: Class ID to query
        filters: Optional dict with keys:
            - date_from: date object
            - date_to: date object
            - topic: string to search in topics JSON
            - last_days: int for recent N days

    Returns:
        List of LessonLog objects matching filters
    """
    query = session.query(LessonLog).filter(LessonLog.class_id == class_id)

    if filters:
        if "last_days" in filters:
            threshold = date.today() - timedelta(days=filters["last_days"])
            query = query.filter(LessonLog.date >= threshold)
        if "date_from" in filters:
            query = query.filter(LessonLog.date >= filters["date_from"])
        if "date_to" in filters:
            query = query.filter(LessonLog.date <= filters["date_to"])
        if "topic" in filters:
            # Search topic within JSON topics column
            query = query.filter(LessonLog.topics.contains(filters["topic"]))

    return query.order_by(LessonLog.date.desc()).all()


def update_assumed_knowledge(
    session: Session, class_id: int, topics: List[str], depth_increment: int = 1
) -> Dict[str, Any]:
    """
    Update assumed knowledge in Class.config JSON.

    Knowledge depth levels:
        1: introduced - topic mentioned once
        2: reinforced - topic revisited
        3: practiced - hands-on/lab work
        4: mastered - pre-test review
        5: expert - advanced applications (max)

    Args:
        session: SQLAlchemy session
        class_id: Class to update
        topics: List of topic strings to update
        depth_increment: How much to increase depth (default 1)

    Returns:
        Updated assumed_knowledge dict
    """
    class_obj = session.query(Class).filter_by(id=class_id).first()
    if not class_obj:
        return {}

    config = json.loads(class_obj.config or "{}")
    knowledge = config.get("assumed_knowledge", {})

    today_str = date.today().isoformat()
    for topic in topics:
        if topic in knowledge:
            current_depth = knowledge[topic].get("depth", 0)
            knowledge[topic]["depth"] = min(current_depth + depth_increment, 5)
            knowledge[topic]["last_taught"] = today_str
            knowledge[topic]["mention_count"] = knowledge[topic].get("mention_count", 1) + 1
        else:
            knowledge[topic] = {
                "depth": 1,
                "last_taught": today_str,
                "mention_count": 1,
            }

    config["assumed_knowledge"] = knowledge
    class_obj.config = json.dumps(config)
    session.commit()

    return knowledge


def delete_lesson(session: Session, lesson_id: int) -> bool:
    """
    Delete a single lesson log by ID.

    Args:
        session: SQLAlchemy session
        lesson_id: ID of the LessonLog to delete

    Returns:
        True if the lesson was found and deleted, False otherwise
    """
    lesson = session.query(LessonLog).filter_by(id=lesson_id).first()
    if lesson is None:
        return False
    session.delete(lesson)
    session.commit()
    return True


def get_assumed_knowledge(session: Session, class_id: int) -> Dict[str, Any]:
    """
    Get the assumed knowledge dict for a class.

    Args:
        session: SQLAlchemy session
        class_id: Class ID

    Returns:
        Dict of {topic: {depth, last_taught, mention_count}, ...}
    """
    class_obj = session.query(Class).filter_by(id=class_id).first()
    if not class_obj:
        return {}
    config = json.loads(class_obj.config or "{}")
    return config.get("assumed_knowledge", {})
