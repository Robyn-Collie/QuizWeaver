"""
Tests for QuizWeaver variant and rubric web routes.

Covers variant generation, listing, rubric generation, rubric detail,
rubric export, rubric deletion, and auth requirements.
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
    Rubric,
    RubricCriterion,
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

    # Source quiz
    quiz = Quiz(
        title="Photosynthesis Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps(
            {
                "grade_level": "7th Grade",
                "cognitive_framework": "blooms",
            }
        ),
    )
    session.add(quiz)
    session.commit()

    for i in range(3):
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
                    "options": ["A", "B", "C", "D"],
                    "correct_index": 0,
                }
            ),
        )
        session.add(q)
    session.commit()

    # A variant quiz
    variant = Quiz(
        title="ELL Variant",
        class_id=cls.id,
        parent_quiz_id=quiz.id,
        reading_level="ell",
        status="generated",
    )
    session.add(variant)
    session.commit()

    # A rubric
    rubric = Rubric(
        quiz_id=quiz.id,
        title="Test Rubric",
        status="generated",
        config=json.dumps({"provider": "mock"}),
    )
    session.add(rubric)
    session.commit()

    levels_json = json.dumps(
        [
            {"level": 1, "label": "Beginning", "description": "Min understanding"},
            {"level": 2, "label": "Developing", "description": "Partial"},
            {"level": 3, "label": "Proficient", "description": "Good"},
            {"level": 4, "label": "Advanced", "description": "Excellent"},
        ]
    )
    c1 = RubricCriterion(
        rubric_id=rubric.id,
        sort_order=0,
        criterion="Content Knowledge",
        description="Understanding of concepts",
        max_points=10,
        levels=levels_json,
    )
    session.add(c1)
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


class TestVariantAuth:
    def test_generate_variant_requires_login(self, anon_client):
        resp = anon_client.get("/quizzes/1/generate-variant")
        assert resp.status_code == 303

    def test_variants_list_requires_login(self, anon_client):
        resp = anon_client.get("/quizzes/1/variants")
        assert resp.status_code == 303

    def test_generate_rubric_requires_login(self, anon_client):
        resp = anon_client.get("/quizzes/1/generate-rubric")
        assert resp.status_code == 303

    def test_rubric_detail_requires_login(self, anon_client):
        resp = anon_client.get("/rubrics/1")
        assert resp.status_code == 303


# --- Variant routes ---


class TestVariantGeneration:
    def test_generate_variant_form_loads(self, client):
        resp = client.get("/quizzes/1/generate-variant")
        assert resp.status_code == 200
        assert b"Generate" in resp.data
        assert b"Reading Level" in resp.data

    def test_generate_variant_post(self, client):
        resp = client.post(
            "/quizzes/1/generate-variant",
            data={
                "reading_level": "ell",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_generate_variant_invalid_level(self, client):
        resp = client.post(
            "/quizzes/1/generate-variant",
            data={
                "reading_level": "nonexistent",
            },
        )
        assert resp.status_code == 400

    def test_generate_variant_404_quiz(self, client):
        resp = client.get("/quizzes/9999/generate-variant")
        assert resp.status_code == 404


class TestVariantsList:
    def test_variants_list_loads(self, client):
        resp = client.get("/quizzes/1/variants")
        assert resp.status_code == 200
        assert b"Variants" in resp.data

    def test_variants_list_shows_variant(self, client):
        resp = client.get("/quizzes/1/variants")
        assert b"ELL Variant" in resp.data

    def test_variants_list_404_quiz(self, client):
        resp = client.get("/quizzes/9999/variants")
        assert resp.status_code == 404


# --- Rubric routes ---


class TestRubricGeneration:
    def test_generate_rubric_form_loads(self, client):
        resp = client.get("/quizzes/1/generate-rubric")
        assert resp.status_code == 200
        assert b"Generate Rubric" in resp.data

    def test_generate_rubric_post(self, client):
        resp = client.post("/quizzes/1/generate-rubric", data={}, follow_redirects=False)
        assert resp.status_code == 303

    def test_generate_rubric_404_quiz(self, client):
        resp = client.get("/quizzes/9999/generate-rubric")
        assert resp.status_code == 404


class TestRubricDetail:
    def test_rubric_detail_loads(self, client):
        resp = client.get("/rubrics/1")
        assert resp.status_code == 200
        assert b"Test Rubric" in resp.data

    def test_rubric_detail_shows_criteria(self, client):
        resp = client.get("/rubrics/1")
        assert b"Content Knowledge" in resp.data

    def test_rubric_detail_404_missing(self, client):
        resp = client.get("/rubrics/9999")
        assert resp.status_code == 404


class TestRubricExport:
    def test_export_csv(self, client):
        resp = client.get("/rubrics/1/export/csv")
        assert resp.status_code == 200
        assert b"Criterion" in resp.data

    def test_export_docx(self, client):
        resp = client.get("/rubrics/1/export/docx")
        assert resp.status_code == 200
        assert resp.data[:2] == b"PK"

    def test_export_pdf(self, client):
        resp = client.get("/rubrics/1/export/pdf")
        assert resp.status_code == 200
        assert resp.data[:5] == b"%PDF-"

    def test_export_invalid_format(self, client):
        resp = client.get("/rubrics/1/export/invalid")
        assert resp.status_code == 404

    def test_export_missing_rubric(self, client):
        resp = client.get("/rubrics/9999/export/csv")
        assert resp.status_code == 404


class TestRubricDelete:
    def test_delete_rubric(self, client):
        resp = client.delete("/api/rubrics/1")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["ok"] is True

    def test_delete_missing_rubric(self, client):
        resp = client.delete("/api/rubrics/9999")
        assert resp.status_code == 404


# --- Quiz detail integration ---


class TestQuizDetailVariantInfo:
    def test_quiz_detail_shows_variant_buttons(self, client):
        resp = client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"Generate Variant" in resp.data
        assert b"Generate Rubric" in resp.data

    def test_quiz_detail_shows_variant_count(self, client):
        resp = client.get("/quizzes/1")
        assert b"variant" in resp.data.lower()

    def test_quiz_detail_shows_rubric(self, client):
        resp = client.get("/quizzes/1")
        assert b"Test Rubric" in resp.data
