"""
Tests for BL-019: AI Literacy Tooltips throughout the UI.

Verifies that AI literacy tooltips are centralized in tooltip_data.py,
injected via context processor, and present in key templates.
"""

import os
import tempfile
import pytest

from src.database import Base, get_engine, get_session
from src.web.tooltip_data import AI_TOOLTIPS


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def _read_template(relative_path):
    """Read a template file and return its content."""
    path = os.path.join(TEMPLATES_DIR, relative_path)
    with open(path) as f:
        return f.read()


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)
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


class TestTooltipData:
    """Test the centralized tooltip data module."""

    def test_ai_tooltips_is_dict(self):
        """AI_TOOLTIPS is a dictionary."""
        assert isinstance(AI_TOOLTIPS, dict)

    def test_required_keys_present(self):
        """All required tooltip keys are present."""
        required = [
            "cognitive_framework",
            "provider_selection",
            "generation_data",
            "review_reminder",
            "study_review",
            "api_key_privacy",
            "mock_provider",
            "lesson_privacy",
            "rubric_review",
        ]
        for key in required:
            assert key in AI_TOOLTIPS, f"Missing tooltip key: {key}"
            assert len(AI_TOOLTIPS[key]) > 20, f"Tooltip '{key}' is too short"

    def test_tooltips_are_strings(self):
        """All tooltip values are non-empty strings."""
        for key, value in AI_TOOLTIPS.items():
            assert isinstance(value, str), f"Tooltip '{key}' is not a string"
            assert len(value.strip()) > 0, f"Tooltip '{key}' is empty"


class TestContextProcessorInjection:
    """Test that AI tooltips are available in template context."""

    def test_ai_tips_in_help_page(self, client):
        """Help page renders with ai_tips available."""
        response = client.get("/help")
        assert response.status_code == 200

    def test_ai_tips_in_settings_page(self, client):
        """Settings page includes tooltip from ai_tips."""
        response = client.get("/settings")
        html = response.data.decode()
        assert AI_TOOLTIPS["provider_selection"] in html

    def test_ai_tips_in_settings_api_key(self, client):
        """Settings page has API key privacy tooltip."""
        response = client.get("/settings")
        html = response.data.decode()
        assert AI_TOOLTIPS["api_key_privacy"] in html


class TestGenerateFormTooltips:
    """Test tooltips on the quiz generation form."""

    def test_cognitive_framework_tooltip(self):
        """Generate form has cognitive framework AI tooltip."""
        content = _read_template(os.path.join("quizzes", "generate.html"))
        assert "ai_tips.cognitive_framework" in content

    def test_provider_tooltip(self):
        """Generate form has provider selection AI tooltip."""
        content = _read_template(os.path.join("quizzes", "generate.html"))
        assert "ai_tips.provider_selection" in content


class TestDetailPageTooltips:
    """Test tooltips on detail/review pages."""

    def test_quiz_detail_has_review_tooltip(self):
        """Quiz detail page has review reminder tooltip."""
        content = _read_template(os.path.join("quizzes", "detail.html"))
        assert "ai_tips.review_reminder" in content

    def test_study_detail_has_review_tooltip(self):
        """Study detail page has study review tooltip."""
        content = _read_template(os.path.join("study", "detail.html"))
        assert "ai_tips.study_review" in content

    def test_rubric_detail_has_review_tooltip(self):
        """Rubric detail page has rubric review tooltip."""
        content = _read_template(os.path.join("rubrics", "detail.html"))
        assert "ai_tips.rubric_review" in content


class TestTooltipMarkup:
    """Test that tooltip markup uses the existing help-tip pattern."""

    def test_settings_uses_help_tip_class(self):
        """Settings page uses help-tip class for tooltips."""
        content = _read_template("settings.html")
        assert 'class="help-tip"' in content

    def test_generate_uses_help_tip_class(self):
        """Generate form uses help-tip class for AI tooltips."""
        content = _read_template(os.path.join("quizzes", "generate.html"))
        # Check that there are help-tip spans
        assert 'class="help-tip"' in content
