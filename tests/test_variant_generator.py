"""
Tests for QuizWeaver reading-level variant generator.

Covers variant generation at each reading level, question preservation,
parent linkage, and error handling.
"""

import json
import os
import tempfile

import pytest

from src.database import (
    Base, Class, Quiz, Question,
    get_engine, get_session,
)
from src.variant_generator import generate_variant, READING_LEVELS


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
        style_profile=json.dumps({"grade_level": "7th Grade", "provider": "mock"}),
    )
    session.add(quiz)
    session.commit()

    for i in range(3):
        q = Question(
            quiz_id=quiz.id,
            question_type="mc",
            title=f"Q{i+1}",
            text=f"What is photosynthesis concept {i+1}?",
            points=5.0,
            sort_order=i,
            data=json.dumps({
                "type": "mc",
                "text": f"What is photosynthesis concept {i+1}?",
                "options": ["A", "B", "C", "D"],
                "correct_index": i % 4,
            }),
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


class TestVariantGeneration:
    def test_generate_ell_variant(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_variant(session, quiz_id, "ell", config)
        assert result is not None
        assert result.reading_level == "ell"
        assert result.parent_quiz_id == quiz_id
        assert result.status == "generated"

    def test_generate_below_grade_variant(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_variant(session, quiz_id, "below_grade", config)
        assert result is not None
        assert result.reading_level == "below_grade"
        assert result.parent_quiz_id == quiz_id

    def test_generate_on_grade_variant(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_variant(session, quiz_id, "on_grade", config)
        assert result is not None
        assert result.reading_level == "on_grade"

    def test_generate_advanced_variant(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_variant(session, quiz_id, "advanced", config)
        assert result is not None
        assert result.reading_level == "advanced"

    def test_question_count_matches_source(self, db_session, config):
        session, class_id, quiz_id = db_session
        source_count = session.query(Question).filter_by(quiz_id=quiz_id).count()
        result = generate_variant(session, quiz_id, "ell", config)
        variant_count = session.query(Question).filter_by(quiz_id=result.id).count()
        assert variant_count == source_count

    def test_variant_has_parent_quiz_id(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_variant(session, quiz_id, "ell", config)
        assert result.parent_quiz_id == quiz_id

    def test_variant_inherits_class_id(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_variant(session, quiz_id, "ell", config)
        source = session.query(Quiz).filter_by(id=quiz_id).first()
        assert result.class_id == source.class_id

    def test_custom_title(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_variant(session, quiz_id, "ell", config, title="My ELL Version")
        assert result.title == "My ELL Version"

    def test_auto_generated_title(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_variant(session, quiz_id, "advanced", config)
        assert "Advanced" in result.title
        assert "Variant" in result.title


class TestVariantErrors:
    def test_invalid_reading_level(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_variant(session, quiz_id, "nonexistent", config)
        assert result is None

    def test_invalid_quiz_id(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_variant(session, 9999, "ell", config)
        assert result is None

    def test_quiz_with_no_questions(self, db_session, config):
        session, class_id, quiz_id = db_session
        # Create empty quiz
        empty_quiz = Quiz(title="Empty", class_id=class_id, status="generated")
        session.add(empty_quiz)
        session.commit()
        result = generate_variant(session, empty_quiz.id, "ell", config)
        assert result is None
