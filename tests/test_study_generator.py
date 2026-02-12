"""
Tests for QuizWeaver study material generator.

Covers all four material types, quiz-based generation, topic-based generation,
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
    StudyCard,
    get_engine,
    get_session,
)
from src.study_generator import generate_study_material


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
        style_profile=json.dumps({"grade_level": "7th Grade"}),
    )
    session.add(quiz)
    session.commit()

    q1 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q1",
        text="What is photosynthesis?",
        points=5.0,
        data=json.dumps(
            {
                "type": "mc",
                "text": "What is photosynthesis?",
                "options": ["Making food from light", "Breathing", "Eating", "Sleeping"],
                "correct_index": 0,
            }
        ),
    )
    session.add(q1)
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
    """Test config using mock provider."""
    return {
        "llm": {"provider": "mock"},
        "paths": {"database_file": ":memory:"},
    }


# --- Test each material type ---


class TestGenerateFlashcards:
    def test_generates_flashcard_set(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_study_material(session, class_id, "flashcard", config, topic="photosynthesis")
        assert result is not None
        assert result.material_type == "flashcard"
        assert result.status == "generated"
        cards = session.query(StudyCard).filter_by(study_set_id=result.id).all()
        assert len(cards) > 0

    def test_flashcard_from_quiz(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_study_material(session, class_id, "flashcard", config, quiz_id=quiz_id)
        assert result is not None
        assert result.quiz_id == quiz_id

    def test_flashcard_cards_have_front_back(self, db_session, config):
        session, class_id, quiz_id = db_session
        result = generate_study_material(session, class_id, "flashcard", config, topic="cells")
        cards = session.query(StudyCard).filter_by(study_set_id=result.id).order_by(StudyCard.sort_order).all()
        for card in cards:
            assert card.front is not None and card.front != ""
            assert card.back is not None and card.back != ""
            assert card.card_type == "flashcard"


class TestGenerateStudyGuide:
    def test_generates_study_guide(self, db_session, config):
        session, class_id, _ = db_session
        result = generate_study_material(session, class_id, "study_guide", config, topic="evolution")
        assert result is not None
        assert result.material_type == "study_guide"
        assert result.status == "generated"
        cards = session.query(StudyCard).filter_by(study_set_id=result.id).all()
        assert len(cards) > 0

    def test_study_guide_sections_have_key_points(self, db_session, config):
        session, class_id, _ = db_session
        result = generate_study_material(session, class_id, "study_guide", config, topic="genetics")
        cards = session.query(StudyCard).filter_by(study_set_id=result.id).all()
        for card in cards:
            assert card.card_type == "section"
            data = json.loads(card.data) if card.data else {}
            assert "key_points" in data


class TestGenerateVocabulary:
    def test_generates_vocabulary_list(self, db_session, config):
        session, class_id, _ = db_session
        result = generate_study_material(session, class_id, "vocabulary", config, topic="cell division")
        assert result is not None
        assert result.material_type == "vocabulary"
        cards = session.query(StudyCard).filter_by(study_set_id=result.id).all()
        assert len(cards) > 0

    def test_vocabulary_cards_have_extras(self, db_session, config):
        session, class_id, _ = db_session
        result = generate_study_material(session, class_id, "vocabulary", config, topic="respiration")
        cards = session.query(StudyCard).filter_by(study_set_id=result.id).all()
        for card in cards:
            assert card.card_type == "term"
            data = json.loads(card.data) if card.data else {}
            assert "example" in data
            assert "part_of_speech" in data


class TestGenerateReviewSheet:
    def test_generates_review_sheet(self, db_session, config):
        session, class_id, _ = db_session
        result = generate_study_material(session, class_id, "review_sheet", config, topic="ecosystems")
        assert result is not None
        assert result.material_type == "review_sheet"
        cards = session.query(StudyCard).filter_by(study_set_id=result.id).all()
        assert len(cards) > 0

    def test_review_sheet_items_have_type(self, db_session, config):
        session, class_id, _ = db_session
        result = generate_study_material(session, class_id, "review_sheet", config, topic="forces")
        cards = session.query(StudyCard).filter_by(study_set_id=result.id).all()
        for card in cards:
            assert card.card_type == "fact"
            data = json.loads(card.data) if card.data else {}
            assert "type" in data


# --- Title / config tests ---


class TestStudySetMetadata:
    def test_custom_title(self, db_session, config):
        session, class_id, _ = db_session
        result = generate_study_material(
            session, class_id, "flashcard", config, topic="mitosis", title="Chapter 3 Flashcards"
        )
        assert result.title == "Chapter 3 Flashcards"

    def test_auto_generated_title(self, db_session, config):
        session, class_id, _ = db_session
        result = generate_study_material(session, class_id, "vocabulary", config, topic="genetics")
        assert "Vocabulary" in result.title

    def test_config_stored_as_json(self, db_session, config):
        session, class_id, _ = db_session
        result = generate_study_material(session, class_id, "flashcard", config, topic="energy")
        stored = json.loads(result.config)
        assert stored["material_type"] == "flashcard"
        assert stored["provider"] == "mock"


# --- Error handling ---


class TestErrorHandling:
    def test_invalid_class_id(self, db_session, config):
        session, _, _ = db_session
        result = generate_study_material(session, 9999, "flashcard", config, topic="test")
        assert result is None

    def test_invalid_material_type(self, db_session, config):
        session, class_id, _ = db_session
        result = generate_study_material(session, class_id, "invalid_type", config, topic="test")
        assert result is None

    def test_invalid_quiz_id(self, db_session, config):
        session, class_id, _ = db_session
        result = generate_study_material(session, class_id, "flashcard", config, quiz_id=9999)
        assert result is None
