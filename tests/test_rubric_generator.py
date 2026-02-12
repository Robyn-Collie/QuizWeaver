"""
Tests for QuizWeaver rubric generator.

Covers rubric generation, criterion creation, proficiency levels,
and error handling.
"""

import json
import os
import tempfile

import pytest

from src.database import (
    Base,
    Class,
    Question,
    Quiz,
    RubricCriterion,
    get_engine,
    get_session,
)
from src.rubric_generator import PROFICIENCY_LEVELS, generate_rubric


@pytest.fixture
def db_session():
    """Create a temporary database with test data."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed a class
    cls = Class(
        name="Test Science",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    # Seed a quiz with questions
    quiz = Quiz(
        title="Photosynthesis Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps(
            {
                "grade_level": "7th Grade",
                "cognitive_framework": "blooms",
                "sol_standards": ["SOL 7.1"],
            }
        ),
    )
    session.add(quiz)
    session.commit()

    for i in range(4):
        q = Question(
            quiz_id=quiz.id,
            question_type="mc",
            title=f"Q{i + 1}",
            text=f"Photosynthesis question {i + 1}?",
            points=5.0,
            sort_order=i,
            data=json.dumps(
                {
                    "type": "mc",
                    "text": f"Photosynthesis question {i + 1}?",
                    "options": ["A", "B", "C", "D"],
                    "correct_index": 0,
                    "cognitive_level": "Remember",
                    "cognitive_framework": "blooms",
                }
            ),
        )
        session.add(q)
    session.commit()

    yield session, cls.id, quiz.id

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


class TestRubricGeneration:
    def test_generates_rubric(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_rubric(session, quiz_id, config)
        assert result is not None
        assert result.status == "generated"
        assert result.quiz_id == quiz_id

    def test_rubric_has_criteria(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_rubric(session, quiz_id, config)
        criteria = session.query(RubricCriterion).filter_by(rubric_id=result.id).all()
        assert len(criteria) >= 4  # Mock returns 4-5 criteria

    def test_criteria_have_proficiency_levels(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_rubric(session, quiz_id, config)
        criteria = session.query(RubricCriterion).filter_by(rubric_id=result.id).all()
        for c in criteria:
            levels = json.loads(c.levels) if c.levels else []
            assert len(levels) == 4
            labels = [lv["label"] for lv in levels]
            for pl in PROFICIENCY_LEVELS:
                assert pl in labels

    def test_criteria_have_max_points(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_rubric(session, quiz_id, config)
        criteria = session.query(RubricCriterion).filter_by(rubric_id=result.id).all()
        for c in criteria:
            assert c.max_points is not None
            assert c.max_points > 0

    def test_custom_title(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_rubric(session, quiz_id, config, title="My Custom Rubric")
        assert result.title == "My Custom Rubric"

    def test_auto_generated_title(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_rubric(session, quiz_id, config)
        assert "Rubric" in result.title

    def test_config_stored(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_rubric(session, quiz_id, config)
        stored = json.loads(result.config)
        assert stored["quiz_id"] == quiz_id
        assert stored["provider"] == "mock"

    def test_criteria_sorted(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_rubric(session, quiz_id, config)
        criteria = (
            session.query(RubricCriterion).filter_by(rubric_id=result.id).order_by(RubricCriterion.sort_order).all()
        )
        for i, c in enumerate(criteria):
            assert c.sort_order == i


class TestRubricErrors:
    def test_invalid_quiz_id(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_rubric(session, 9999, config)
        assert result is None

    def test_quiz_with_no_questions(self, db_session, config):
        session, class_id, quiz_id = db_session
        empty_quiz = Quiz(title="Empty", class_id=class_id, status="generated")
        session.add(empty_quiz)
        session.commit()
        result = generate_rubric(session, empty_quiz.id, config)
        assert result is None
