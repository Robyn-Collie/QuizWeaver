"""
Class sections and organization module for QuizWeaver.

Provides CRUD operations for teacher classes/blocks and active class switching.
"""

import json
from typing import List, Optional

import yaml
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
        result.append(
            {
                "id": cls.id,
                "name": cls.name,
                "grade_level": cls.grade_level,
                "subject": cls.subject,
                "standards": cls.standards,
                "lesson_count": lesson_count,
                "quiz_count": quiz_count,
                "created_at": cls.created_at,
            }
        )
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


def delete_class(session: Session, class_id: int) -> bool:
    """
    Delete a class by ID.

    Associated lesson_logs are removed via CASCADE.
    Associated quizzes have class_id set to NULL via SET NULL.

    Args:
        session: SQLAlchemy session
        class_id: ID of the class to delete

    Returns:
        True if the class was found and deleted, False otherwise
    """
    class_obj = session.query(Class).filter_by(id=class_id).first()
    if class_obj is None:
        return False
    # Explicitly delete lesson_logs first to avoid SQLAlchemy trying to
    # SET NULL on the NOT NULL class_id column before SQL CASCADE fires.
    session.query(LessonLog).filter_by(class_id=class_id).delete()
    session.delete(class_obj)
    session.commit()
    return True


def update_class(
    session: Session,
    class_id: int,
    name: Optional[str] = None,
    grade_level: Optional[str] = None,
    subject: Optional[str] = None,
    standards: Optional[List[str]] = None,
) -> Optional[Class]:
    """
    Update fields on an existing class.

    Only non-None arguments are applied, leaving other fields unchanged.

    Args:
        session: SQLAlchemy session
        class_id: ID of the class to update
        name: New name (or None to keep current)
        grade_level: New grade level (or None to keep current)
        subject: New subject (or None to keep current)
        standards: New standards list (or None to keep current)

    Returns:
        The updated Class object, or None if the class was not found
    """
    class_obj = session.query(Class).filter_by(id=class_id).first()
    if class_obj is None:
        return None

    if name is not None:
        class_obj.name = name
    if grade_level is not None:
        class_obj.grade_level = grade_level
    if subject is not None:
        class_obj.subject = subject
    if standards is not None:
        class_obj.standards = json.dumps(standards)

    session.commit()
    return class_obj


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
        with open(config_path) as f:
            config = yaml.safe_load(f)

        config["active_class_id"] = class_id

        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return True
    except Exception as e:
        print(f"Error updating config: {e}")
        return False
