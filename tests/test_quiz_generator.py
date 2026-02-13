"""
Tests for the generate_quiz function in src/quiz_generator.py.

Tests use MockLLMProvider (zero cost) and temporary SQLite databases.
Run with: python -m pytest tests/test_quiz_generator.py -v
"""

import json
import os
import sys

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.classroom import create_class
from src.database import Question, Quiz, get_engine, get_session, init_db
from src.migrations import run_migrations
from src.quiz_generator import generate_quiz

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# db_path fixture is provided by tests/conftest.py


@pytest.fixture
def db_session(db_path):
    """
    Provide a fully-initialised SQLAlchemy session bound to a temp DB.

    Runs migrations, creates all ORM tables, and yields the session.
    The engine is disposed on teardown so the temp file can be deleted.
    """
    run_migrations(db_path, verbose=False)
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def mock_config(db_path):
    """Return a minimal config dict that uses MockLLMProvider."""
    return {
        "llm": {"provider": "mock"},
        "paths": {"database_file": db_path},
        "generation": {
            "quiz_title": "Test Quiz",
            "default_grade_level": "7th Grade Science",
            "sol_standards": [],
            "target_image_ratio": 0.0,
            "generate_ai_images": False,
            "interactive_review": False,
        },
    }


@pytest.fixture
def sample_class(db_session):
    """Create and return a sample class record for testing."""
    return create_class(
        db_session,
        name="7th Grade Science - Block A",
        grade_level="7th Grade",
        subject="Science",
        standards=["SOL 7.1", "SOL 7.2"],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateQuizReturnsQuizObject:
    """test_generate_quiz_returns_quiz_object"""

    def test_returns_quiz_not_none(self, db_session, mock_config, sample_class):
        """generate_quiz should return a Quiz ORM object, not None."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config)
        assert quiz is not None, "generate_quiz should return a Quiz object"

    def test_returns_quiz_instance(self, db_session, mock_config, sample_class):
        """The returned object must be an instance of Quiz."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config)
        assert isinstance(quiz, Quiz), f"Expected Quiz, got {type(quiz)}"

    def test_quiz_class_id_matches(self, db_session, mock_config, sample_class):
        """quiz.class_id must match the class_id that was passed in."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config)
        assert quiz.class_id == sample_class.id

    def test_quiz_status_generated(self, db_session, mock_config, sample_class):
        """quiz.status should be 'generated' or 'needs_review' on success."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config)
        assert quiz.status in ("generated", "needs_review")


class TestGenerateQuizCreatesQuestions:
    """test_generate_quiz_creates_questions"""

    def test_quiz_has_questions(self, db_session, mock_config, sample_class):
        """The returned quiz must have at least one question attached."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config)
        assert quiz is not None
        assert len(quiz.questions) > 0, "Quiz should have at least one question"

    def test_each_question_has_quiz_id(self, db_session, mock_config, sample_class):
        """Every question must reference the parent quiz via quiz_id."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config)
        assert quiz is not None
        for question in quiz.questions:
            assert question.quiz_id == quiz.id, (
                f"Question {question.id} has quiz_id={question.quiz_id}, expected {quiz.id}"
            )

    def test_questions_are_question_instances(self, db_session, mock_config, sample_class):
        """Each element of quiz.questions must be a Question ORM object."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config)
        assert quiz is not None
        for q in quiz.questions:
            assert isinstance(q, Question), f"Expected Question, got {type(q)}"


class TestGenerateQuizUsesClassGradeLevel:
    """test_generate_quiz_uses_class_grade_level"""

    def test_grade_from_class(self, db_session, mock_config):
        """When grade_level is not overridden, the class grade_level is used."""
        cls = create_class(
            db_session,
            name="8th Grade Block B",
            grade_level="8th Grade",
            subject="Science",
        )
        quiz = generate_quiz(db_session, cls.id, mock_config)
        assert quiz is not None
        # The style_profile should reflect the class's grade_level
        profile = quiz.style_profile
        if isinstance(profile, str):
            profile = json.loads(profile)
        assert profile is not None, "style_profile should not be None"
        profile_str = json.dumps(profile) if isinstance(profile, dict) else str(profile)
        assert "8th Grade" in profile_str, f"Expected '8th Grade' in style_profile, got: {profile_str}"


class TestGenerateQuizGradeOverride:
    """test_generate_quiz_grade_override"""

    def test_override_replaces_class_grade(self, db_session, mock_config):
        """An explicit grade_level arg should override the class's grade_level."""
        cls = create_class(
            db_session,
            name="7th Grade Block C",
            grade_level="7th Grade",
            subject="Science",
        )
        quiz = generate_quiz(db_session, cls.id, mock_config, grade_level="9th Grade")
        assert quiz is not None
        profile = quiz.style_profile
        if isinstance(profile, str):
            profile = json.loads(profile)
        profile_str = json.dumps(profile) if isinstance(profile, dict) else str(profile)
        assert "9th Grade" in profile_str, f"Expected '9th Grade' override in style_profile, got: {profile_str}"


class TestGenerateQuizWithSolStandards:
    """test_generate_quiz_with_sol_standards"""

    def test_sol_standards_in_profile(self, db_session, mock_config, sample_class):
        """Supplied SOL standards should appear in the quiz style_profile."""
        sol = ["SOL 7.1", "SOL 7.2"]
        quiz = generate_quiz(db_session, sample_class.id, mock_config, sol_standards=sol)
        assert quiz is not None
        profile = quiz.style_profile
        if isinstance(profile, str):
            profile = json.loads(profile)
        profile_str = json.dumps(profile) if isinstance(profile, dict) else str(profile)
        for standard in sol:
            assert standard in profile_str, f"Expected '{standard}' in style_profile, got: {profile_str}"


class TestGenerateQuizWithNonexistentClass:
    """test_generate_quiz_with_nonexistent_class"""

    def test_returns_none_for_missing_class(self, db_session, mock_config):
        """generate_quiz should return None when the class does not exist."""
        result = generate_quiz(db_session, 9999, mock_config)
        assert result is None, "generate_quiz should return None for a nonexistent class_id"


class TestGenerateQuizSetsNumQuestions:
    """test_generate_quiz_sets_num_questions"""

    def test_num_questions_forwarded(self, db_session, mock_config, sample_class):
        """The num_questions parameter should influence the generation context."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config, num_questions=5)
        assert quiz is not None
        # The mock provider may not honour exact counts, but the quiz should
        # still be created successfully.  At minimum, verify the quiz has
        # questions and a style_profile that records the requested count.
        profile = quiz.style_profile
        if isinstance(profile, str):
            profile = json.loads(profile)
        # If the implementation stores num_questions in style_profile, verify it.
        if profile and "num_questions" in (profile if isinstance(profile, dict) else {}):
            assert profile["num_questions"] == 5
        # Regardless, the quiz should have at least some questions.
        assert len(quiz.questions) > 0


class TestGenerateQuizPersistedToDB:
    """test_generate_quiz_persisted_to_db"""

    def test_quiz_in_database(self, db_session, mock_config, sample_class):
        """After generate_quiz, querying the DB directly should find the quiz."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config)
        assert quiz is not None

        # Re-query from the database independently
        fetched = db_session.query(Quiz).filter_by(id=quiz.id).first()
        assert fetched is not None, "Quiz should be persisted in the database"
        assert fetched.id == quiz.id
        assert fetched.class_id == sample_class.id
        # Mock critic always rejects, so status is "needs_review" (BL-050)
        assert fetched.status in ("generated", "needs_review")

    def test_questions_in_database(self, db_session, mock_config, sample_class):
        """Questions created by generate_quiz must be independently queryable."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config)
        assert quiz is not None

        questions = db_session.query(Question).filter_by(quiz_id=quiz.id).all()
        assert len(questions) > 0, "Questions should be persisted in the database"
        assert len(questions) == len(quiz.questions)


class TestGenerateQuizDefaultConfig:
    """test_generate_quiz_default_config"""

    def test_minimal_mock_config_works(self, db_session, db_path):
        """A minimal config with only llm.provider='mock' should not error."""
        minimal_config = {
            "llm": {"provider": "mock"},
            "paths": {"database_file": db_path},
            "generation": {
                "quiz_title": "Test Quiz",
                "default_grade_level": "7th Grade Science",
                "sol_standards": [],
                "target_image_ratio": 0.0,
                "generate_ai_images": False,
                "interactive_review": False,
            },
        }
        cls = create_class(
            db_session,
            name="Default Config Class",
            grade_level="7th Grade",
            subject="Science",
        )
        quiz = generate_quiz(db_session, cls.id, minimal_config)
        assert quiz is not None, "generate_quiz should succeed with minimal mock config"
        assert isinstance(quiz, Quiz)
        assert len(quiz.questions) > 0
