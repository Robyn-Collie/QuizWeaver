"""
Tests for Session 7 help page clarification.

Verifies mock mode is clearly described as demo/testing,
Provider Setup section is present, and links to Settings.
"""

import os
import tempfile

import pytest

from src.database import Base, get_engine, get_session


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


class TestHelpPage:
    """Test help page content."""

    def test_help_returns_200(self, client):
        """Help page loads successfully."""
        response = client.get("/help")
        assert response.status_code == 200

    def test_mock_described_as_demo(self, client):
        """Mock mode is described as demo or testing mode."""
        response = client.get("/help")
        html = response.data.decode().lower()
        assert "demo" in html or "testing" in html

    def test_links_to_settings(self, client):
        """Help page links to settings for provider configuration."""
        response = client.get("/help")
        html = response.data.decode()
        assert "/settings" in html

    def test_provider_setup_section_exists(self, client):
        """Help page has a Provider Setup section."""
        response = client.get("/help")
        html = response.data.decode()
        assert "Provider Setup" in html
        assert "provider-setup" in html

    def test_mentions_test_connection(self, client):
        """Help page mentions the Test Connection feature."""
        response = client.get("/help")
        html = response.data.decode()
        assert "Test Connection" in html
