"""
Multi-class management module for QuizWeaver.

Provides CRUD operations for teacher classes/blocks and active class switching.
"""

import json
import yaml
from typing import Optional, List
from sqlalchemy.orm import Session

from src.database import Class, LessonLog, Quiz


def create_class(
    session: Session,
    name: str,
    grade_level: Optional[str] = None,
    subject: Optional[str] = None,
    standards: Optional[List[str]] = None,
) -> Class:
    """
    Create a new Class record in the database.

    Args:
        session: SQLAlchemy session
        name: Class name (required)
        grade_level: Grade level (e.g., "7th Grade")
        subject: Subject area (e.g., "Science")
        standards: List of standards (e.g., ["SOL 7.1", "SOL 7.2"])

    Returns:
        The created Class object with its assigned ID
    """
    new_class = Class(
        name=name,
        grade_level=grade_level,
        subject=subject,
        standards=json.dumps(standards or []),
        config=json.dumps({}),
    )
    session.add(new_class)
    session.commit()
    return new_class


def get_class(session: Session, class_id: int) -> Optional[Class]:
    """
    Fetch a single class by ID.

    Args:
        session: SQLAlchemy session
        class_id: The class ID to look up

    Returns:
        Class object or None if not found
    """
    return session.query(Class).filter_by(id=class_id).first()


def list_classes(session: Session) -> List[dict]:
    """
    Query all classes with lesson and quiz counts.

    Args:
        session: SQLAlchemy session

    Returns:
        List of dicts with class info plus lesson_count and quiz_count
    """
    classes = session.query(Class).order_by(Class.id).all()
    result = []
    for cls in classes:
        lesson_count = session.query(LessonLog).filter_by(class_id=cls.id).count()
        quiz_count = session.query(Quiz).filter_by(class_id=cls.id).count()
        result.append({
            "id": cls.id,
            "name": cls.name,
            "grade_level": cls.grade_level,
            "subject": cls.subject,
            "standards": cls.standards,
            "lesson_count": lesson_count,
            "quiz_count": quiz_count,
            "created_at": cls.created_at,
        })
    return result


def get_active_class(session: Session, config: dict) -> Optional[Class]:
    """
    Get the currently active class based on config.yaml's active_class_id.

    Args:
        session: SQLAlchemy session
        config: Application config dict

    Returns:
        Class object or None if not configured / not found
    """
    class_id = config.get("llm", {}).get("active_class_id")
    if class_id is None:
        class_id = config.get("active_class_id")
    if class_id is None:
        return None
    return get_class(session, int(class_id))


def set_active_class(config_path: str, class_id: int) -> bool:
    """
    Update config.yaml with a new active_class_id.

    Args:
        config_path: Path to config.yaml file
        class_id: The class ID to set as active

    Returns:
        True on success, False on failure
    """
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        config["active_class_id"] = class_id

        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return True
    except Exception as e:
        print(f"Error updating config: {e}")
        return False
