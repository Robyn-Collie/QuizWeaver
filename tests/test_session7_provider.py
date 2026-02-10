"""
Tests for Session 7 LLM provider test connection feature.

Verifies the POST /api/settings/test-provider endpoint and
the settings page UI additions.
"""

import os
import json
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


@pytest.fixture
def anon_client(app):
    """Create an unauthenticated test client."""
    return app.test_client()


class TestProviderTestEndpoint:
    """Test the POST /api/settings/test-provider API."""

    def test_endpoint_exists(self, client):
        """Endpoint accepts POST requests."""
        response = client.post(
            "/api/settings/test-provider",
            data=json.dumps({"provider": "mock"}),
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_returns_json(self, client):
        """Endpoint returns valid JSON."""
        response = client.post(
            "/api/settings/test-provider",
            data=json.dumps({"provider": "mock"}),
            content_type="application/json",
        )
        data = response.get_json()
        assert data is not None
        assert "success" in data
        assert "message" in data
        assert "latency_ms" in data

    def test_mock_succeeds_instantly(self, client):
        """Mock provider returns instant success."""
        response = client.post(
            "/api/settings/test-provider",
            data=json.dumps({"provider": "mock"}),
            content_type="application/json",
        )
        data = response.get_json()
        assert data["success"] is True
        assert "always available" in data["message"].lower()
        assert data["latency_ms"] == 0

    def test_response_shape_correct(self, client):
        """Response has success, message, and latency_ms fields."""
        response = client.post(
            "/api/settings/test-provider",
            data=json.dumps({"provider": "mock"}),
            content_type="application/json",
        )
        data = response.get_json()
        assert isinstance(data["success"], bool)
        assert isinstance(data["message"], str)
        assert isinstance(data["latency_ms"], int)

    def test_unknown_provider_fails(self, client):
        """Unknown provider name returns failure."""
        response = client.post(
            "/api/settings/test-provider",
            data=json.dumps({"provider": "nonexistent-provider"}),
            content_type="application/json",
        )
        data = response.get_json()
        assert data["success"] is False

    def test_gemini_without_key_fails(self, client):
        """Gemini provider without API key fails."""
        # Ensure no env key is set
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "gemini"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
        finally:
            if old_key:
                os.environ["GEMINI_API_KEY"] = old_key

    def test_openai_without_key_fails(self, client):
        """OpenAI provider without API key fails."""
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "openai"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_openai_compatible_without_base_url_fails(self, client):
        """OpenAI-compatible without base_url fails."""
        response = client.post(
            "/api/settings/test-provider",
            data=json.dumps({"provider": "openai-compatible", "api_key": "test-key"}),
            content_type="application/json",
        )
        data = response.get_json()
        assert data["success"] is False

    def test_empty_body_defaults_to_mock(self, client):
        """Empty request body defaults to mock provider."""
        response = client.post(
            "/api/settings/test-provider",
            data=json.dumps({}),
            content_type="application/json",
        )
        data = response.get_json()
        assert data["success"] is True

    def test_get_returns_405(self, client):
        """GET method is not allowed on test-provider endpoint."""
        response = client.get("/api/settings/test-provider")
        assert response.status_code == 405

    def test_requires_auth(self, anon_client):
        """Endpoint requires authentication."""
        response = anon_client.post(
            "/api/settings/test-provider",
            data=json.dumps({"provider": "mock"}),
            content_type="application/json",
        )
        # Should redirect to login
        assert response.status_code == 303


class TestSettingsPageUI:
    """Test settings page has test connection UI elements."""

    def test_settings_has_test_button(self, client):
        """Settings page includes Test Connection button."""
        response = client.get("/settings")
        html = response.data.decode()
        assert "Test Connection" in html
        assert "testConnectionBtn" in html

    def test_settings_has_field_hints(self, client):
        """Settings page includes hint text below fields."""
        response = client.get("/settings")
        html = response.data.decode()
        assert "stored locally" in html.lower() or "model identifier" in html.lower()

    def test_settings_save_still_works(self, client):
        """Saving settings still works after UI changes."""
        response = client.post(
            "/settings",
            data={"provider": "mock"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        html = response.data.decode()
        assert "Settings saved" in html or "success" in html.lower()
