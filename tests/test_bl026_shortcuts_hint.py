"""
Tests for BL-026: Keyboard Shortcuts Discoverability Hint.
Verifies the shortcuts hint appears in the footer on pages.
"""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, get_engine, get_session


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)
    cls = Class(
        name="Test Class",
        grade_level="7th Grade",
        subject="Math",
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


class TestShortcutsHint:
    """Keyboard shortcuts hint in footer."""

    def test_hint_present_on_dashboard(self, client):
        """The shortcuts hint appears on the dashboard page."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'id="shortcutsHint"' in html
        assert "shortcuts-hint" in html

    def test_hint_contains_question_mark_key(self, client):
        """The hint tells users to press ? for shortcuts."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert "<kbd>?</kbd>" in html
        assert "keyboard shortcuts" in html.lower()

    def test_hint_present_on_classes_page(self, client):
        """The hint appears on the classes page too (base template)."""
        resp = client.get("/classes")
        html = resp.data.decode()
        assert 'id="shortcutsHint"' in html

    def test_hint_present_on_help_page(self, client):
        """The hint appears on the help page."""
        resp = client.get("/help")
        html = resp.data.decode()
        assert 'id="shortcutsHint"' in html

    def test_hint_in_footer_element(self, client):
        """The hint is inside the footer."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        # The hint should appear after the footer tag
        footer_idx = html.find('class="footer"')
        hint_idx = html.find('id="shortcutsHint"')
        assert footer_idx != -1
        assert hint_idx != -1
        assert hint_idx > footer_idx

    def test_shortcuts_js_loaded(self, client):
        """The shortcuts.js script is loaded on every page."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert "shortcuts.js" in html

    def test_localstorage_hint_logic_present(self, client):
        """The localStorage logic for shortcuts hint is in the page."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert "qw-shortcuts-seen" in html
