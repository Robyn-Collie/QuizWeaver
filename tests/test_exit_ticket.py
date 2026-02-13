"""Tests for exit ticket generator."""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, LessonLog, Question, get_engine, get_session


@pytest.fixture
def db_session():
    """Create a temporary database session for testing."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = get_engine(tmp.name)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Create test class
    cls = Class(id=1, name="Science 7A", grade_level="7th Grade Science")
    session.add(cls)

    # Create a lesson log
    import datetime

    lesson = LessonLog(
        id=1,
        class_id=1,
        content="Today we covered the light reactions and Calvin cycle in photosynthesis.",
        topics="Photosynthesis",
        notes="Covered light reactions and Calvin cycle",
        date=datetime.date.today(),
    )
    session.add(lesson)
    session.commit()

    yield session

    session.close()
    engine.dispose()
    os.remove(tmp.name)


@pytest.fixture
def mock_config():
    """Standard mock config."""
    return {
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "7th Grade Science"},
        "paths": {"database_file": ":memory:"},
    }


class TestExitTicketGenerator:
    """Tests for the exit ticket generation module."""

    def test_generate_from_topic(self, db_session, mock_config):
        from src.exit_ticket_generator import generate_exit_ticket

        quiz = generate_exit_ticket(
            db_session, class_id=1, config=mock_config, topic="Photosynthesis"
        )
        assert quiz is not None
        assert quiz.status == "generated"
        assert "Exit Ticket" in quiz.title

    def test_generate_from_lesson_log(self, db_session, mock_config):
        from src.exit_ticket_generator import generate_exit_ticket

        quiz = generate_exit_ticket(
            db_session, class_id=1, config=mock_config, lesson_log_id=1
        )
        assert quiz is not None
        assert quiz.status == "generated"
        assert "Photosynthesis" in quiz.title

    def test_generate_default_count(self, db_session, mock_config):
        from src.exit_ticket_generator import generate_exit_ticket

        quiz = generate_exit_ticket(
            db_session, class_id=1, config=mock_config, topic="Cells"
        )
        questions = db_session.query(Question).filter_by(quiz_id=quiz.id).all()
        assert len(questions) <= 3

    def test_generate_custom_count(self, db_session, mock_config):
        from src.exit_ticket_generator import generate_exit_ticket

        quiz = generate_exit_ticket(
            db_session,
            class_id=1,
            config=mock_config,
            topic="Cells",
            num_questions=5,
        )
        questions = db_session.query(Question).filter_by(quiz_id=quiz.id).all()
        assert len(questions) <= 5

    def test_count_clamped_min(self, db_session, mock_config):
        from src.exit_ticket_generator import generate_exit_ticket

        quiz = generate_exit_ticket(
            db_session,
            class_id=1,
            config=mock_config,
            topic="Cells",
            num_questions=0,
        )
        assert quiz is not None  # Should clamp to 1, not fail

    def test_count_clamped_max(self, db_session, mock_config):
        from src.exit_ticket_generator import generate_exit_ticket

        quiz = generate_exit_ticket(
            db_session,
            class_id=1,
            config=mock_config,
            topic="Cells",
            num_questions=100,
        )
        questions = db_session.query(Question).filter_by(quiz_id=quiz.id).all()
        assert len(questions) <= 5

    def test_invalid_class_returns_none(self, db_session, mock_config):
        from src.exit_ticket_generator import generate_exit_ticket

        result = generate_exit_ticket(
            db_session, class_id=999, config=mock_config, topic="Cells"
        )
        assert result is None

    def test_exit_ticket_style_profile(self, db_session, mock_config):
        from src.exit_ticket_generator import generate_exit_ticket

        quiz = generate_exit_ticket(
            db_session, class_id=1, config=mock_config, topic="Cells"
        )
        sp = json.loads(quiz.style_profile) if isinstance(quiz.style_profile, str) else quiz.style_profile
        assert sp["exit_ticket"] is True

    def test_points_default_to_one(self, db_session, mock_config):
        from src.exit_ticket_generator import generate_exit_ticket

        quiz = generate_exit_ticket(
            db_session, class_id=1, config=mock_config, topic="Cells"
        )
        questions = db_session.query(Question).filter_by(quiz_id=quiz.id).all()
        for q in questions:
            assert q.points == 1

    def test_custom_title(self, db_session, mock_config):
        from src.exit_ticket_generator import generate_exit_ticket

        quiz = generate_exit_ticket(
            db_session,
            class_id=1,
            config=mock_config,
            topic="Cells",
            title="My Custom Exit Ticket",
        )
        assert quiz.title == "My Custom Exit Ticket"

    def test_question_types_are_valid(self, db_session, mock_config):
        from src.exit_ticket_generator import generate_exit_ticket

        quiz = generate_exit_ticket(
            db_session,
            class_id=1,
            config=mock_config,
            topic="Cells",
            num_questions=5,
        )
        questions = db_session.query(Question).filter_by(quiz_id=quiz.id).all()
        valid_types = {"multiple_choice", "true_false", "short_answer", "mc", "tf"}
        for q in questions:
            assert q.question_type in valid_types

    def test_no_topic_no_lesson_uses_recent(self, db_session, mock_config):
        """When no topic or lesson_log_id, should use recent lessons."""
        from src.exit_ticket_generator import generate_exit_ticket

        quiz = generate_exit_ticket(
            db_session,
            class_id=1,
            config=mock_config,
        )
        assert quiz is not None
        assert quiz.status == "generated"


class TestExitTicketMockResponse:
    """Tests for the mock exit ticket response."""

    def test_mock_response_returns_json(self):
        from src.mock_responses import get_exit_ticket_response

        result = get_exit_ticket_response(3)
        data = json.loads(result)
        assert isinstance(data, list)

    def test_mock_response_respects_count(self):
        from src.mock_responses import get_exit_ticket_response

        for count in [1, 2, 3, 4, 5]:
            data = json.loads(get_exit_ticket_response(count))
            assert len(data) == count

    def test_mock_response_clamps_count(self):
        from src.mock_responses import get_exit_ticket_response

        data = json.loads(get_exit_ticket_response(10))
        assert len(data) == 5  # Max
        data = json.loads(get_exit_ticket_response(0))
        assert len(data) == 1  # Min

    def test_mock_response_has_required_fields(self):
        from src.mock_responses import get_exit_ticket_response

        data = json.loads(get_exit_ticket_response(3))
        for q in data:
            assert "type" in q
            assert "text" in q
            assert "points" in q
            assert q["points"] == 1

    def test_mock_response_mixed_types(self):
        from src.mock_responses import get_exit_ticket_response

        data = json.loads(get_exit_ticket_response(3))
        types = {q["type"] for q in data}
        assert len(types) > 1  # At least 2 different types

    def test_mock_detection_in_get_mock_response(self):
        from src.mock_responses import get_mock_response

        result = get_mock_response(["Generate 3 exit ticket questions"], json_mode=True)
        data = json.loads(result)
        assert isinstance(data, list)
        # Should have exit ticket style (1 point per question)
        for q in data:
            assert q["points"] == 1


class TestExitTicketWebRoutes:
    """Tests for exit ticket web routes."""

    @pytest.fixture
    def web_app(self):
        """Create a Flask app with a seeded temp database."""
        import datetime

        from src.web.app import create_app

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()

        config = {
            "llm": {"provider": "mock"},
            "generation": {"default_grade_level": "7th Grade Science"},
            "paths": {"database_file": tmp.name},
        }
        app = create_app(config)
        app.config["TESTING"] = True

        app.config["WTF_CSRF_ENABLED"] = False

        # Seed data AFTER create_app (migrations may reset tables)
        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        cls = Class(id=1, name="Science 7A", grade_level="7th Grade Science")
        session.merge(cls)
        lesson = LessonLog(
            id=1,
            class_id=1,
            content="Photosynthesis lesson content",
            topics="Photosynthesis",
            notes="Light reactions and Calvin cycle",
            date=datetime.date.today(),
        )
        session.merge(lesson)
        session.commit()
        session.close()

        yield app

        app.config["DB_ENGINE"].dispose()
        try:
            os.remove(tmp.name)
        except PermissionError:
            pass

    @pytest.fixture
    def client(self, web_app):
        """Logged-in test client."""
        c = web_app.test_client()
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        return c

    def test_get_form(self, client):
        resp = client.get("/exit-ticket/generate")
        assert resp.status_code == 200
        assert b"Exit Ticket" in resp.data

    def test_post_missing_class(self, client):
        resp = client.post("/exit-ticket/generate", data={})
        assert resp.status_code == 400

    def test_post_success(self, client):
        resp = client.post(
            "/exit-ticket/generate",
            data={
                "class_id": 1,
                "topic": "Photosynthesis",
                "num_questions": 3,
            },
        )
        assert resp.status_code == 303  # Redirect to quiz detail

    def test_lessons_api(self, client):
        resp = client.get("/api/classes/1/lessons")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)


class TestExitTicketCLI:
    """Tests for the exit ticket CLI command."""

    def test_cli_registration(self):
        """Verify generate-exit-ticket is registered as a CLI command."""
        import argparse

        from src.cli.study_commands import register_study_commands

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register_study_commands(subparsers)
        args = parser.parse_args(["generate-exit-ticket", "--topic", "Cells", "--count", "3"])
        assert args.command == "generate-exit-ticket"
        assert args.topic == "Cells"
        assert args.num_questions == 3
