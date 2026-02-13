"""
Tests for UI polish features (Session 6): dark mode, toasts, print, health.
"""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)
    cls = Class(name="Test Class", grade_level="8th Grade", subject="Math")
    session.add(cls)
    session.commit()
    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "8th Grade"},
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


# ============================================================
# TestDarkMode
# ============================================================


class TestDarkMode:
    """Test dark mode UI elements."""

    def test_theme_toggle_in_html(self, client):
        """Dashboard HTML includes theme toggle button."""
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert b"theme-toggle" in resp.data

    def test_theme_script_in_html(self, client):
        """Dashboard HTML includes toggleTheme function."""
        resp = client.get("/dashboard")
        assert b"toggleTheme" in resp.data

    def test_dark_css_vars_exist(self, app):
        """CSS file contains dark theme variables."""
        css_path = os.path.join(app.static_folder, "css", "style.css")
        with open(css_path) as f:
            css = f.read()
        assert 'data-theme="dark"' in css
        assert "--bg: #1a1e24" in css


# ============================================================
# TestToast
# ============================================================


class TestToast:
    """Test toast notification elements."""

    def test_toast_container_in_html(self, client):
        """Dashboard HTML includes toast container."""
        resp = client.get("/dashboard")
        assert b"toastContainer" in resp.data

    def test_show_toast_script(self, client):
        """Dashboard HTML includes showToast function."""
        resp = client.get("/dashboard")
        assert b"showToast" in resp.data


# ============================================================
# TestPrint
# ============================================================


class TestPrint:
    """Test print CSS."""

    def test_print_media_query_in_css(self, app):
        """CSS file contains @media print block."""
        css_path = os.path.join(app.static_folder, "css", "style.css")
        with open(css_path) as f:
            css = f.read()
        assert "@media print" in css


# ============================================================
# TestHealth
# ============================================================


class TestHealth:
    """Test health check endpoint."""

    def test_health_returns_200(self, anon_client):
        """Health endpoint returns 200 with JSON."""
        resp = anon_client.get("/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"
        assert data["service"] == "quizweaver"

    def test_health_no_auth_required(self, anon_client):
        """Health endpoint does not require authentication."""
        resp = anon_client.get("/health")
        assert resp.status_code == 200
