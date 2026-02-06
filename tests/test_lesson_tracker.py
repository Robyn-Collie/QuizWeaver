"""
Tests for the lesson tracker module (src/lesson_tracker.py).

Covers topic extraction, lesson logging, assumed knowledge tracking,
and lesson querying with filters.

Run with: python -m pytest tests/test_lesson_tracker.py -v
"""

import json
import os
import sys
import tempfile
from datetime import date, timedelta

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import get_engine, init_db, get_session, Class, LessonLog
from src.lesson_tracker import (
    extract_topics,
    log_lesson,
    get_recent_lessons,
    list_lessons,
    update_assumed_knowledge,
    get_assumed_knowledge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    """Create a temporary SQLite database, yield a session, then clean up.

    Uses engine.dispose() before file removal to avoid Windows file-lock
    issues with SQLite.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()

    engine = get_engine(tmp_path)
    init_db(engine)
    session = get_session(engine)

    yield session

    session.close()
    engine.dispose()
    try:
        os.remove(tmp_path)
    except OSError:
        pass  # Windows may still hold the file briefly


@pytest.fixture
def sample_class(db_session):
    """Insert and return a Class record for use in tests."""
    cls = Class(
        name="7th Grade Science - Block A",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1", "SOL 7.2"]),
        config=json.dumps({}),
    )
    db_session.add(cls)
    db_session.commit()
    return cls


# ---------------------------------------------------------------------------
# 1 - extract_topics: found
# ---------------------------------------------------------------------------

def test_extract_topics_found():
    """Text containing 'photosynthesis' and 'cell division' should extract both."""
    text = (
        "Today we studied photosynthesis in depth and also introduced "
        "cell division as a preview for next week."
    )
    topics = extract_topics(text)
    assert "photosynthesis" in topics
    assert "cell division" in topics


# ---------------------------------------------------------------------------
# 2 - extract_topics: case insensitive
# ---------------------------------------------------------------------------

def test_extract_topics_case_insensitive():
    """Uppercase 'PHOTOSYNTHESIS' should still match the known topic."""
    text = "The students reviewed PHOTOSYNTHESIS before the lab."
    topics = extract_topics(text)
    assert "photosynthesis" in topics


# ---------------------------------------------------------------------------
# 3 - extract_topics: no known topics
# ---------------------------------------------------------------------------

def test_extract_topics_none():
    """Text with no known science topics should return an empty list."""
    text = "The class went over homework policies and discussed the field trip."
    topics = extract_topics(text)
    assert topics == []


# ---------------------------------------------------------------------------
# 4 - log_lesson: basic creation
# ---------------------------------------------------------------------------

def test_log_lesson_with_text(db_session, sample_class):
    """log_lesson should create a LessonLog with the given content."""
    lesson = log_lesson(
        db_session,
        class_id=sample_class.id,
        content="We covered the water cycle today.",
    )

    assert isinstance(lesson, LessonLog)
    assert lesson.id is not None
    assert lesson.content == "We covered the water cycle today."
    assert lesson.class_id == sample_class.id

    # Verify it is persisted in the database
    found = db_session.query(LessonLog).filter_by(id=lesson.id).first()
    assert found is not None
    assert found.content == lesson.content


# ---------------------------------------------------------------------------
# 5 - log_lesson: auto-extracts topics
# ---------------------------------------------------------------------------

def test_log_lesson_auto_extracts_topics(db_session, sample_class):
    """When topics=None, log_lesson should auto-extract from content."""
    lesson = log_lesson(
        db_session,
        class_id=sample_class.id,
        content="Today's lesson focused on photosynthesis and how plants use light.",
    )

    stored_topics = json.loads(lesson.topics)
    assert "photosynthesis" in stored_topics


# ---------------------------------------------------------------------------
# 6 - log_lesson: explicit topic override
# ---------------------------------------------------------------------------

def test_log_lesson_with_topic_override(db_session, sample_class):
    """Providing explicit topics should override auto-extraction."""
    lesson = log_lesson(
        db_session,
        class_id=sample_class.id,
        content="Today's lesson focused on photosynthesis.",
        topics=["custom topic alpha", "custom topic beta"],
    )

    stored_topics = json.loads(lesson.topics)
    assert stored_topics == ["custom topic alpha", "custom topic beta"]
    # photosynthesis should NOT appear because we overrode
    assert "photosynthesis" not in stored_topics


# ---------------------------------------------------------------------------
# 7 - log_lesson: updates assumed knowledge
# ---------------------------------------------------------------------------

def test_log_lesson_updates_assumed_knowledge(db_session, sample_class):
    """After logging a lesson with a known topic, assumed_knowledge should update."""
    log_lesson(
        db_session,
        class_id=sample_class.id,
        content="Students learned about mitosis and cell division.",
    )

    knowledge = get_assumed_knowledge(db_session, sample_class.id)
    assert "mitosis" in knowledge
    assert knowledge["mitosis"]["depth"] == 1
    assert knowledge["mitosis"]["mention_count"] == 1


# ---------------------------------------------------------------------------
# 8 - assumed knowledge: depth increment
# ---------------------------------------------------------------------------

def test_assumed_knowledge_depth_increment(db_session, sample_class):
    """Logging the same topic twice should increment depth to 2."""
    log_lesson(
        db_session,
        class_id=sample_class.id,
        content="Introduction to genetics.",
    )
    log_lesson(
        db_session,
        class_id=sample_class.id,
        content="Continued discussion of genetics and heredity.",
    )

    knowledge = get_assumed_knowledge(db_session, sample_class.id)
    assert knowledge["genetics"]["depth"] == 2
    assert knowledge["genetics"]["mention_count"] == 2


# ---------------------------------------------------------------------------
# 9 - assumed knowledge: max depth capped at 5
# ---------------------------------------------------------------------------

def test_assumed_knowledge_max_depth(db_session, sample_class):
    """Logging the same topic 10 times should cap depth at 5."""
    for i in range(10):
        log_lesson(
            db_session,
            class_id=sample_class.id,
            content=f"Session {i + 1} about evolution and natural selection.",
        )

    knowledge = get_assumed_knowledge(db_session, sample_class.id)
    assert knowledge["evolution"]["depth"] == 5, (
        "Depth should be capped at 5 even after 10 lessons"
    )
    assert knowledge["evolution"]["mention_count"] == 10


# ---------------------------------------------------------------------------
# 10 - get_recent_lessons
# ---------------------------------------------------------------------------

def test_get_recent_lessons(db_session, sample_class):
    """get_recent_lessons should return lessons within the specified window."""
    # Log a lesson for today (default date)
    log_lesson(
        db_session,
        class_id=sample_class.id,
        content="Recent lesson on ecosystems.",
    )
    # Log a lesson dated 30 days ago (outside 14-day default window)
    log_lesson(
        db_session,
        class_id=sample_class.id,
        content="Old lesson on weather.",
        lesson_date=date.today() - timedelta(days=30),
    )

    recent = get_recent_lessons(db_session, sample_class.id, days=14)
    assert len(recent) == 1
    assert recent[0].content == "Recent lesson on ecosystems."

    # Widen the window to capture the old lesson as well
    all_recent = get_recent_lessons(db_session, sample_class.id, days=60)
    assert len(all_recent) == 2


# ---------------------------------------------------------------------------
# 11 - list_lessons: filter by topic
# ---------------------------------------------------------------------------

def test_list_lessons_with_topic_filter(db_session, sample_class):
    """list_lessons should return only lessons matching a topic filter."""
    log_lesson(
        db_session,
        class_id=sample_class.id,
        content="Today we covered photosynthesis.",
    )
    log_lesson(
        db_session,
        class_id=sample_class.id,
        content="Today we reviewed gravity and forces.",
    )

    photo_lessons = list_lessons(
        db_session, sample_class.id, filters={"topic": "photosynthesis"}
    )
    assert len(photo_lessons) == 1
    assert "photosynthesis" in photo_lessons[0].content

    gravity_lessons = list_lessons(
        db_session, sample_class.id, filters={"topic": "gravity"}
    )
    assert len(gravity_lessons) == 1
    assert "gravity" in gravity_lessons[0].content


# ---------------------------------------------------------------------------
# 12 - list_lessons: filter by last_days
# ---------------------------------------------------------------------------

def test_list_lessons_with_last_days_filter(db_session, sample_class):
    """list_lessons with last_days filter should exclude older lessons."""
    # Recent lesson (today)
    log_lesson(
        db_session,
        class_id=sample_class.id,
        content="Fresh lesson on circuits.",
    )
    # Old lesson (20 days ago)
    log_lesson(
        db_session,
        class_id=sample_class.id,
        content="Old lesson on plate tectonics.",
        lesson_date=date.today() - timedelta(days=20),
    )

    # Filter to last 7 days - should only get the recent one
    filtered = list_lessons(
        db_session, sample_class.id, filters={"last_days": 7}
    )
    assert len(filtered) == 1
    assert filtered[0].content == "Fresh lesson on circuits."

    # Filter to last 30 days - should get both
    all_filtered = list_lessons(
        db_session, sample_class.id, filters={"last_days": 30}
    )
    assert len(all_filtered) == 2
