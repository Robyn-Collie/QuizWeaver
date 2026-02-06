"""
End-to-end integration tests for multi-class workflow.

Tests the full workflow across classroom, lesson tracking, and database modules
working together. Uses temporary SQLite databases for isolation and
engine.dispose() before cleanup for Windows compatibility.

Run with: python -m pytest tests/test_e2e_multi_class.py -v
"""

import json
import os
import sys
import tempfile

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import get_engine, init_db, get_session, Class, LessonLog, Quiz
from src.classroom import create_class, get_class, list_classes
from src.lesson_tracker import (
    log_lesson,
    get_recent_lessons,
    get_assumed_knowledge,
    extract_topics,
)
from src.migrations import run_migrations, create_default_class_if_needed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_env():
    """
    Create a temporary SQLite database with all tables initialized.

    Yields (engine, session, db_path) and cleans up afterward.
    Uses engine.dispose() before file removal to avoid Windows file-lock errors.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()

    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)

    yield engine, session, db_path

    # Tear down -- close session and dispose engine before deleting the file
    session.close()
    engine.dispose()
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except OSError:
        pass  # Windows may still hold a lock; ignore cleanup errors


# ---------------------------------------------------------------------------
# 1. Full multi-class workflow
# ---------------------------------------------------------------------------

class TestFullMultiClassWorkflow:
    """
    Create two classes, log distinct lessons to each, and verify that
    lessons and assumed knowledge are fully isolated per class.
    """

    def test_full_multi_class_workflow(self, db_env):
        engine, session, db_path = db_env

        # -- Create two classes -------------------------------------------
        block_a = create_class(
            session,
            name="7th Grade Block A",
            grade_level="7th Grade",
            subject="Science",
        )
        block_b = create_class(
            session,
            name="7th Grade Block B",
            grade_level="7th Grade",
            subject="Science",
        )
        assert block_a.id is not None, "Block A should have an assigned ID"
        assert block_b.id is not None, "Block B should have an assigned ID"
        assert block_a.id != block_b.id, "Classes should have distinct IDs"

        # -- Log photosynthesis to Block A --------------------------------
        log_lesson(
            session,
            class_id=block_a.id,
            content="Today we covered photosynthesis and how plants convert light energy.",
            topics=["photosynthesis"],
        )

        # -- Log cell division to Block B ---------------------------------
        log_lesson(
            session,
            class_id=block_b.id,
            content="Today we studied cell division and the stages of mitosis.",
            topics=["cell division"],
        )

        # -- Verify lesson isolation --------------------------------------
        lessons_a = get_recent_lessons(session, class_id=block_a.id, days=30)
        lessons_b = get_recent_lessons(session, class_id=block_b.id, days=30)

        assert len(lessons_a) == 1, "Block A should have exactly 1 lesson"
        assert len(lessons_b) == 1, "Block B should have exactly 1 lesson"
        assert "photosynthesis" in lessons_a[0].content
        assert "cell division" in lessons_b[0].content

        # -- Verify assumed knowledge correct per class -------------------
        knowledge_a = get_assumed_knowledge(session, block_a.id)
        knowledge_b = get_assumed_knowledge(session, block_b.id)

        assert "photosynthesis" in knowledge_a, (
            "Block A should know photosynthesis"
        )
        assert "cell division" not in knowledge_a, (
            "Block A should NOT know cell division"
        )
        assert "cell division" in knowledge_b, (
            "Block B should know cell division"
        )
        assert "photosynthesis" not in knowledge_b, (
            "Block B should NOT know photosynthesis"
        )


# ---------------------------------------------------------------------------
# 2. Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """
    Verify that a Quiz created without a class_id (legacy behavior) is
    still accessible after migrations and default-class creation.
    """

    def test_backward_compatibility(self, db_env):
        engine, session, db_path = db_env

        # -- Create a quiz with no class_id (legacy) ----------------------
        legacy_quiz = Quiz(title="Legacy Chapter 5 Quiz", status="generated")
        session.add(legacy_quiz)
        session.commit()
        legacy_quiz_id = legacy_quiz.id

        assert legacy_quiz.class_id is None, (
            "Legacy quiz should have NULL class_id before migration"
        )

        # -- Run SQL migrations and create default class ------------------
        run_migrations(db_path, verbose=False)
        create_default_class_if_needed(db_path)

        # Refresh the session to pick up raw-SQL changes
        session.expire_all()

        # -- Verify the legacy quiz is still accessible -------------------
        reloaded = session.query(Quiz).filter_by(id=legacy_quiz_id).first()
        assert reloaded is not None, "Legacy quiz should still exist after migration"
        assert reloaded.title == "Legacy Chapter 5 Quiz"

        # After create_default_class_if_needed, NULL class_ids are updated to 1
        # The quiz's class_id should now be 1 (Legacy Class)
        assert reloaded.class_id == 1, (
            "Legacy quiz should be assigned to default Legacy Class (id=1)"
        )


# ---------------------------------------------------------------------------
# 3. Class knowledge builds over time
# ---------------------------------------------------------------------------

class TestClassKnowledgeBuildsOverTime:
    """
    Logging the same topic multiple times should increment its depth,
    while new topics start at depth 1.
    """

    def test_class_knowledge_builds_over_time(self, db_env):
        engine, session, db_path = db_env

        # -- Create a class -----------------------------------------------
        cls = create_class(
            session,
            name="8th Grade Biology",
            grade_level="8th Grade",
            subject="Biology",
        )

        # -- Lesson 1: introduce photosynthesis (depth 1) -----------------
        log_lesson(
            session,
            class_id=cls.id,
            content="Introduction to photosynthesis.",
            topics=["photosynthesis"],
        )
        knowledge = get_assumed_knowledge(session, cls.id)
        assert knowledge["photosynthesis"]["depth"] == 1, (
            "First mention should be depth 1"
        )
        assert knowledge["photosynthesis"]["mention_count"] == 1

        # -- Lesson 2: revisit photosynthesis (depth 2) -------------------
        log_lesson(
            session,
            class_id=cls.id,
            content="Deeper dive into photosynthesis reactions.",
            topics=["photosynthesis"],
        )
        knowledge = get_assumed_knowledge(session, cls.id)
        assert knowledge["photosynthesis"]["depth"] == 2, (
            "Second mention should be depth 2"
        )
        assert knowledge["photosynthesis"]["mention_count"] == 2

        # -- Lesson 3: introduce cell division (depth 1) ------------------
        # photosynthesis should stay at depth 2
        log_lesson(
            session,
            class_id=cls.id,
            content="Introduction to cell division and mitosis.",
            topics=["cell division"],
        )
        knowledge = get_assumed_knowledge(session, cls.id)
        assert knowledge["photosynthesis"]["depth"] == 2, (
            "Photosynthesis depth should remain 2 after unrelated lesson"
        )
        assert knowledge["photosynthesis"]["mention_count"] == 2, (
            "Photosynthesis mention_count should remain 2"
        )
        assert knowledge["cell division"]["depth"] == 1, (
            "Cell division should start at depth 1"
        )
        assert knowledge["cell division"]["mention_count"] == 1


# ---------------------------------------------------------------------------
# 4. Error handling -- invalid class
# ---------------------------------------------------------------------------

class TestErrorHandlingInvalidClass:
    """
    Accessing or logging against a non-existent class should be handled
    gracefully without crashing.
    """

    def test_get_class_with_invalid_id(self, db_env):
        engine, session, db_path = db_env

        result = get_class(session, class_id=99999)
        assert result is None, (
            "get_class should return None for a non-existent class ID"
        )

    def test_log_lesson_with_invalid_class_id(self, db_env):
        engine, session, db_path = db_env

        # Logging to a non-existent class_id should raise an IntegrityError
        # because of the foreign-key constraint (class_id references classes.id).
        # Enable SQLite foreign key enforcement for this session.
        session.execute(
            __import__("sqlalchemy").text("PRAGMA foreign_keys = ON")
        )

        with pytest.raises(Exception):
            log_lesson(
                session,
                class_id=99999,
                content="This lesson has no valid class.",
                topics=["orphan"],
            )
        # Roll back so the session is usable for teardown
        session.rollback()

    def test_get_assumed_knowledge_invalid_class(self, db_env):
        engine, session, db_path = db_env

        knowledge = get_assumed_knowledge(session, class_id=99999)
        assert knowledge == {}, (
            "get_assumed_knowledge should return empty dict for non-existent class"
        )


# ---------------------------------------------------------------------------
# 5. list_classes with data (lesson_count and quiz_count)
# ---------------------------------------------------------------------------

class TestListClassesWithData:
    """
    Verify that list_classes returns correct lesson_count and quiz_count
    for each class.
    """

    def test_list_classes_with_data(self, db_env):
        engine, session, db_path = db_env

        # -- Create two classes -------------------------------------------
        cls_a = create_class(session, name="Algebra I", subject="Math")
        cls_b = create_class(session, name="Geometry", subject="Math")

        # -- Log different numbers of lessons -----------------------------
        # Class A: 3 lessons
        for i in range(3):
            log_lesson(
                session,
                class_id=cls_a.id,
                content=f"Algebra lesson {i + 1}",
                topics=["algebra"],
            )

        # Class B: 1 lesson
        log_lesson(
            session,
            class_id=cls_b.id,
            content="Intro to geometry angles",
            topics=["angles"],
        )

        # -- Create quizzes for each class --------------------------------
        # Class A: 2 quizzes
        for i in range(2):
            q = Quiz(
                title=f"Algebra Quiz {i + 1}",
                class_id=cls_a.id,
                status="generated",
            )
            session.add(q)
        session.commit()

        # Class B: 1 quiz
        q = Quiz(title="Geometry Quiz 1", class_id=cls_b.id, status="generated")
        session.add(q)
        session.commit()

        # -- Verify list_classes output -----------------------------------
        classes_info = list_classes(session)

        # Build a lookup by name for easier assertions
        by_name = {c["name"]: c for c in classes_info}

        assert "Algebra I" in by_name, "Algebra I should appear in list_classes"
        assert "Geometry" in by_name, "Geometry should appear in list_classes"

        assert by_name["Algebra I"]["lesson_count"] == 3, (
            "Algebra I should have 3 lessons"
        )
        assert by_name["Algebra I"]["quiz_count"] == 2, (
            "Algebra I should have 2 quizzes"
        )

        assert by_name["Geometry"]["lesson_count"] == 1, (
            "Geometry should have 1 lesson"
        )
        assert by_name["Geometry"]["quiz_count"] == 1, (
            "Geometry should have 1 quiz"
        )

    def test_list_classes_empty(self, db_env):
        """list_classes on a fresh DB should return an empty list."""
        engine, session, db_path = db_env

        classes_info = list_classes(session)
        assert classes_info == [], (
            "list_classes should return [] when no classes exist"
        )


# ---------------------------------------------------------------------------
# Standalone runner (for running without pytest)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
