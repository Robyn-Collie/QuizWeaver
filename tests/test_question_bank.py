"""
Tests for BL-012: Question Bank.

Tests the API endpoints for saving/removing questions to/from the bank,
the question bank page, and the bank toggle on quiz detail.
"""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with a quiz and questions."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Test Class",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps([]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.flush()

    quiz = Quiz(
        title="Test Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({"sol_standards": ["SOL 7.1"]}),
    )
    session.add(quiz)
    session.flush()

    # Add questions with different types
    for i, (qtype, text, saved) in enumerate(
        [
            ("mc", "What is photosynthesis?", 0),
            ("tf", "The sun is a star.", 1),  # Already saved
            ("mc", "What is mitosis?", 0),
        ]
    ):
        q = Question(
            quiz_id=quiz.id,
            question_type=qtype,
            text=text,
            points=1.0,
            sort_order=i,
            saved_to_bank=saved,
            data=json.dumps({"options": ["A", "B", "C", "D"], "correct_index": 0}),
        )
        session.add(q)

    session.commit()
    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "7th Grade"},
    }
    flask_app = create_app(test_config)
    flask_app.config["TESTING"] = True

    yield flask_app

    flask_app.config["DB_ENGINE"].dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def client(app):
    """Create a logged-in test client."""
    c = app.test_client()
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


def _get_question_ids(app):
    """Helper to get question IDs from the database."""
    engine = app.config["DB_ENGINE"]
    session = get_session(engine)
    questions = session.query(Question).order_by(Question.sort_order).all()
    ids = [q.id for q in questions]
    session.close()
    return ids


# --- API: Add to Bank ---


class TestAddToBank:
    def test_add_question(self, app, client):
        qids = _get_question_ids(app)
        resp = client.post(
            "/api/question-bank/add",
            json={"question_id": qids[0]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

        # Verify in DB
        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        q = session.query(Question).filter_by(id=qids[0]).first()
        assert q.saved_to_bank == 1
        session.close()

    def test_add_missing_question(self, client):
        resp = client.post(
            "/api/question-bank/add",
            json={"question_id": 99999},
        )
        assert resp.status_code == 404

    def test_add_without_id(self, client):
        resp = client.post("/api/question-bank/add", json={})
        assert resp.status_code == 400


# --- API: Remove from Bank ---


class TestRemoveFromBank:
    def test_remove_question(self, app, client):
        qids = _get_question_ids(app)
        # qids[1] is already saved
        resp = client.post(
            "/api/question-bank/remove",
            json={"question_id": qids[1]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        q = session.query(Question).filter_by(id=qids[1]).first()
        assert q.saved_to_bank == 0
        session.close()

    def test_remove_missing_question(self, client):
        resp = client.post(
            "/api/question-bank/remove",
            json={"question_id": 99999},
        )
        assert resp.status_code == 404


# --- Question Bank Page ---


class TestQuestionBankPage:
    def test_page_loads(self, client):
        resp = client.get("/question-bank")
        assert resp.status_code == 200

    def test_shows_saved_questions(self, client):
        resp = client.get("/question-bank")
        html = resp.data.decode()
        # Only the TF question (qids[1]) is saved
        assert "The sun is a star." in html
        assert "What is photosynthesis?" not in html

    def test_search_filter(self, app, client):
        # First save another question to bank
        qids = _get_question_ids(app)
        client.post("/api/question-bank/add", json={"question_id": qids[0]})

        resp = client.get("/question-bank?search=photosynthesis")
        html = resp.data.decode()
        assert "photosynthesis" in html
        assert "sun is a star" not in html

    def test_type_filter(self, client):
        resp = client.get("/question-bank?type=tf")
        html = resp.data.decode()
        assert "The sun is a star." in html

    def test_type_filter_no_results(self, client):
        resp = client.get("/question-bank?type=essay")
        html = resp.data.decode()
        assert "No questions saved" in html

    def test_bank_link_in_nav(self, client):
        resp = client.get("/question-bank")
        html = resp.data.decode()
        assert "/question-bank" in html
        assert "Bank" in html


# --- Quiz Detail Bank Toggle ---


class TestQuizDetailBankToggle:
    def test_detail_has_bank_button(self, app, client):
        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        quiz = session.query(Quiz).first()
        session.close()

        resp = client.get(f"/quizzes/{quiz.id}")
        html = resp.data.decode()
        assert "btn-bank-toggle" in html
        assert "Bank" in html

    def test_saved_question_shows_banked(self, app, client):
        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        quiz = session.query(Quiz).first()
        session.close()

        resp = client.get(f"/quizzes/{quiz.id}")
        html = resp.data.decode()
        assert "Banked" in html  # The TF question is already saved
