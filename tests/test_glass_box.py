"""
Tests for Glass Box transparency features (BL-040, BL-041).

BL-040: Show prompt summary to teacher after generation.
BL-041: Show critic feedback/rejection reasons in UI.

Verifies that generation_metadata is captured by the Orchestrator,
stored on Quiz records, and rendered in the quiz detail template.
"""

import json

from src.agents import Orchestrator
from src.classroom import create_class
from src.database import Quiz, get_engine, get_session
from src.quiz_generator import generate_quiz

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(db_path):
    """Return a minimal mock config for quiz generation."""
    return {
        "llm": {"provider": "mock"},
        "paths": {"database_file": db_path},
        "generation": {
            "quiz_title": "Glass Box Test Quiz",
            "default_grade_level": "7th Grade Science",
            "sol_standards": [],
            "target_image_ratio": 0.0,
            "generate_ai_images": False,
            "interactive_review": False,
        },
        "agent_loop": {"max_retries": 3},
    }


def _seed_class(session):
    """Create a test class and return its id."""
    cls = create_class(
        session,
        name="Glass Box Test Class",
        grade_level="7th Grade",
        subject="Science",
    )
    return cls.id


# ---------------------------------------------------------------------------
# Test: Orchestrator returns (questions, metadata) tuple
# ---------------------------------------------------------------------------


class TestOrchestratorReturnsTuple:
    def test_orchestrator_returns_tuple(self, db_session):
        """Orchestrator.run() returns a (questions, metadata) tuple."""
        session, db_path = db_session
        config = _make_config(db_path)
        orch = Orchestrator(config, web_mode=True)
        context = {
            "content_summary": "Test content about cells",
            "structured_data": [],
            "retake_text": "",
            "num_questions": 5,
            "images": [],
            "image_ratio": 0.0,
            "grade_level": "7th Grade",
            "sol_standards": ["SOL 7.1"],
            "difficulty": 3,
        }
        result = orch.run(context)
        assert isinstance(result, tuple), "Orchestrator.run() should return a tuple"
        assert len(result) == 2, "Tuple should have 2 elements"
        questions, metadata = result
        assert isinstance(questions, list)
        assert isinstance(metadata, dict)


# ---------------------------------------------------------------------------
# Test: generation_metadata is stored on Quiz record
# ---------------------------------------------------------------------------


class TestGenerationMetadataStored:
    def test_generation_metadata_stored(self, db_session):
        """generate_quiz() stores generation_metadata JSON on the Quiz record."""
        session, db_path = db_session
        config = _make_config(db_path)
        class_id = _seed_class(session)

        quiz = generate_quiz(session, class_id, config, num_questions=5)
        assert quiz is not None, "generate_quiz should return a Quiz"
        assert quiz.generation_metadata is not None, "generation_metadata should be set"

        metadata = json.loads(quiz.generation_metadata)
        assert isinstance(metadata, dict)
        assert "metrics" in metadata
        assert "critic_history" in metadata
        assert "prompt_summary" in metadata
        assert "provider" in metadata


# ---------------------------------------------------------------------------
# Test: metadata metrics structure
# ---------------------------------------------------------------------------


class TestGenerationMetadataMetrics:
    def test_generation_metadata_metrics(self, db_session):
        """Metrics include generator_calls, critic_calls, attempts, approved, duration."""
        session, db_path = db_session
        config = _make_config(db_path)
        class_id = _seed_class(session)

        quiz = generate_quiz(session, class_id, config, num_questions=5)
        metadata = json.loads(quiz.generation_metadata)
        metrics = metadata["metrics"]

        assert "generator_calls" in metrics
        assert "critic_calls" in metrics
        assert "attempts" in metrics
        assert "approved" in metrics
        assert "duration_seconds" in metrics
        assert "total_llm_calls" in metrics
        assert metrics["generator_calls"] >= 1
        assert metrics["critic_calls"] >= 1
        assert metrics["attempts"] >= 1
        assert isinstance(metrics["duration_seconds"], (int, float))


# ---------------------------------------------------------------------------
# Test: critic_history structure
# ---------------------------------------------------------------------------


class TestGenerationMetadataCriticHistory:
    def test_generation_metadata_critic_history(self, db_session):
        """critic_history is a list of entries with attempt, status, feedback keys."""
        session, db_path = db_session
        config = _make_config(db_path)
        class_id = _seed_class(session)

        quiz = generate_quiz(session, class_id, config, num_questions=5)
        metadata = json.loads(quiz.generation_metadata)
        history = metadata["critic_history"]

        assert isinstance(history, list)
        assert len(history) >= 1, "At least one critic review should be recorded"

        for entry in history:
            assert "attempt" in entry
            assert "status" in entry
            assert entry["status"] in ("APPROVED", "REJECTED")
            # feedback can be None for APPROVED
            assert "feedback" in entry


# ---------------------------------------------------------------------------
# Test: prompt_summary structure
# ---------------------------------------------------------------------------


class TestGenerationMetadataPromptSummary:
    def test_generation_metadata_prompt_summary(self, db_session):
        """prompt_summary contains grade_level, num_questions, standards, framework."""
        session, db_path = db_session
        config = _make_config(db_path)
        class_id = _seed_class(session)

        quiz = generate_quiz(
            session,
            class_id,
            config,
            num_questions=10,
            grade_level="8th Grade",
            sol_standards=["SOL 8.1", "SOL 8.2"],
            cognitive_framework="blooms",
            difficulty=4,
        )
        metadata = json.loads(quiz.generation_metadata)
        summary = metadata["prompt_summary"]

        assert summary["grade_level"] == "8th Grade"
        assert summary["num_questions"] == 10
        assert "SOL 8.1" in summary["standards"]
        assert "SOL 8.2" in summary["standards"]
        assert summary["cognitive_framework"] == "blooms"
        assert summary["difficulty"] == 4


# ---------------------------------------------------------------------------
# Test: quiz detail template renders Glass Box section
# ---------------------------------------------------------------------------


class TestQuizDetailRendersGlassBox:
    def test_quiz_detail_renders_glass_box(self, flask_app):
        """Quiz detail page shows 'How This Quiz Was Generated' for quizzes with metadata."""
        # Seed a quiz with generation_metadata

        db_path = flask_app.config["APP_CONFIG"]["paths"]["database_file"]
        engine = get_engine(db_path)
        session = get_session(engine)

        metadata = {
            "prompt_summary": {
                "grade_level": "7th Grade",
                "num_questions": 10,
                "standards": ["SOL 7.1"],
                "cognitive_framework": "blooms",
                "difficulty": 3,
                "topics_from_lessons": [],
            },
            "metrics": {
                "duration_seconds": 1.5,
                "generator_calls": 2,
                "critic_calls": 2,
                "total_llm_calls": 4,
                "errors": 0,
                "attempts": 2,
                "approved": True,
            },
            "critic_history": [
                {"attempt": 1, "status": "REJECTED", "feedback": "Questions need revision."},
                {"attempt": 2, "status": "APPROVED", "feedback": None},
            ],
            "provider": "mock",
            "model": None,
        }

        quiz = Quiz(
            title="Glass Box Quiz",
            class_id=1,
            status="generated",
            style_profile=json.dumps({"grade_level": "7th Grade", "provider": "mock"}),
            generation_metadata=json.dumps(metadata),
        )
        session.add(quiz)
        session.commit()
        quiz_id = quiz.id
        session.close()
        engine.dispose()

        with flask_app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["username"] = "teacher"
            resp = client.get(f"/quizzes/{quiz_id}?skip_onboarding=1")
            assert resp.status_code == 200
            html = resp.data.decode()
            assert "How This Quiz Was Generated" in html
            assert "Glass Box" in html
            assert "Generation Parameters" in html
            assert "Pipeline Metrics" in html
            assert "Quality Review History" in html
            assert "Questions need revision." in html
            assert "REJECTED" in html
            assert "APPROVED" in html


# ---------------------------------------------------------------------------
# Test: no Glass Box section when metadata is absent
# ---------------------------------------------------------------------------


class TestQuizDetailNoGlassBoxWithoutMetadata:
    def test_quiz_detail_no_glass_box_without_metadata(self, flask_client):
        """Old quizzes without generation_metadata don't show the Glass Box section."""
        # The flask_client fixture seeds quiz id=1 without generation_metadata
        resp = flask_client.get("/quizzes/1?skip_onboarding=1")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "How This Quiz Was Generated" not in html
        assert "glass-box-section" not in html


# ---------------------------------------------------------------------------
# Test: pipeline backward compat — generate_quiz returns Quiz object
# ---------------------------------------------------------------------------


class TestPipelineBackwardCompat:
    def test_pipeline_backward_compat(self, db_session):
        """generate_quiz() still returns a Quiz object (not a tuple)."""
        session, db_path = db_session
        config = _make_config(db_path)
        class_id = _seed_class(session)

        result = generate_quiz(session, class_id, config, num_questions=5)
        assert isinstance(result, Quiz), "generate_quiz should return a Quiz ORM object"
        assert result.status in ("generated", "needs_review")
        assert len(result.questions) > 0
