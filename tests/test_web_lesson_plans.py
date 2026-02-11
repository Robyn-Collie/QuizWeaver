"""
Tests for QuizWeaver lesson plan web routes.

Covers list, generate, detail, edit, export, delete, and generate-quiz routes.
"""

import json
import os
import tempfile

import pytest

from src.database import (
    Base, Class, LessonPlan,
    get_engine, get_session,
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

    # Seed a lesson plan
    plan_data = {
        "learning_objectives": "Students will define photosynthesis.",
        "materials_needed": "Textbook, whiteboard.",
        "warm_up": "Photo observation activity.",
        "direct_instruction": "Mini-lecture on photosynthesis.",
        "guided_practice": "Pair work: label diagram.",
        "independent_practice": "Answer 5 questions.",
        "assessment": "Exit ticket.",
        "closure": "Review objectives.",
        "differentiation": "Below grade: word bank. Advanced: extension.",
        "standards_alignment": "SOL 7.1.",
    }

    plan = LessonPlan(
        class_id=cls.id,
        title="Test Lesson Plan",
        topics=json.dumps(["Photosynthesis"]),
        standards=json.dumps(["SOL 7.1"]),
        grade_level="7th Grade",
        duration_minutes=50,
        plan_data=json.dumps(plan_data),
        status="draft",
    )
    session.add(plan)
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
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


@pytest.fixture
def anon_client(app):
    """Unauthenticated test client."""
    return app.test_client()


# --- Auth tests ---

class TestLessonPlanAuth:
    def test_list_requires_login(self, anon_client):
        resp = anon_client.get("/lesson-plans")
        assert resp.status_code == 303

    def test_generate_requires_login(self, anon_client):
        resp = anon_client.get("/lesson-plans/generate")
        assert resp.status_code == 303

    def test_detail_requires_login(self, anon_client):
        resp = anon_client.get("/lesson-plans/1")
        assert resp.status_code == 303


# --- List route ---

class TestLessonPlanList:
    def test_list_page_loads(self, client):
        resp = client.get("/lesson-plans")
        assert resp.status_code == 200
        assert b"Lesson Plans" in resp.data

    def test_list_shows_plans(self, client):
        resp = client.get("/lesson-plans")
        assert b"Test Lesson Plan" in resp.data

    def test_list_filter_by_class(self, client):
        resp = client.get("/lesson-plans?class_id=1")
        assert resp.status_code == 200
        assert b"Test Lesson Plan" in resp.data

    def test_list_search(self, client):
        resp = client.get("/lesson-plans?q=Photosynthesis")
        # The title doesn't contain "Photosynthesis" directly but the plan exists
        assert resp.status_code == 200


# --- Generate route ---

class TestLessonPlanGenerate:
    def test_generate_form_loads(self, client):
        resp = client.get("/lesson-plans/generate")
        assert resp.status_code == 200
        assert b"Generate Lesson Plan" in resp.data

    def test_generate_post_success(self, client):
        resp = client.post("/lesson-plans/generate", data={
            "class_id": "1",
            "topics": "Ecosystems",
            "standards": "SOL 7.1",
            "duration_minutes": "50",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_generate_post_no_class(self, client):
        resp = client.post("/lesson-plans/generate", data={
            "topics": "Ecosystems",
        }, follow_redirects=False)
        assert resp.status_code == 400

    def test_generate_post_with_all_fields(self, client):
        resp = client.post("/lesson-plans/generate", data={
            "class_id": "1",
            "topics": "Photosynthesis, Respiration",
            "standards": "SOL 7.1, SOL 7.2",
            "duration_minutes": "90",
            "grade_level": "8th Grade",
        }, follow_redirects=False)
        assert resp.status_code == 303


# --- Detail route ---

class TestLessonPlanDetail:
    def test_detail_page_loads(self, client):
        resp = client.get("/lesson-plans/1")
        assert resp.status_code == 200
        assert b"Test Lesson Plan" in resp.data

    def test_detail_shows_sections(self, client):
        resp = client.get("/lesson-plans/1")
        assert b"Learning Objectives" in resp.data
        assert b"Warm-Up" in resp.data
        assert b"Direct Instruction" in resp.data

    def test_detail_shows_ai_draft_banner(self, client):
        resp = client.get("/lesson-plans/1")
        assert b"AI-generated draft" in resp.data

    def test_detail_not_found(self, client):
        resp = client.get("/lesson-plans/9999")
        assert resp.status_code == 404


# --- Edit route ---

class TestLessonPlanEdit:
    def test_edit_section(self, client):
        resp = client.post("/lesson-plans/1/edit", data={
            "section_key": "warm_up",
            "section_content": "Updated warm-up activity.",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_edit_section_persists(self, client):
        client.post("/lesson-plans/1/edit", data={
            "section_key": "closure",
            "section_content": "New closure text.",
        })
        resp = client.get("/lesson-plans/1")
        assert b"New closure text." in resp.data

    def test_edit_invalid_plan(self, client):
        resp = client.post("/lesson-plans/9999/edit", data={
            "section_key": "warm_up",
            "section_content": "Test",
        })
        assert resp.status_code == 404


# --- Export routes ---

class TestLessonPlanExport:
    def test_export_pdf(self, client):
        resp = client.get("/lesson-plans/1/export/pdf")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    def test_export_docx(self, client):
        resp = client.get("/lesson-plans/1/export/docx")
        assert resp.status_code == 200
        assert "wordprocessingml" in resp.content_type

    def test_export_invalid_format(self, client):
        resp = client.get("/lesson-plans/1/export/txt")
        assert resp.status_code == 400

    def test_export_not_found(self, client):
        resp = client.get("/lesson-plans/9999/export/pdf")
        assert resp.status_code == 404


# --- Delete route ---

class TestLessonPlanDelete:
    def test_delete_plan(self, client):
        # Generate a new plan to delete
        client.post("/lesson-plans/generate", data={
            "class_id": "1",
            "topics": "Temporary",
        })
        resp = client.post("/lesson-plans/2/delete", follow_redirects=False)
        assert resp.status_code == 303

    def test_delete_not_found(self, client):
        resp = client.post("/lesson-plans/9999/delete")
        assert resp.status_code == 404
