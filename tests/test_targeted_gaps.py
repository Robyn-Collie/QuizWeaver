"""
Targeted tests for specific gaps identified in project instructions.

This test file addresses SPECIFIC gaps called out for:
  1. Classroom module (src/classroom.py)
     - Deleting a class with associated quizzes
     - Creating classes with duplicate names
     - Setting active class with invalid class_id

  2. Lesson tracker module (src/lesson_tracker.py)
     - Logging lesson with empty/blank content
     - Listing lessons with invalid date range (from > to)
     - Getting recent lessons with limit=0 (days=0)

  3. Cost tracking module (src/cost_tracking.py)
     - Logging cost with negative values
     - Getting cost summary with empty database
     - Formatting cost report with zero costs

Run with: python -m pytest tests/test_targeted_gaps.py -v
"""

import json
import os
import sys
import tempfile
from datetime import date, timedelta

import pytest
import yaml

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.classroom import (
    create_class,
    delete_class,
    set_active_class,
)
from src.cost_tracking import (
    format_cost_report,
    get_cost_summary,
    log_api_call,
)
from src.database import (
    Class,
    LessonLog,
    Question,
    Quiz,
    get_engine,
    get_session,
    init_db,
)
from src.lesson_tracker import (
    get_recent_lessons,
    list_lessons,
    log_lesson,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    """
    Provide a temporary SQLite database with all tables created.

    Yields a (engine, session) tuple. After the test, the session and engine
    are closed, and the temporary file is removed. engine.dispose() is
    called before deletion to avoid Windows file-locking errors.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()  # Close handle immediately so SQLAlchemy can use the file

    engine = get_engine(tmp_path)
    init_db(engine)
    session = get_session(engine)

    yield engine, session

    # Teardown
    session.close()
    engine.dispose()
    try:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except OSError:
        pass  # Windows may still hold a lock; ignore cleanup errors


@pytest.fixture()
def tmp_config():
    """
    Provide a temporary config.yaml file with minimal content.

    Yields the file path. The file is removed after the test.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w", encoding="utf-8")
    yaml.dump({"llm": {"provider": "mock"}, "paths": {}}, tmp, default_flow_style=False)
    tmp.close()

    yield tmp.name

    try:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
    except OSError:
        pass


@pytest.fixture()
def tmp_cost_log():
    """
    Provide a temporary cost log file.

    Yields the file path. The file is removed after the test.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w", encoding="utf-8")
    tmp.close()

    yield tmp.name

    try:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Classroom Module Tests - Targeted Gaps
# ---------------------------------------------------------------------------


def test_delete_class_with_quizzes(db):
    """
    Test that deleting a class with associated quizzes sets quiz.class_id to NULL.

    Gap: Verify that quizzes are not deleted, only have their class_id set to NULL.
    """
    engine, session = db

    # Create class
    cls = create_class(session, "Block A", "8th Grade", "Science")
    class_id = cls.id

    # Create quiz associated with this class
    quiz = Quiz(title="Quiz 1", class_id=class_id)
    session.add(quiz)
    session.commit()
    quiz_id = quiz.id

    # Create question for the quiz
    question = Question(
        quiz_id=quiz_id,
        question_type="mc",
        title="Q1",
        text="What is photosynthesis?",
        points=1.0,
        data=json.dumps({"options": ["A", "B", "C"], "correct_index": 0}),
    )
    session.add(question)
    session.commit()

    # Delete the class
    result = delete_class(session, class_id)
    assert result is True, "delete_class should return True"

    # Verify class is deleted
    deleted_class = session.query(Class).filter_by(id=class_id).first()
    assert deleted_class is None, "Class should be deleted"

    # Verify quiz still exists but class_id is NULL
    remaining_quiz = session.query(Quiz).filter_by(id=quiz_id).first()
    assert remaining_quiz is not None, "Quiz should still exist"
    assert remaining_quiz.class_id is None, "Quiz class_id should be NULL"

    # Verify question still exists
    remaining_question = session.query(Question).filter_by(quiz_id=quiz_id).first()
    assert remaining_question is not None, "Question should still exist"

    print("[PASS] Deleting class with quizzes sets class_id to NULL correctly")


def test_create_classes_with_duplicate_names(db):
    """
    Test that duplicate class names are allowed (names are not unique).

    Gap: Verify that multiple classes can have the same name.
    """
    engine, session = db

    # Create first class
    cls1 = create_class(session, "Block A", "7th Grade", "Science")
    assert cls1.id is not None

    # Create second class with same name but different grade
    cls2 = create_class(session, "Block A", "8th Grade", "Math")
    assert cls2.id is not None

    # Create third class with exact same name and grade
    cls3 = create_class(session, "Block A", "7th Grade", "Science")
    assert cls3.id is not None

    # Verify all three classes exist with different IDs
    assert cls1.id != cls2.id != cls3.id, "Classes should have unique IDs"

    # Verify all have the same name
    assert cls1.name == cls2.name == cls3.name == "Block A"

    # Query all classes
    all_classes = session.query(Class).filter_by(name="Block A").all()
    assert len(all_classes) == 3, "Should have 3 classes with name 'Block A'"

    print("[PASS] Duplicate class names are allowed")


def test_set_active_class_with_invalid_id(tmp_config):
    """
    Test that set_active_class writes invalid class_id to config (no validation).

    Gap: set_active_class does not validate if class exists - it just writes to config.
    This test verifies that behavior.
    """
    config_path = tmp_config

    # Set active class to invalid ID (9999)
    result = set_active_class(config_path, 9999)
    assert result is True, "set_active_class should return True (writes to config)"

    # Read config and verify the invalid ID was written
    with open(config_path) as f:
        config = yaml.safe_load(f)

    assert config.get("active_class_id") == 9999, "Invalid class_id should be written to config"

    # Set to negative ID
    result = set_active_class(config_path, -1)
    assert result is True, "set_active_class should return True for negative ID"

    with open(config_path) as f:
        config = yaml.safe_load(f)

    assert config.get("active_class_id") == -1, "Negative class_id should be written to config"

    print("[PASS] set_active_class accepts invalid class_id (no validation)")


# ---------------------------------------------------------------------------
# Lesson Tracker Module Tests - Targeted Gaps
# ---------------------------------------------------------------------------


def test_log_lesson_with_empty_content(db):
    """
    Test logging a lesson with empty/blank content.

    Gap: Verify that empty content is allowed (no validation error).
    """
    engine, session = db

    # Create class
    cls = create_class(session, "Block A", "7th Grade", "Science")

    # Log lesson with empty content
    lesson1 = log_lesson(session, cls.id, "")
    assert lesson1.id is not None, "Lesson with empty content should be created"
    assert lesson1.content == "", "Content should be empty string"
    assert lesson1.topics == "[]", "Topics should be empty array"

    # Log lesson with whitespace-only content
    lesson2 = log_lesson(session, cls.id, "   \n\t   ")
    assert lesson2.id is not None, "Lesson with whitespace should be created"
    assert lesson2.content == "   \n\t   ", "Content should preserve whitespace"

    # Query all lessons
    all_lessons = session.query(LessonLog).filter_by(class_id=cls.id).all()
    assert len(all_lessons) == 2, "Both lessons should be created"

    print("[PASS] Empty/blank content is allowed in log_lesson")


def test_list_lessons_with_invalid_date_range(db):
    """
    Test list_lessons with invalid date range (from > to).

    Gap: Verify behavior when date_from is after date_to.
    """
    engine, session = db

    # Create class
    cls = create_class(session, "Block A", "7th Grade", "Science")

    # Log some lessons on different dates
    today = date.today()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    log_lesson(session, cls.id, "Lesson 1", lesson_date=week_ago)
    log_lesson(session, cls.id, "Lesson 2", lesson_date=yesterday)
    log_lesson(session, cls.id, "Lesson 3", lesson_date=today)

    # Query with invalid date range (from > to)
    filters = {
        "date_from": today,
        "date_to": week_ago,  # Before date_from
    }
    lessons = list_lessons(session, cls.id, filters)

    # Should return empty list (no lessons match the impossible date range)
    assert len(lessons) == 0, "Invalid date range should return empty list"

    # Verify with another invalid range
    filters2 = {
        "date_from": yesterday,
        "date_to": week_ago,
    }
    lessons2 = list_lessons(session, cls.id, filters2)
    assert len(lessons2) == 0, "Another invalid date range should return empty list"

    # Verify valid range works
    filters3 = {
        "date_from": week_ago,
        "date_to": today,
    }
    lessons3 = list_lessons(session, cls.id, filters3)
    assert len(lessons3) == 3, "Valid date range should return all lessons"

    print("[PASS] Invalid date range (from > to) returns empty list")


def test_get_recent_lessons_with_zero_days(db):
    """
    Test get_recent_lessons with days=0.

    Gap: Verify behavior with days=0 (should look back 0 days = today only).
    """
    engine, session = db

    # Create class
    cls = create_class(session, "Block A", "7th Grade", "Science")

    # Log lessons on different dates
    today = date.today()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    log_lesson(session, cls.id, "Old lesson", lesson_date=week_ago)
    log_lesson(session, cls.id, "Yesterday lesson", lesson_date=yesterday)
    log_lesson(session, cls.id, "Today lesson", lesson_date=today)

    # Query with days=0 (should only get lessons from today)
    recent = get_recent_lessons(session, cls.id, days=0)

    # Should only return today's lesson
    assert len(recent) == 1, "days=0 should return only today's lessons"
    assert recent[0].content == "Today lesson", "Should be today's lesson"

    # Verify with days=1 (should get today and yesterday)
    recent1 = get_recent_lessons(session, cls.id, days=1)
    assert len(recent1) == 2, "days=1 should return lessons from today and yesterday"

    print("[PASS] get_recent_lessons with days=0 returns only today's lessons")


def test_get_recent_lessons_with_negative_days(db):
    """
    Test get_recent_lessons with negative days value.

    Extra gap: Verify behavior with negative days (should look to the future).
    """
    engine, session = db

    # Create class
    cls = create_class(session, "Block A", "7th Grade", "Science")

    # Log lessons on different dates
    today = date.today()
    yesterday = today - timedelta(days=1)

    log_lesson(session, cls.id, "Yesterday lesson", lesson_date=yesterday)
    log_lesson(session, cls.id, "Today lesson", lesson_date=today)

    # Query with negative days (threshold will be in the future)
    recent = get_recent_lessons(session, cls.id, days=-7)

    # Should return empty list (no lessons in the future)
    assert len(recent) == 0, "Negative days should return empty list"

    print("[PASS] get_recent_lessons with negative days returns empty list")


# ---------------------------------------------------------------------------
# Cost Tracking Module Tests - Targeted Gaps
# ---------------------------------------------------------------------------


def test_log_cost_with_negative_values(tmp_cost_log):
    """
    Test logging API call with negative token counts.

    Gap: Verify behavior with negative input/output tokens.
    """
    log_file = tmp_cost_log

    # Log with negative input tokens
    result1 = log_api_call("gemini", "gemini-1.5-flash", -100, 500, log_file=log_file)
    assert result1 is True, "log_api_call should succeed with negative input tokens"

    # Log with negative output tokens
    result2 = log_api_call("gemini", "gemini-1.5-flash", 1000, -200, log_file=log_file)
    assert result2 is True, "log_api_call should succeed with negative output tokens"

    # Log with negative cost
    result3 = log_api_call("gemini", "gemini-1.5-flash", 1000, 500, cost=-0.50, log_file=log_file)
    assert result3 is True, "log_api_call should succeed with negative cost"

    # Read back and verify
    summary = get_cost_summary(log_file)
    assert summary["total_calls"] == 3, "Should have 3 logged calls"

    # Note: The cost calculation will be negative, which is mathematically valid
    # The function doesn't validate, it just logs
    print("[PASS] log_api_call accepts negative values (no validation)")


def test_get_cost_summary_with_empty_database(tmp_cost_log):
    """
    Test get_cost_summary with empty/nonexistent log file.

    Gap: Verify behavior when no costs have been logged.
    """
    log_file = tmp_cost_log

    # Delete the file to simulate nonexistent log
    if os.path.exists(log_file):
        os.remove(log_file)

    # Get summary from nonexistent file
    summary = get_cost_summary(log_file)

    # Should return default empty summary
    assert summary["total_calls"] == 0, "Empty DB should have 0 calls"
    assert summary["total_cost"] == 0.0, "Empty DB should have 0 cost"
    assert summary["total_input_tokens"] == 0, "Empty DB should have 0 input tokens"
    assert summary["total_output_tokens"] == 0, "Empty DB should have 0 output tokens"
    assert summary["by_provider"] == {}, "Empty DB should have empty by_provider"
    assert summary["by_day"] == {}, "Empty DB should have empty by_day"

    print("[PASS] get_cost_summary with empty database returns default values")


def test_format_cost_report_with_zero_costs():
    """
    Test format_cost_report with zero costs (empty summary).

    Gap: Verify formatting when no API calls have been made.
    """
    # Create empty summary
    empty_summary = {
        "total_calls": 0,
        "total_cost": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "by_provider": {},
        "by_day": {},
    }

    report = format_cost_report(empty_summary)

    # Verify report contains expected fields
    assert "Total API calls: 0" in report, "Report should show 0 calls"
    assert "Total cost: $0.0000" in report, "Report should show $0.0000 cost"
    assert "Total input tokens: 0" in report, "Report should show 0 input tokens"
    assert "Total output tokens: 0" in report, "Report should show 0 output tokens"

    # Should not have provider or day sections
    assert "By Provider:" not in report, "Report should not have provider section"
    assert "By Day:" not in report, "Report should not have day section"

    # Should not have warning
    assert "[WARNING]" not in report, "Report should not have warning for zero cost"

    print("[PASS] format_cost_report handles zero costs correctly")


def test_format_cost_report_with_high_cost():
    """
    Test format_cost_report with cost exceeding $5.00.

    Extra gap: Verify warning is displayed for high costs.
    """
    high_cost_summary = {
        "total_calls": 100,
        "total_cost": 10.50,
        "total_input_tokens": 500000,
        "total_output_tokens": 250000,
        "by_provider": {"gemini": {"calls": 100, "cost": 10.50}},
        "by_day": {"2026-02-06": {"calls": 100, "cost": 10.50}},
    }

    report = format_cost_report(high_cost_summary)

    # Verify warning is present
    assert "[WARNING] Total cost exceeds $5.00!" in report, "Report should have warning for high cost"
    assert "Total cost: $10.5000" in report, "Report should show correct cost"

    # Verify provider and day sections are present
    assert "By Provider:" in report, "Report should have provider section"
    assert "gemini" in report, "Report should list gemini provider"
    assert "By Day:" in report, "Report should have day section"
    assert "2026-02-06" in report, "Report should list specific day"

    print("[PASS] format_cost_report shows warning for high costs")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
