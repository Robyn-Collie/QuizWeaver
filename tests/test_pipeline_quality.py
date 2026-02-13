"""
Tests for pipeline quality and reliability fixes.

BL-050: Quiz gets status "needs_review" when critic rejects all attempts.
BL-049: Rubric generation retries on parse failure.
BL-052: qa_guidelines.txt missing warning uses logging.debug, not print.
"""

import json
from unittest.mock import MagicMock, patch

from src.agents import get_qa_guidelines
from src.classroom import create_class
from src.database import Question, Quiz, get_engine, get_session
from src.quiz_generator import generate_quiz
from src.rubric_generator import generate_rubric

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(db_path):
    """Return a minimal mock config for quiz generation."""
    return {
        "llm": {"provider": "mock"},
        "paths": {"database_file": db_path},
        "generation": {
            "quiz_title": "Pipeline Quality Test Quiz",
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
        name="Pipeline Quality Test Class",
        grade_level="7th Grade",
        subject="Science",
    )
    return cls.id


# ---------------------------------------------------------------------------
# BL-050: Quiz status "needs_review" when critic rejects all attempts
# ---------------------------------------------------------------------------


class TestQuizNeedsReview:
    def test_quiz_status_generated_when_approved(self, db_session):
        """Quiz gets status 'generated' when critic approves."""
        session, db_path = db_session
        config = _make_config(db_path)
        class_id = _seed_class(session)

        # Patch pipeline to return metadata with approved=True
        fake_questions = [
            {"text": "What is photosynthesis?", "type": "mc",
             "options": ["A", "B", "C", "D"], "correct_index": 0}
        ]
        fake_metadata = {
            "prompt_summary": {},
            "metrics": {
                "duration_seconds": 0.5,
                "generator_calls": 1,
                "critic_calls": 1,
                "total_llm_calls": 2,
                "errors": 0,
                "attempts": 1,
                "approved": True,
            },
            "critic_history": [
                {"attempt": 1, "status": "APPROVED", "feedback": None},
            ],
            "provider": "mock",
            "model": None,
        }

        with patch("src.quiz_generator.run_agentic_pipeline",
                    return_value=(fake_questions, fake_metadata)):
            quiz = generate_quiz(session, class_id, config, num_questions=5)

        assert quiz is not None
        assert quiz.status == "generated"

    def test_quiz_status_needs_review_when_rejected(self, db_session):
        """Quiz gets status 'needs_review' when critic rejects all attempts."""
        session, db_path = db_session
        config = _make_config(db_path)
        config["agent_loop"] = {"max_retries": 1}
        class_id = _seed_class(session)

        # Patch the orchestrator to return metadata with approved=False
        fake_questions = [
            {"text": "What is photosynthesis?", "type": "mc",
             "options": ["A", "B", "C", "D"], "correct_index": 0}
        ]
        fake_metadata = {
            "prompt_summary": {},
            "metrics": {
                "duration_seconds": 0.5,
                "generator_calls": 1,
                "critic_calls": 1,
                "total_llm_calls": 2,
                "errors": 0,
                "attempts": 1,
                "approved": False,
            },
            "critic_history": [
                {"attempt": 1, "status": "REJECTED",
                 "feedback": "Questions are too easy"},
            ],
            "provider": "mock",
            "model": None,
        }

        with patch("src.quiz_generator.run_agentic_pipeline",
                    return_value=(fake_questions, fake_metadata)):
            quiz = generate_quiz(session, class_id, config, num_questions=5)

        assert quiz is not None
        assert quiz.status == "needs_review"

    def test_quiz_metadata_stored_with_needs_review(self, db_session):
        """Quiz with needs_review status still stores generation_metadata."""
        session, db_path = db_session
        config = _make_config(db_path)
        config["agent_loop"] = {"max_retries": 1}
        class_id = _seed_class(session)

        fake_questions = [
            {"text": "Test?", "type": "mc",
             "options": ["A", "B"], "correct_index": 0}
        ]
        fake_metadata = {
            "prompt_summary": {},
            "metrics": {"approved": False, "duration_seconds": 0.1,
                        "generator_calls": 1, "critic_calls": 1,
                        "total_llm_calls": 2, "errors": 0, "attempts": 1},
            "critic_history": [
                {"attempt": 1, "status": "REJECTED", "feedback": "Bad quiz"},
            ],
            "provider": "mock",
            "model": None,
        }

        with patch("src.quiz_generator.run_agentic_pipeline",
                    return_value=(fake_questions, fake_metadata)):
            quiz = generate_quiz(session, class_id, config, num_questions=5)

        assert quiz is not None
        assert quiz.generation_metadata is not None
        stored = json.loads(quiz.generation_metadata)
        assert stored["metrics"]["approved"] is False


class TestNeedsReviewBadgeInTemplate:
    def test_needs_review_warning_shown(self, flask_app):
        """Quiz detail page shows needs_review warning when status is needs_review."""
        db_path = flask_app.config["APP_CONFIG"]["paths"]["database_file"]
        engine = get_engine(db_path)
        session = get_session(engine)

        quiz = Quiz(
            title="Rejected Quiz",
            class_id=1,
            status="needs_review",
            style_profile=json.dumps({"grade_level": "7th Grade", "provider": "mock"}),
            generation_metadata=json.dumps({
                "prompt_summary": {},
                "metrics": {"approved": False, "duration_seconds": 0.5,
                            "generator_calls": 1, "critic_calls": 1,
                            "total_llm_calls": 2, "errors": 0, "attempts": 1},
                "critic_history": [
                    {"attempt": 1, "status": "REJECTED",
                     "feedback": "Questions are not aligned."},
                ],
                "provider": "mock",
                "model": None,
            }),
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
            assert "needs-review-warning" in html
            assert "not approved by the quality reviewer" in html

    def test_no_warning_when_generated(self, flask_client):
        """Normal generated quiz does not show needs_review warning."""
        resp = flask_client.get("/quizzes/1?skip_onboarding=1")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "needs-review-warning" not in html


# ---------------------------------------------------------------------------
# BL-049: Rubric generation retry on parse failure
# ---------------------------------------------------------------------------


class TestRubricRetry:
    def test_rubric_retry_on_parse_failure(self, db_session):
        """Rubric generation retries when first parse fails."""
        session, db_path = db_session
        config = _make_config(db_path)
        class_id = _seed_class(session)

        # Create a quiz with questions for rubric generation
        quiz = Quiz(
            title="Rubric Retry Test",
            class_id=class_id,
            status="generated",
            style_profile=json.dumps({"grade_level": "7th Grade"}),
        )
        session.add(quiz)
        session.commit()

        q = Question(
            quiz_id=quiz.id, question_type="mc", text="Test?",
            points=5.0, sort_order=0,
            data=json.dumps({"type": "mc", "text": "Test?",
                             "options": ["A", "B"], "correct_index": 0}),
        )
        session.add(q)
        session.commit()

        # Mock: first call returns unparseable text, second returns valid JSON
        valid_json = json.dumps([{
            "criterion": "Content Knowledge",
            "description": "Demonstrates understanding",
            "max_points": 10,
            "levels": [
                {"level": 1, "label": "Beginning", "description": "Minimal"},
                {"level": 2, "label": "Developing", "description": "Some"},
                {"level": 3, "label": "Proficient", "description": "Good"},
                {"level": 4, "label": "Advanced", "description": "Excellent"},
            ],
        }])

        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            "This is not valid JSON at all...",
            valid_json,
        ]

        config["llm"]["provider"] = "test_real"
        with patch("src.llm_provider.get_provider", return_value=mock_provider):
            rubric = generate_rubric(session, quiz.id, config)

        assert rubric is not None
        assert rubric.status == "generated"
        assert len(rubric.criteria) == 1
        assert mock_provider.generate.call_count == 2

    def test_rubric_fails_after_all_retries(self, db_session):
        """Rubric generation returns None after all retries exhausted."""
        session, db_path = db_session
        config = _make_config(db_path)
        class_id = _seed_class(session)

        quiz = Quiz(
            title="Rubric Fail Test",
            class_id=class_id,
            status="generated",
            style_profile=json.dumps({"grade_level": "7th Grade"}),
        )
        session.add(quiz)
        session.commit()

        q = Question(
            quiz_id=quiz.id, question_type="mc", text="Test?",
            points=5.0, sort_order=0,
            data=json.dumps({"type": "mc", "text": "Test?",
                             "options": ["A", "B"], "correct_index": 0}),
        )
        session.add(q)
        session.commit()

        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            "not json",
            "still not json",
        ]

        config["llm"]["provider"] = "test_real"
        with patch("src.llm_provider.get_provider", return_value=mock_provider):
            rubric = generate_rubric(session, quiz.id, config)

        assert rubric is None

    def test_rubric_retry_on_llm_exception(self, db_session):
        """Rubric generation retries when LLM call throws an exception."""
        session, db_path = db_session
        config = _make_config(db_path)
        class_id = _seed_class(session)

        quiz = Quiz(
            title="Rubric Exception Test",
            class_id=class_id,
            status="generated",
            style_profile=json.dumps({"grade_level": "7th Grade"}),
        )
        session.add(quiz)
        session.commit()

        q = Question(
            quiz_id=quiz.id, question_type="mc", text="Test?",
            points=5.0, sort_order=0,
            data=json.dumps({"type": "mc", "text": "Test?",
                             "options": ["A", "B"], "correct_index": 0}),
        )
        session.add(q)
        session.commit()

        valid_json = json.dumps([{
            "criterion": "Knowledge",
            "description": "Understanding",
            "max_points": 5,
            "levels": [],
        }])

        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            RuntimeError("API timeout"),
            valid_json,
        ]

        config["llm"]["provider"] = "test_real"
        with patch("src.llm_provider.get_provider", return_value=mock_provider):
            rubric = generate_rubric(session, quiz.id, config)

        assert rubric is not None
        assert rubric.status == "generated"


# ---------------------------------------------------------------------------
# BL-052: qa_guidelines.txt warning uses logging, not print
# ---------------------------------------------------------------------------


class TestQaGuidelinesLogging:
    def test_qa_guidelines_missing_uses_debug_logging(self, tmp_path, monkeypatch):
        """get_qa_guidelines() uses logging.debug, not print, when file is missing."""
        # Change to a directory without qa_guidelines.txt
        monkeypatch.chdir(tmp_path)

        with patch("builtins.print") as mock_print:
            result = get_qa_guidelines()

        assert result == ""
        # print should NOT have been called
        mock_print.assert_not_called()

    def test_qa_guidelines_debug_message(self, tmp_path, monkeypatch):
        """get_qa_guidelines() emits a debug log when file is missing."""
        monkeypatch.chdir(tmp_path)

        with patch("src.agents.logger") as mock_logger:
            result = get_qa_guidelines()

        assert result == ""
        mock_logger.debug.assert_called_once()
        assert "not found" in mock_logger.debug.call_args[0][0]
