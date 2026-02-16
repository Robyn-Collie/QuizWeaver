"""
Tests for Session 16 Wave 1 quick fixes:
- F14: CSRF token in quiz_edit.js API calls
- F9: Regeneration loading spinner CSS class
- F5: Standards optional helper text on class forms
- F15: Delete image description API endpoint + button
- F4: Lesson logging guidance on generate form
"""

import json
import os

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session


@pytest.fixture
def app_with_image_desc(db_path):
    """Flask app with a quiz question that has an image_description field."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Test Class",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    quiz = Quiz(
        title="Image Desc Quiz",
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
        data=json.dumps({
            "type": "mc",
            "options": ["A process", "A disease", "A planet", "A tool"],
            "correct_index": 0,
            "image_description": "A diagram showing the process of photosynthesis",
        }),
    )
    session.add(q1)
    session.commit()

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {
            "default_grade_level": "7th Grade Science",
            "quiz_title": "Test Quiz",
            "sol_standards": [],
            "target_image_ratio": 0.0,
            "generate_ai_images": False,
            "interactive_review": False,
        },
    }
    app = create_app(test_config)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    yield app

    app.config["DB_ENGINE"].dispose()


@pytest.fixture
def client_with_image_desc(app_with_image_desc):
    """Logged-in client for the image description test app."""
    with app_with_image_desc.test_client() as client:
        with client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        yield client


# --- F14: CSRF token in quiz_edit.js ---


class TestCsrfInQuizEditJs:
    """Verify quiz_edit.js includes CSRF token in all API calls."""

    def test_csrf_helper_function_exists(self):
        """The getCsrfToken() helper should exist in quiz_edit.js."""
        js_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "js", "quiz_edit.js"
        )
        with open(js_path, "r") as f:
            content = f.read()
        assert "function getCsrfToken()" in content

    def test_csrf_in_json_put(self):
        """jsonPut() should include X-CSRFToken header."""
        js_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "js", "quiz_edit.js"
        )
        with open(js_path, "r") as f:
            content = f.read()
        # Find the jsonPut function and check it has CSRF
        put_idx = content.index("function jsonPut")
        put_block = content[put_idx : put_idx + 300]
        assert "X-CSRFToken" in put_block
        assert "getCsrfToken()" in put_block

    def test_csrf_in_json_post(self):
        """jsonPost() should include X-CSRFToken header."""
        js_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "js", "quiz_edit.js"
        )
        with open(js_path, "r") as f:
            content = f.read()
        post_idx = content.index("function jsonPost")
        post_block = content[post_idx : post_idx + 300]
        assert "X-CSRFToken" in post_block
        assert "getCsrfToken()" in post_block

    def test_csrf_in_json_delete(self):
        """jsonDelete() should include X-CSRFToken header."""
        js_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "js", "quiz_edit.js"
        )
        with open(js_path, "r") as f:
            content = f.read()
        del_idx = content.index("function jsonDelete")
        del_block = content[del_idx : del_idx + 200]
        assert "X-CSRFToken" in del_block
        assert "getCsrfToken()" in del_block

    def test_csrf_in_image_upload(self):
        """Image upload fetch() should include X-CSRFToken header."""
        js_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "js", "quiz_edit.js"
        )
        with open(js_path, "r") as f:
            content = f.read()
        # Find the image upload POST section (formData-based, in change handler)
        upload_idx = content.index("formData.append")
        upload_block = content[upload_idx : upload_idx + 300]
        assert "X-CSRFToken" in upload_block


# --- F9: Regeneration loading spinner ---


class TestRegenSpinner:
    """Verify the regeneration spinner CSS class is applied."""

    def test_regenerating_class_added_in_js(self):
        """The 'regenerating' CSS class should be added to the card on regen submit."""
        js_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "js", "quiz_edit.js"
        )
        with open(js_path, "r") as f:
            content = f.read()
        assert 'card.classList.add("regenerating")' in content

    def test_regenerating_class_removed_on_response(self):
        """The 'regenerating' CSS class should be removed when the response arrives."""
        js_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "js", "quiz_edit.js"
        )
        with open(js_path, "r") as f:
            content = f.read()
        assert 'card.classList.remove("regenerating")' in content

    def test_regenerating_css_exists(self):
        """CSS for .question-card.regenerating should exist in style.css."""
        css_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "css", "style.css"
        )
        with open(css_path, "r") as f:
            content = f.read()
        assert ".question-card.regenerating" in content
        assert "regen-pulse" in content


# --- F15: Delete image description ---


class TestDeleteImageDescription:
    """Verify the image description deletion API endpoint works."""

    def test_delete_image_description_success(self, client_with_image_desc):
        """DELETE /api/questions/1/image-description should clear the field."""
        resp = client_with_image_desc.delete("/api/questions/1/image-description")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

        # Verify the image_description is gone from the question data
        resp2 = client_with_image_desc.get("/quizzes/1")
        assert resp2.status_code == 200
        assert b"Suggested image:" not in resp2.data

    def test_delete_image_description_not_found(self, client_with_image_desc):
        """DELETE /api/questions/999/image-description should return 404."""
        resp = client_with_image_desc.delete("/api/questions/999/image-description")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["ok"] is False

    def test_clear_button_in_detail_template(self):
        """The detail.html template should have a clear-image-desc button."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "quizzes", "detail.html"
        )
        with open(template_path, "r") as f:
            content = f.read()
        assert "btn-clear-image-desc" in content

    def test_clear_handler_in_js(self):
        """quiz_edit.js should handle btn-clear-image-desc clicks."""
        js_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "js", "quiz_edit.js"
        )
        with open(js_path, "r") as f:
            content = f.read()
        assert "btn-clear-image-desc" in content
        assert "/image-description" in content

    def test_image_desc_visible_before_delete(self, client_with_image_desc):
        """The quiz detail page should show 'Suggested image' before deletion."""
        resp = client_with_image_desc.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"Suggested image:" in resp.data
        assert b"photosynthesis" in resp.data


# --- F5: Standards optional at class level ---


class TestStandardsOptional:
    """Verify standards field is marked optional on class forms."""

    def test_new_class_standards_optional_label(self):
        """new.html should label standards as (optional)."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "classes", "new.html"
        )
        with open(template_path, "r") as f:
            content = f.read()
        assert "Standards (optional)" in content

    def test_new_class_standards_hint(self):
        """new.html should have a hint below the standards field."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "classes", "new.html"
        )
        with open(template_path, "r") as f:
            content = f.read()
        assert "select specific standards when generating quizzes" in content

    def test_edit_class_standards_optional_label(self):
        """edit.html should label standards as (optional)."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "classes", "edit.html"
        )
        with open(template_path, "r") as f:
            content = f.read()
        assert "Standards (optional)" in content

    def test_edit_class_standards_hint(self):
        """edit.html should have a hint below the standards field."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "classes", "edit.html"
        )
        with open(template_path, "r") as f:
            content = f.read()
        assert "select specific standards when generating quizzes" in content

    def test_new_class_form_renders(self, flask_client):
        """The new class form should render with optional standards."""
        resp = flask_client.get("/classes/new")
        assert resp.status_code == 200
        assert b"Standards (optional)" in resp.data

    def test_edit_class_form_renders(self, flask_client):
        """The edit class form should render with optional standards."""
        resp = flask_client.get("/classes/1/edit")
        assert resp.status_code == 200
        assert b"Standards (optional)" in resp.data


# --- F4: Lesson logging guidance ---


class TestLessonLoggingGuidance:
    """Verify lesson logging tip appears on generate quiz form."""

    def test_generate_form_has_lesson_tip(self):
        """generate.html should have a lesson logging tip."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "quizzes", "generate.html"
        )
        with open(template_path, "r") as f:
            content = f.read()
        assert "Lesson logging is optional" in content

    def test_generate_form_tip_visible(self, flask_client):
        """The generate form should show the lesson logging tip."""
        resp = flask_client.get("/classes/1/generate")
        assert resp.status_code == 200
        assert b"Lesson logging is optional" in resp.data

    def test_info_tip_css_exists(self):
        """The .info-tip CSS class should exist in style.css."""
        css_path = os.path.join(
            os.path.dirname(__file__), "..", "static", "css", "style.css"
        )
        with open(css_path, "r") as f:
            content = f.read()
        assert ".info-tip" in content
