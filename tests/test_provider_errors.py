"""
Tests for improved LLM provider error messages.

Verifies:
- Provider factory raises teacher-friendly error messages mentioning Settings/Setup Wizard
- Each provider type with missing credentials gives actionable guidance
- Test-provider endpoint classifies common HTTP errors with helpful hints
- Error types (ValueError, ImportError) remain unchanged
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from src.llm_provider import (
    AnthropicProvider,
    VertexAIProvider,
    VertexAnthropicProvider,
    get_provider,
)

# ---------------------------------------------------------------------------
# 1. Provider factory: teacher-friendly error messages
# ---------------------------------------------------------------------------


class TestGeminiMissingKey:
    """Gemini provider without API key mentions Settings and Setup Wizard."""

    def test_gemini_missing_key_mentions_settings(self):
        config = {"llm": {"provider": "gemini", "mode": "production"}}
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="Settings"):
                get_provider(config, web_mode=True)
        finally:
            if old_key:
                os.environ["GEMINI_API_KEY"] = old_key

    def test_gemini_missing_key_mentions_setup_wizard(self):
        config = {"llm": {"provider": "gemini", "mode": "production"}}
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="Setup Wizard"):
                get_provider(config, web_mode=True)
        finally:
            if old_key:
                os.environ["GEMINI_API_KEY"] = old_key

    def test_gemini_missing_key_mentions_env_var(self):
        config = {"llm": {"provider": "gemini", "mode": "production"}}
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                get_provider(config, web_mode=True)
        finally:
            if old_key:
                os.environ["GEMINI_API_KEY"] = old_key


class TestAnthropicMissingKey:
    """Anthropic provider without API key mentions Settings and Setup Wizard."""

    def test_anthropic_missing_key_mentions_settings(self):
        config = {"llm": {"provider": "anthropic", "mode": "production"}}
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="Settings"):
                get_provider(config, web_mode=True)
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key

    def test_anthropic_missing_key_mentions_setup_wizard(self):
        config = {"llm": {"provider": "anthropic", "mode": "production"}}
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="Setup Wizard"):
                get_provider(config, web_mode=True)
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key

    def test_anthropic_missing_key_mentions_env_var(self):
        config = {"llm": {"provider": "anthropic", "mode": "production"}}
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                get_provider(config, web_mode=True)
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key


class TestOpenAIMissingKey:
    """OpenAI provider without API key mentions Settings and Setup Wizard."""

    def test_openai_missing_key_mentions_settings(self):
        config = {"llm": {"provider": "openai", "mode": "production"}}
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="Settings"):
                get_provider(config, web_mode=True)
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key


class TestVertexMissingConfig:
    """Vertex AI provider without project config mentions Settings."""

    def test_vertex_missing_config_mentions_settings(self):
        config = {"llm": {"provider": "vertex", "mode": "production"}}
        with pytest.raises((ValueError, ImportError), match="Settings|pip install"):
            get_provider(config, web_mode=True)

    def test_vertex_anthropic_missing_config_mentions_settings(self):
        config = {"llm": {"provider": "vertex-anthropic", "mode": "production"}}
        with pytest.raises((ValueError, ImportError), match="Settings|pip install"):
            get_provider(config, web_mode=True)


class TestOpenAICompatibleMissingBaseURL:
    """OpenAI-compatible provider without base_url mentions Settings."""

    def test_missing_base_url_mentions_settings(self):
        config = {"llm": {"provider": "openai-compatible", "mode": "production"}}
        with pytest.raises(ValueError, match="Settings"):
            get_provider(config, web_mode=True)

    def test_missing_base_url_mentions_ollama_example(self):
        config = {"llm": {"provider": "openai-compatible", "mode": "production"}}
        with pytest.raises(ValueError, match="Ollama"):
            get_provider(config, web_mode=True)


class TestUnsupportedProviderMessage:
    """Unsupported provider gives actionable message."""

    def test_unsupported_provider_mentions_settings(self):
        config = {"llm": {"provider": "nonexistent-provider", "mode": "production"}}
        with pytest.raises(ValueError, match="Settings"):
            get_provider(config, web_mode=True)


class TestImportErrorMessages:
    """ImportError messages give pip install instructions."""

    def test_vertex_import_error_mentions_pip_install(self):
        config = {"llm": {"provider": "vertex", "mode": "production"}}
        with patch("src.llm_provider._GENAI_AVAILABLE", False):
            with pytest.raises(ImportError, match="pip install google-genai"):
                get_provider(config, web_mode=True)

    def test_anthropic_init_import_error_mentions_pip_install(self):
        with patch("src.llm_provider._ANTHROPIC_AVAILABLE", False):
            with pytest.raises(ImportError, match="pip install anthropic"):
                AnthropicProvider(api_key="test-key")

    def test_vertex_anthropic_init_import_error_mentions_pip_install(self):
        with patch("src.llm_provider._ANTHROPIC_AVAILABLE", False):
            with pytest.raises(ImportError, match=r"pip install anthropic\[vertex\]"):
                VertexAnthropicProvider(project_id="proj", location="us-east5")

    def test_vertex_ai_init_import_error_mentions_pip_install(self):
        with patch("src.llm_provider._GENAI_AVAILABLE", False):
            with pytest.raises(ImportError, match="pip install google-genai"):
                VertexAIProvider(project_id="proj", location="us-central1")


# ---------------------------------------------------------------------------
# 2. Test-provider endpoint: error classification with helpful hints
# ---------------------------------------------------------------------------


class TestTestProviderErrorClassification:
    """Test that the test-provider endpoint adds helpful hints to common errors."""

    @pytest.fixture
    def app(self):
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        from src.database import Base, get_engine, get_session

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
    def client(self, app):
        c = app.test_client()
        c.post("/login", data={"username": "teacher", "password": "quizweaver"})
        return c

    def test_401_error_adds_api_key_hint(self, client):
        """401 Unauthorized errors get a hint about checking the API key."""
        with patch("src.web.routes.get_provider") as mock_gp:
            mock_gp.side_effect = Exception("HTTP 401 Unauthorized")
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "gemini", "api_key": "bad-key"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
            assert "API key" in data["message"]
            assert "expired" in data["message"]

    def test_403_error_adds_permission_hint(self, client):
        """403 Forbidden errors get a hint about permissions."""
        with patch("src.web.routes.get_provider") as mock_gp:
            mock_gp.side_effect = Exception("HTTP 403 Forbidden")
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "gemini", "api_key": "key"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
            assert "permission" in data["message"]

    def test_404_error_adds_model_hint(self, client):
        """404 Not Found errors get a hint about the model name."""
        with patch("src.web.routes.get_provider") as mock_gp:
            mock_gp.side_effect = Exception("HTTP 404 Not Found")
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "gemini", "api_key": "key"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
            assert "model name" in data["message"]

    def test_429_error_adds_rate_limit_hint(self, client):
        """429 rate limit errors get a hint about waiting or checking billing."""
        with patch("src.web.routes.get_provider") as mock_gp:
            mock_gp.side_effect = Exception("HTTP 429 Too Many Requests")
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "gemini", "api_key": "key"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
            assert "rate limit" in data["message"] or "quota" in data["message"]

    def test_connection_error_adds_network_hint(self, client):
        """Connection errors get a hint about internet and endpoint URL."""
        with patch("src.web.routes.get_provider") as mock_gp:
            mock_gp.side_effect = Exception("Connection refused")
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "openai-compatible", "base_url": "http://localhost:9999"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
            assert "internet connection" in data["message"] or "endpoint" in data["message"].lower()

    def test_timeout_error_adds_timeout_hint(self, client):
        """Timeout errors get a hint about the provider being slow."""
        with patch("src.web.routes.get_provider") as mock_gp:
            mock_gp.side_effect = Exception("Request timed out")
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "gemini", "api_key": "key"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
            assert "internet connection" in data["message"] or "too long" in data["message"]

    def test_missing_key_error_contains_settings_guidance(self, client):
        """Missing API key errors should contain teacher-friendly guidance."""
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "gemini"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
            assert "Settings" in data["message"] or "Setup Wizard" in data["message"]
        finally:
            if old_key:
                os.environ["GEMINI_API_KEY"] = old_key
