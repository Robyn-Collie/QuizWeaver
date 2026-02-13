"""
Tests for BL-011: Loading Spinners for LLM generation.

Verifies that loading overlays, spinner elements, and data-loading-form attributes
are present on all generation forms (variant, rubric, reteach, quiz, study).
Also verifies the loading CSS and JS are loaded from base.html.
"""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed: one class and one quiz
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
        title="Test Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "7th Grade"}),
    )
    session.add(quiz)
    session.commit()

    q = Question(
        quiz_id=quiz.id,
        text="Sample question?",
        question_type="mc",
        points=1,
        data=json.dumps(
            {
                "options": ["A", "B", "C", "D"],
                "correct_index": 0,
            }
        ),
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
    """Create a logged-in test client."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
    return c


class TestBaseTemplateLoadsAssets:
    """Verify that loading CSS and JS are included in the base template."""

    def test_loading_css_included(self, client):
        """The loading.css stylesheet is loaded on every page."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "loading.css" in html

    def test_loading_js_included(self, client):
        """The loading.js script is loaded on every page."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "loading.js" in html


class TestVariantFormLoadingOverlay:
    """Verify the variant generation form has loading overlay attributes."""

    def test_variant_form_has_data_loading(self, client):
        """Variant generation form has data-loading-form attribute."""
        response = client.get("/quizzes/1/generate-variant")
        html = response.data.decode()
        assert "data-loading-form" in html

    def test_variant_form_has_loading_title(self, client):
        """Variant generation form specifies a loading title."""
        response = client.get("/quizzes/1/generate-variant")
        html = response.data.decode()
        assert "data-loading-title" in html
        assert "Generating Variant" in html

    def test_variant_form_has_loading_message(self, client):
        """Variant generation form specifies a loading message."""
        response = client.get("/quizzes/1/generate-variant")
        html = response.data.decode()
        assert "data-loading-message" in html

    def test_variant_no_old_inline_script(self, client):
        """Old inline script that just changed button text is removed."""
        response = client.get("/quizzes/1/generate-variant")
        html = response.data.decode()
        # The old pattern was: btn.textContent = 'Generating...'
        assert "btn.textContent = 'Generating...'" not in html


class TestRubricFormLoadingOverlay:
    """Verify the rubric generation form has loading overlay attributes."""

    def test_rubric_form_has_data_loading(self, client):
        """Rubric generation form has data-loading-form attribute."""
        response = client.get("/quizzes/1/generate-rubric")
        html = response.data.decode()
        assert "data-loading-form" in html

    def test_rubric_form_has_loading_title(self, client):
        """Rubric generation form specifies a loading title."""
        response = client.get("/quizzes/1/generate-rubric")
        html = response.data.decode()
        assert "data-loading-title" in html
        assert "Generating Rubric" in html

    def test_rubric_form_has_loading_message(self, client):
        """Rubric generation form specifies a loading message."""
        response = client.get("/quizzes/1/generate-rubric")
        html = response.data.decode()
        assert "data-loading-message" in html

    def test_rubric_no_old_inline_script(self, client):
        """Old inline script that just changed button text is removed."""
        response = client.get("/quizzes/1/generate-rubric")
        html = response.data.decode()
        assert "btn.textContent = 'Generating...'" not in html


class TestReteachFormLoadingOverlay:
    """Verify the reteach suggestions form has loading overlay attributes."""

    def test_reteach_form_has_data_loading(self, client):
        """Reteach form has data-loading-form attribute."""
        response = client.get("/classes/1/analytics/reteach")
        html = response.data.decode()
        assert "data-loading-form" in html

    def test_reteach_form_has_loading_title(self, client):
        """Reteach form specifies a loading title."""
        response = client.get("/classes/1/analytics/reteach")
        html = response.data.decode()
        assert "Generating Suggestions" in html


class TestQuizGenerateProgressOverlay:
    """Verify the quiz generation page still has its progress overlay."""

    def test_quiz_generate_has_progress(self, client):
        """Quiz generate form has the detailed progress overlay."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "generate-progress" in html
        assert "progress-card" in html
        assert "progress-checklist" in html

    def test_quiz_generate_has_steps(self, client):
        """Quiz generate form has all 6 progress steps."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "step-0" in html
        assert "step-5" in html


class TestStudyGenerateProgressOverlay:
    """Verify the study generation page still has its progress overlay."""

    def test_study_generate_has_progress(self, client):
        """Study generate form has the progress overlay."""
        response = client.get("/study/generate")
        html = response.data.decode()
        assert "study-generate-progress" in html
        assert "progress-card" in html

    def test_study_generate_has_steps(self, client):
        """Study generate form has all 3 progress steps."""
        response = client.get("/study/generate")
        html = response.data.decode()
        assert "study-step-0" in html
        assert "study-step-1" in html
        assert "study-step-2" in html


class TestQuizDetailRegenButton:
    """Verify quiz detail page has regen button that can use inline spinner."""

    def test_regen_button_exists(self, client):
        """Quiz detail has the Regen button for questions."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert "btn-regen-question" in html
        assert "btn-regen-submit" in html

    def test_quiz_edit_js_loaded(self, client):
        """Quiz detail page loads quiz_edit.js."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert "quiz_edit.js" in html


class TestSettingsTestConnection:
    """Verify settings page test connection button exists."""

    def test_test_connection_button_exists(self, client):
        """Settings page has the Test Connection button."""
        response = client.get("/settings")
        html = response.data.decode()
        assert "testConnectionBtn" in html
        assert "Test Connection" in html

    def test_settings_uses_qw_loading(self, client):
        """Settings page references QWLoading for the test button spinner."""
        response = client.get("/settings")
        html = response.data.decode()
        assert "QWLoading" in html


class TestStaticFiles:
    """Verify static CSS and JS files exist and have expected content."""

    def test_loading_css_exists(self):
        """loading.css file exists."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "loading.css")
        assert os.path.isfile(path)

    def test_loading_css_has_overlay_class(self):
        """loading.css defines the .loading-overlay class."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "loading.css")
        with open(path) as f:
            content = f.read()
        assert ".loading-overlay" in content
        assert ".loading-spinner" in content
        assert ".btn-loading" in content

    def test_loading_js_exists(self):
        """loading.js file exists."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "loading.js")
        assert os.path.isfile(path)

    def test_loading_js_has_qw_loading(self):
        """loading.js exposes window.QWLoading."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "loading.js")
        with open(path) as f:
            content = f.read()
        assert "QWLoading" in content
        assert "data-loading-form" in content
        assert "createOverlay" in content
        assert "setBtnLoading" in content
