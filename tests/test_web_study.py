"""
Tests for QuizWeaver study material web routes.

Covers all 6 study routes plus the class quiz API.
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
    StudySet,
    get_engine,
    get_session,
)


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed test data
    cls = Class(
        name="Block A",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    # Add a quiz
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
        data=json.dumps({"type": "mc", "options": ["A", "B"], "correct_index": 0}),
    )
    session.add(q1)
    session.commit()

    # Add a study set with cards
    ss = StudySet(
        class_id=cls.id,
        quiz_id=quiz.id,
        title="Test Flashcards",
        material_type="flashcard",
        status="generated",
        config=json.dumps({"material_type": "flashcard", "provider": "mock"}),
    )
    session.add(ss)
    session.commit()

    card1 = StudyCard(
        study_set_id=ss.id,
        card_type="flashcard",
        sort_order=0,
        front="What is DNA?",
        back="Deoxyribonucleic acid",
        data=json.dumps({"tags": ["biology"]}),
    )
    card2 = StudyCard(
        study_set_id=ss.id,
        card_type="flashcard",
        sort_order=1,
        front="What is RNA?",
        back="Ribonucleic acid",
        data=json.dumps({"tags": ["biology"]}),
    )
    session.add(card1)
    session.add(card2)
    session.commit()

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "7th Grade Science"},
    }
    flask_app = create_app(test_config)
    flask_app.config["TESTING"] = True

    flask_app.config["WTF_CSRF_ENABLED"] = False

    yield flask_app

    flask_app.config["DB_ENGINE"].dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def client(app):
    """Logged-in test client."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
    return c


@pytest.fixture
def anon_client(app):
    """Unauthenticated test client."""
    return app.test_client()


# --- Auth tests ---


class TestStudyAuth:
    def test_study_list_requires_login(self, anon_client):
        resp = anon_client.get("/study")
        assert resp.status_code == 303

    def test_study_generate_requires_login(self, anon_client):
        resp = anon_client.get("/study/generate")
        assert resp.status_code == 303

    def test_study_detail_requires_login(self, anon_client):
        resp = anon_client.get("/study/1")
        assert resp.status_code == 303


# --- List route ---


class TestStudyList:
    def test_list_page_loads(self, client):
        resp = client.get("/study")
        assert resp.status_code == 200
        assert b"Study Materials" in resp.data

    def test_list_shows_study_sets(self, client):
        resp = client.get("/study")
        assert b"Test Flashcards" in resp.data

    def test_list_filter_by_type(self, client):
        resp = client.get("/study?type=flashcard")
        assert resp.status_code == 200
        assert b"Test Flashcards" in resp.data


# --- Generate route ---


class TestStudyGenerate:
    def test_generate_form_loads(self, client):
        resp = client.get("/study/generate")
        assert resp.status_code == 200
        assert b"Generate Study Material" in resp.data

    def test_generate_post_flashcard(self, client):
        resp = client.post(
            "/study/generate",
            data={
                "class_id": "1",
                "material_type": "flashcard",
                "topic": "photosynthesis",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_generate_post_study_guide(self, client):
        resp = client.post(
            "/study/generate",
            data={
                "class_id": "1",
                "material_type": "study_guide",
                "topic": "evolution",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_generate_requires_class_id(self, client):
        resp = client.post(
            "/study/generate",
            data={
                "material_type": "flashcard",
                "topic": "test",
            },
        )
        assert resp.status_code == 400


# --- Detail route ---


class TestStudyDetail:
    def test_detail_page_loads(self, client):
        resp = client.get("/study/1")
        assert resp.status_code == 200
        assert b"Test Flashcards" in resp.data

    def test_detail_shows_cards(self, client):
        resp = client.get("/study/1")
        assert b"What is DNA?" in resp.data
        assert b"Deoxyribonucleic acid" in resp.data

    def test_detail_404_for_missing(self, client):
        resp = client.get("/study/9999")
        assert resp.status_code == 404


# --- Export route ---


class TestStudyExport:
    def test_export_tsv(self, client):
        resp = client.get("/study/1/export/tsv")
        assert resp.status_code == 200
        assert b"What is DNA?" in resp.data

    def test_export_csv(self, client):
        resp = client.get("/study/1/export/csv")
        assert resp.status_code == 200
        assert b"Front" in resp.data

    def test_export_pdf(self, client):
        resp = client.get("/study/1/export/pdf")
        assert resp.status_code == 200
        assert resp.data[:5] == b"%PDF-"

    def test_export_docx(self, client):
        resp = client.get("/study/1/export/docx")
        assert resp.status_code == 200
        assert resp.data[:2] == b"PK"

    def test_export_invalid_format(self, client):
        resp = client.get("/study/1/export/invalid")
        assert resp.status_code == 404

    def test_export_missing_set(self, client):
        resp = client.get("/study/9999/export/tsv")
        assert resp.status_code == 404


# --- Delete API ---


class TestStudyDelete:
    def test_delete_study_set(self, client):
        resp = client.delete("/api/study-sets/1")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["ok"] is True

    def test_delete_missing_set(self, client):
        resp = client.delete("/api/study-sets/9999")
        assert resp.status_code == 404


# --- Class quizzes API ---


class TestClassQuizzesAPI:
    def test_get_class_quizzes(self, client):
        resp = client.get("/api/classes/1/quizzes")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "title" in data[0]
