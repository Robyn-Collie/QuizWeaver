"""
Tests for QuizWeaver re-teach suggestion generator.

Covers suggestion generation, field validation, focus topics,
max limits, mock provider, and error handling.
"""

import json
import os
import tempfile
from datetime import date

import pytest

from src.database import (
    Base, Class, PerformanceData,
    get_engine, get_session,
)
from src.lesson_tracker import log_lesson
from src.reteach_generator import generate_reteach_suggestions


@pytest.fixture
def db_session():
    """Create a temporary database with gap data."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Test Science",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    # Teach topics to set expected depth
    log_lesson(session, cls.id, "Intro to photosynthesis",
               topics=["photosynthesis"])
    log_lesson(session, cls.id, "Genetics basics",
               topics=["genetics"])

    # Add performance data with gaps (scores below expectations)
    records = [
        PerformanceData(
            class_id=cls.id, topic="photosynthesis",
            avg_score=0.25, source="manual_entry",
            sample_size=25, date=date.today(),
        ),
        PerformanceData(
            class_id=cls.id, topic="genetics",
            avg_score=0.30, source="manual_entry",
            sample_size=25, date=date.today(),
        ),
    ]
    for r in records:
        session.add(r)
    session.commit()

    yield session, cls.id

    session.close()
    engine.dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def config():
    return {"llm": {"provider": "mock"}}


class TestReteachGeneration:
    def test_generates_suggestions(self, db_session, config):
        session, class_id = db_session
        result = generate_reteach_suggestions(session, class_id, config)
        assert result is not None
        assert len(result) >= 1

    def test_suggestions_have_required_fields(self, db_session, config):
        session, class_id = db_session
        result = generate_reteach_suggestions(session, class_id, config)
        required = [
            "topic", "gap_severity", "current_score", "target_score",
            "lesson_plan", "activities", "estimated_duration",
            "resources", "assessment_suggestion", "priority",
        ]
        for s in result:
            for field in required:
                assert field in s, f"Missing field: {field}"

    def test_focus_topics(self, db_session, config):
        session, class_id = db_session
        result = generate_reteach_suggestions(
            session, class_id, config,
            focus_topics=["photosynthesis"],
        )
        assert result is not None
        topics = [s["topic"] for s in result]
        assert "photosynthesis" in topics

    def test_max_suggestions_limit(self, db_session, config):
        session, class_id = db_session
        result = generate_reteach_suggestions(
            session, class_id, config, max_suggestions=1,
        )
        assert len(result) <= 1

    def test_mock_provider_returns_data(self, db_session, config):
        session, class_id = db_session
        result = generate_reteach_suggestions(session, class_id, config)
        assert result is not None
        for s in result:
            assert isinstance(s["activities"], list)
            assert isinstance(s["resources"], list)
            assert s["lesson_plan"]  # non-empty string


class TestReteachErrors:
    def test_invalid_class_id(self, config):
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        engine = get_engine(db_path)
        Base.metadata.create_all(engine)
        session = get_session(engine)

        result = generate_reteach_suggestions(session, 9999, config)
        assert result is None

        session.close()
        engine.dispose()
        os.close(db_fd)
        try:
            os.unlink(db_path)
        except PermissionError:
            pass

    def test_no_gap_data(self, config):
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        engine = get_engine(db_path)
        Base.metadata.create_all(engine)
        session = get_session(engine)

        cls = Class(
            name="Empty Class", grade_level="7th", subject="Science",
            standards=json.dumps([]), config=json.dumps({}),
        )
        session.add(cls)
        session.commit()

        result = generate_reteach_suggestions(session, cls.id, config)
        assert result is not None
        assert result == []

        session.close()
        engine.dispose()
        os.close(db_fd)
        try:
            os.unlink(db_path)
        except PermissionError:
            pass

    def test_all_topics_on_track(self, config):
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        engine = get_engine(db_path)
        Base.metadata.create_all(engine)
        session = get_session(engine)

        cls = Class(
            name="Good Class", grade_level="7th", subject="Science",
            standards=json.dumps([]), config=json.dumps({}),
        )
        session.add(cls)
        session.commit()

        # All scores at or above expectation
        record = PerformanceData(
            class_id=cls.id, topic="photosynthesis",
            avg_score=0.95, source="manual_entry",
            sample_size=25, date=date.today(),
        )
        session.add(record)
        session.commit()

        result = generate_reteach_suggestions(session, cls.id, config)
        assert result is not None
        assert result == []

        session.close()
        engine.dispose()
        os.close(db_fd)
        try:
            os.unlink(db_path)
        except PermissionError:
            pass
