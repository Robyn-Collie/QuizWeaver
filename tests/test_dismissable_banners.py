"""
Tests for BL-021: Dismissable AI notice banners.

Verifies that AI banners have dismiss buttons with data-dismiss-key
attributes and that the dismiss JS is loaded in base.html.
"""

import os
import tempfile

import pytest

from src.database import Base, get_engine, get_session

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


class TestDismissableBaseScript:
    """Test that base.html includes AI dismiss JS."""

    def test_dismiss_js_in_base(self, client):
        """Base template includes the dismiss sessionStorage JS."""
        response = client.get("/help")
        html = response.data.decode()
        assert "qw_dismissed_" in html
        assert "sessionStorage" in html

    def test_dismiss_js_uses_data_dismiss_key(self, client):
        """JS references data-dismiss-key attribute."""
        response = client.get("/help")
        html = response.data.decode()
        assert "data-dismiss-key" in html


class TestQuizDetailBanner:
    """Test quiz detail template has dismissable banner."""

    def test_quiz_detail_has_dismiss_key(self):
        """Quiz detail template has data-dismiss-key attribute."""
        content = _read_template(os.path.join("quizzes", "detail.html"))
        assert 'data-dismiss-key="quiz-detail"' in content

    def test_quiz_detail_has_dismiss_button(self):
        """Quiz detail template has dismiss button."""
        content = _read_template(os.path.join("quizzes", "detail.html"))
        assert "ai-notice-dismiss" in content

    def test_quiz_detail_links_to_ai_section(self):
        """Quiz detail banner links to help#understanding-ai."""
        content = _read_template(os.path.join("quizzes", "detail.html"))
        assert "/help#understanding-ai" in content


class TestLessonNewBanner:
    """Test new lesson template has dismissable privacy banner."""

    def test_lesson_new_has_dismiss_key(self):
        """Lesson new template has data-dismiss-key attribute."""
        content = _read_template(os.path.join("lessons", "new.html"))
        assert 'data-dismiss-key="lesson-privacy"' in content

    def test_lesson_new_has_dismiss_button(self):
        """Lesson new template has dismiss button."""
        content = _read_template(os.path.join("lessons", "new.html"))
        assert "ai-notice-dismiss" in content


class TestStudyDetailBanner:
    """Test study detail page would have dismissable banner."""

    def test_study_detail_template_has_dismiss_key(self):
        """Study detail template contains dismiss key attribute."""
        import os

        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "study", "detail.html")
        with open(template_path) as f:
            content = f.read()
        assert 'data-dismiss-key="study-detail"' in content
        assert "ai-notice-dismiss" in content


class TestRubricDetailBanner:
    """Test rubric detail template has dismissable banner."""

    def test_rubric_detail_template_has_dismiss_key(self):
        """Rubric detail template contains dismiss key attribute."""
        import os

        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "rubrics", "detail.html")
        with open(template_path) as f:
            content = f.read()
        assert 'data-dismiss-key="rubric-detail"' in content
        assert "ai-notice-dismiss" in content


class TestReteachBanner:
    """Test reteach suggestions template has dismissable banner."""

    def test_reteach_template_has_dismiss_key(self):
        """Reteach template contains dismiss key attribute."""
        import os

        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "analytics", "reteach.html")
        with open(template_path) as f:
            content = f.read()
        assert 'data-dismiss-key="reteach-suggestions"' in content
        assert "ai-notice-dismiss" in content


class TestDismissCSS:
    """Test dismiss button CSS exists."""

    def test_dismiss_css_exists(self):
        """CSS file contains ai-notice-dismiss styles."""
        import os

        css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
        with open(css_path) as f:
            content = f.read()
        assert ".ai-notice-dismiss" in content

    def test_dismiss_key_padding(self):
        """CSS adds padding-right for banners with dismiss keys."""
        import os

        css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
        with open(css_path) as f:
            content = f.read()
        assert "data-dismiss-key" in content
        assert "padding-right" in content


class TestAllBannersHaveDismiss:
    """Verify all ai-notice elements have dismiss functionality."""

    def test_all_templates_have_dismiss_keys(self):
        """Every ai-notice in templates has a data-dismiss-key attribute."""
        import os
        import re

        templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        missing = []
        for root, dirs, files in os.walk(templates_dir):
            for fname in files:
                if not fname.endswith(".html"):
                    continue
                path = os.path.join(root, fname)
                with open(path) as f:
                    content = f.read()
                # Find ai-notice divs without data-dismiss-key
                notices = re.findall(r'<div\s+class="ai-notice[^"]*"(?![^>]*data-dismiss-key)', content)
                if notices:
                    missing.append((fname, len(notices)))
        assert missing == [], f"Templates with ai-notice missing data-dismiss-key: {missing}"
