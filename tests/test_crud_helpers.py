"""
Tests for delete/update CRUD helper functions in classroom.py and lesson_tracker.py.

Tests cover:
    - delete_class: success, not found, cascade lesson deletion, nullify quiz class_id
    - update_class: name, multiple fields, partial update, not found, standards as JSON
    - delete_lesson: success, not found, doesn't affect other lessons

Run with: python -m pytest tests/test_crud_helpers.py -v
"""

import json
import os
import sys
import tempfile

import pytest

# Ensure project root is on the path so src imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import event

from src.database import get_engine, init_db, get_session, Class, LessonLog, Quiz
from src.classroom import create_class, get_class, list_classes, delete_class, update_class
from src.lesson_tracker import log_lesson, delete_lesson


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """
    Provide a fresh SQLAlchemy session backed by a temporary SQLite database.

    Enables SQLite foreign key enforcement (required for CASCADE / SET NULL)
    and tears down cleanly on Windows (engine.dispose before file removal).
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    engine = get_engine(db_path)

    # SQLite does not enforce FK constraints by default -- turn them on so
    # that ON DELETE CASCADE / SET NULL actually fire.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    init_db(engine)
    session = get_session(engine)

    yield session

    session.close()
    engine.dispose()
    try:
        os.remove(db_path)
    except OSError:
        pass  # Windows may still hold the file briefly


# ===========================================================================
# delete_class tests
# ===========================================================================

class TestDeleteClass:
    """Tests for classroom.delete_class()."""

    def test_delete_class_success(self, db_session):
        """Create a class, delete it, and verify it is gone from the DB."""
        cls = create_class(db_session, name="Block A", grade_level="7th Grade")
        class_id = cls.id

        result = delete_class(db_session, class_id)

        assert result is True, "delete_class should return True on success"
        assert get_class(db_session, class_id) is None, (
            "Class should no longer exist after deletion"
        )

    def test_delete_class_not_found(self, db_session):
        """Deleting a nonexistent class_id should return False."""
        result = delete_class(db_session, 99999)

        assert result is False, (
            "delete_class should return False when the class does not exist"
        )

    def test_delete_class_cascades_lessons(self, db_session):
        """Deleting a class should also delete its associated lesson logs (CASCADE)."""
        cls = create_class(db_session, name="Cascade Class")
        log_lesson(db_session, cls.id, content="Lesson about photosynthesis")
        log_lesson(db_session, cls.id, content="Lesson about cell division")

        # Sanity check: lessons exist
        lessons_before = (
            db_session.query(LessonLog).filter_by(class_id=cls.id).all()
        )
        assert len(lessons_before) == 2, "Should have two lessons before delete"

        delete_class(db_session, cls.id)

        lessons_after = (
            db_session.query(LessonLog).filter_by(class_id=cls.id).all()
        )
        assert len(lessons_after) == 0, (
            "All lesson logs for the deleted class should be removed (CASCADE)"
        )

    def test_delete_class_nullifies_quizzes(self, db_session):
        """Deleting a class should SET NULL on quiz.class_id, not delete the quiz."""
        cls = create_class(db_session, name="Quiz Class")
        quiz = Quiz(title="Unit Test Quiz", class_id=cls.id, status="generated")
        db_session.add(quiz)
        db_session.commit()
        quiz_id = quiz.id

        delete_class(db_session, cls.id)

        # Expire cached attributes so we re-read from DB
        db_session.expire_all()

        remaining_quiz = db_session.query(Quiz).filter_by(id=quiz_id).first()
        assert remaining_quiz is not None, (
            "Quiz should still exist after its class is deleted"
        )
        assert remaining_quiz.class_id is None, (
            "Quiz class_id should be NULL after class deletion (SET NULL)"
        )


# ===========================================================================
# update_class tests
# ===========================================================================

class TestUpdateClass:
    """Tests for classroom.update_class()."""

    def test_update_class_name(self, db_session):
        """Updating only the name should change it and leave other fields intact."""
        cls = create_class(
            db_session,
            name="Original Name",
            grade_level="8th Grade",
            subject="Science",
        )

        updated = update_class(db_session, cls.id, name="New Name")

        assert updated is not None, "update_class should return the updated object"
        assert updated.name == "New Name", "Name should be updated"
        assert updated.grade_level == "8th Grade", "grade_level should be unchanged"
        assert updated.subject == "Science", "subject should be unchanged"

    def test_update_class_multiple_fields(self, db_session):
        """Updating grade_level and subject at the same time should apply both."""
        cls = create_class(db_session, name="Multi Update")

        updated = update_class(
            db_session, cls.id, grade_level="9th Grade", subject="Math"
        )

        assert updated is not None
        assert updated.grade_level == "9th Grade"
        assert updated.subject == "Math"
        assert updated.name == "Multi Update", "Name should remain unchanged"

    def test_update_class_partial(self, db_session):
        """Updating only one field should not alter the others."""
        cls = create_class(
            db_session,
            name="Partial",
            grade_level="6th Grade",
            subject="History",
            standards=["SOL 6.1", "SOL 6.2"],
        )
        original_standards = cls.standards

        updated = update_class(db_session, cls.id, name="Partial Updated")

        assert updated is not None
        assert updated.name == "Partial Updated"
        assert updated.grade_level == "6th Grade", "grade_level should be unchanged"
        assert updated.subject == "History", "subject should be unchanged"
        assert updated.standards == original_standards, "standards should be unchanged"

    def test_update_class_not_found(self, db_session):
        """Updating a nonexistent class should return None."""
        result = update_class(db_session, 99999, name="Ghost")

        assert result is None, (
            "update_class should return None when the class does not exist"
        )

    def test_update_class_standards(self, db_session):
        """Updating standards should store them as a JSON-encoded list."""
        cls = create_class(db_session, name="Standards Test")

        new_standards = ["SOL 8.1", "SOL 8.3", "SAT-MATH-1"]
        updated = update_class(db_session, cls.id, standards=new_standards)

        assert updated is not None

        # The implementation may store standards as a JSON string or a native
        # list (depending on the SQLAlchemy JSON column handling for SQLite).
        stored = updated.standards
        if isinstance(stored, str):
            stored = json.loads(stored)
        assert stored == new_standards, (
            "Standards should be stored as the provided list (JSON-encoded)"
        )


# ===========================================================================
# delete_lesson tests
# ===========================================================================

class TestDeleteLesson:
    """Tests for lesson_tracker.delete_lesson()."""

    def test_delete_lesson_success(self, db_session):
        """Log a lesson, delete it, and verify it is gone."""
        cls = create_class(db_session, name="Lesson Del Class")
        lesson = log_lesson(db_session, cls.id, content="Temporary lesson on energy")
        lesson_id = lesson.id

        result = delete_lesson(db_session, lesson_id)

        assert result is True, "delete_lesson should return True on success"
        assert (
            db_session.query(LessonLog).filter_by(id=lesson_id).first() is None
        ), "Lesson should no longer exist after deletion"

    def test_delete_lesson_not_found(self, db_session):
        """Deleting a nonexistent lesson should return False."""
        result = delete_lesson(db_session, 99999)

        assert result is False, (
            "delete_lesson should return False when the lesson does not exist"
        )

    def test_delete_lesson_doesnt_affect_others(self, db_session):
        """Deleting one lesson should leave other lessons for the same class intact."""
        cls = create_class(db_session, name="Multi Lesson Class")
        lesson_a = log_lesson(db_session, cls.id, content="Lesson A about waves")
        lesson_b = log_lesson(db_session, cls.id, content="Lesson B about light")
        lesson_c = log_lesson(db_session, cls.id, content="Lesson C about sound")

        delete_lesson(db_session, lesson_b.id)

        remaining = (
            db_session.query(LessonLog).filter_by(class_id=cls.id).all()
        )
        remaining_ids = {l.id for l in remaining}

        assert lesson_a.id in remaining_ids, "Lesson A should still exist"
        assert lesson_c.id in remaining_ids, "Lesson C should still exist"
        assert lesson_b.id not in remaining_ids, "Lesson B should be deleted"
        assert len(remaining) == 2, "Exactly two lessons should remain"
