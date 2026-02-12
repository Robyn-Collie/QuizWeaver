"""
Tests for BL-013: Keyboard Shortcuts.

Verifies that shortcuts.js is loaded, the shortcuts modal
CSS exists, and the keyboard shortcut definitions are correct.
"""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app."""
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
    c = app.test_client()
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


class TestShortcutsLoaded:
    """Verify shortcuts.js is included on pages."""

    def test_shortcuts_js_on_dashboard(self, client):
        resp = client.get("/dashboard")
        html = resp.data.decode()
        assert "shortcuts.js" in html

    def test_shortcuts_js_on_quizzes(self, client):
        resp = client.get("/quizzes")
        html = resp.data.decode()
        assert "shortcuts.js" in html

    def test_shortcuts_js_on_study(self, client):
        resp = client.get("/study")
        html = resp.data.decode()
        assert "shortcuts.js" in html

    def test_shortcuts_js_on_classes(self, client):
        resp = client.get("/classes")
        html = resp.data.decode()
        assert "shortcuts.js" in html

    def test_shortcuts_js_on_help(self, client):
        resp = client.get("/help")
        html = resp.data.decode()
        assert "shortcuts.js" in html


class TestShortcutsFileContent:
    """Verify the shortcuts JS file has expected content."""

    def test_shortcuts_file_exists(self):
        path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "shortcuts.js")
        assert os.path.exists(path)

    def test_shortcuts_has_help_modal(self):
        path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "shortcuts.js")
        content = open(path).read()
        assert "shortcuts-modal" in content
        assert "toggleHelpModal" in content

    def test_shortcuts_has_navigation(self):
        path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "shortcuts.js")
        content = open(path).read()
        assert "/dashboard" in content
        assert "/quizzes" in content
        assert "/study" in content

    def test_shortcuts_has_chord_support(self):
        path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "shortcuts.js")
        content = open(path).read()
        assert "pendingPrefix" in content
        assert "CHORD_DELAY" in content

    def test_shortcuts_skips_input_fields(self):
        path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "shortcuts.js")
        content = open(path).read()
        assert "isInputFocused" in content


class TestShortcutsCSS:
    """Verify shortcuts modal CSS is present."""

    def test_shortcuts_modal_css(self, client):
        resp = client.get("/static/css/style.css")
        css = resp.data.decode()
        assert "shortcuts-modal" in css
        assert "shortcuts-table" in css
        assert "shortcut-keys" in css
