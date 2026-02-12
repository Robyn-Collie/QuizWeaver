"""
Integration tests for cognitive framework features in the quiz pipeline.

Tests full generate_quiz() calls with Bloom's/DOK distributions via mock provider.
Run with: python -m pytest tests/test_cognitive_pipeline.py -v
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.classroom import create_class
from src.database import get_engine, get_session, init_db
from src.migrations import run_migrations
from src.quiz_generator import generate_quiz

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path():
    """Create a temporary database file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    yield tmp.name
    try:
        os.remove(tmp.name)
    except OSError:
        pass


@pytest.fixture
def db_session(db_path):
    """Provide a fully-initialised SQLAlchemy session."""
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
            "quiz_title": "Cognitive Test Quiz",
            "default_grade_level": "7th Grade Science",
            "sol_standards": [],
            "target_image_ratio": 0.0,
            "generate_ai_images": False,
            "interactive_review": False,
        },
    }


@pytest.fixture
def sample_class(db_session):
    """Create and return a sample class."""
    return create_class(
        db_session,
        name="7th Grade Science - Block A",
        grade_level="7th Grade",
        subject="Science",
        standards=["SOL 7.1"],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCognitivePipelineBlooms:
    """Tests for quiz generation with Bloom's Taxonomy framework."""

    def test_blooms_framework_in_style_profile(self, db_session, mock_config, sample_class):
        """Style profile should contain cognitive_framework='blooms'."""
        dist = {1: 5, 2: 5, 3: 5, 4: 3, 5: 1, 6: 1}
        quiz = generate_quiz(
            db_session,
            sample_class.id,
            mock_config,
            num_questions=20,
            cognitive_framework="blooms",
            cognitive_distribution=dist,
            difficulty=4,
        )
        assert quiz is not None
        profile = quiz.style_profile
        if isinstance(profile, str):
            profile = json.loads(profile)
        assert profile["cognitive_framework"] == "blooms"

    def test_blooms_difficulty_in_style_profile(self, db_session, mock_config, sample_class):
        """Style profile should contain the specified difficulty."""
        dist = {1: 10, 2: 10}
        quiz = generate_quiz(
            db_session,
            sample_class.id,
            mock_config,
            num_questions=20,
            cognitive_framework="blooms",
            cognitive_distribution=dist,
            difficulty=5,
        )
        assert quiz is not None
        profile = quiz.style_profile
        if isinstance(profile, str):
            profile = json.loads(profile)
        assert profile["difficulty"] == 5

    def test_blooms_distribution_in_style_profile(self, db_session, mock_config, sample_class):
        """Style profile should contain the cognitive distribution."""
        dist = {1: 5, 2: 5, 3: 5, 4: 3, 5: 1, 6: 1}
        quiz = generate_quiz(
            db_session,
            sample_class.id,
            mock_config,
            num_questions=20,
            cognitive_framework="blooms",
            cognitive_distribution=dist,
        )
        assert quiz is not None
        profile = quiz.style_profile
        if isinstance(profile, str):
            profile = json.loads(profile)
        assert profile["cognitive_distribution"] is not None


class TestCognitivePipelineDOK:
    """Tests for quiz generation with Webb's DOK framework."""

    def test_dok_framework_in_style_profile(self, db_session, mock_config, sample_class):
        """Style profile should contain cognitive_framework='dok'."""
        dist = {1: 5, 2: 5, 3: 5, 4: 5}
        quiz = generate_quiz(
            db_session,
            sample_class.id,
            mock_config,
            num_questions=20,
            cognitive_framework="dok",
            cognitive_distribution=dist,
        )
        assert quiz is not None
        profile = quiz.style_profile
        if isinstance(profile, str):
            profile = json.loads(profile)
        assert profile["cognitive_framework"] == "dok"


class TestCognitivePipelineBackwardCompat:
    """Tests that no-framework mode remains fully backward compatible."""

    def test_no_framework_no_cognitive_in_profile(self, db_session, mock_config, sample_class):
        """Without framework, cognitive_framework should be None in profile."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config)
        assert quiz is not None
        profile = quiz.style_profile
        if isinstance(profile, str):
            profile = json.loads(profile)
        assert profile.get("cognitive_framework") is None

    def test_no_framework_quiz_still_generated(self, db_session, mock_config, sample_class):
        """Without framework, quiz should still generate successfully."""
        quiz = generate_quiz(db_session, sample_class.id, mock_config)
        assert quiz is not None
        assert quiz.status == "generated"
        assert len(quiz.questions) > 0


class TestCognitivePipelineInvalidDistribution:
    """Tests for graceful handling of invalid distributions."""

    def test_invalid_distribution_fallback(self, db_session, mock_config, sample_class):
        """Invalid distribution should fall back gracefully (no crash)."""
        # Sum doesn't match num_questions
        dist = {1: 100}
        quiz = generate_quiz(
            db_session,
            sample_class.id,
            mock_config,
            num_questions=20,
            cognitive_framework="blooms",
            cognitive_distribution=dist,
        )
        assert quiz is not None
        assert quiz.status == "generated"
        # Framework should be cleared due to invalid distribution
        profile = quiz.style_profile
        if isinstance(profile, str):
            profile = json.loads(profile)
        assert profile.get("cognitive_framework") is None

    def test_invalid_levels_fallback(self, db_session, mock_config, sample_class):
        """Invalid level numbers should fall back gracefully."""
        dist = {99: 20}  # Invalid level for blooms
        quiz = generate_quiz(
            db_session,
            sample_class.id,
            mock_config,
            num_questions=20,
            cognitive_framework="blooms",
            cognitive_distribution=dist,
        )
        assert quiz is not None
        assert quiz.status == "generated"


class TestCognitivePipelineQuestionTags:
    """Tests that mock questions get cognitive tags when framework is specified."""

    def test_blooms_questions_have_cognitive_tags(self, db_session, mock_config, sample_class):
        """Questions generated with Bloom's should have cognitive_level in data."""
        dist = {1: 5, 2: 5, 3: 5, 4: 3, 5: 1, 6: 1}
        quiz = generate_quiz(
            db_session,
            sample_class.id,
            mock_config,
            num_questions=20,
            cognitive_framework="blooms",
            cognitive_distribution=dist,
        )
        assert quiz is not None
        # Check at least one question has cognitive tags
        has_cognitive = False
        for q in quiz.questions:
            data = q.data
            if isinstance(data, str):
                data = json.loads(data)
            if data.get("cognitive_level"):
                has_cognitive = True
                break
        assert has_cognitive, "At least one question should have cognitive_level tag"
