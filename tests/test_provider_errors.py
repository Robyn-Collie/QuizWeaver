"""
Tests for improved LLM provider error messages.

Verifies:
- Provider factory raises teacher-friendly error messages mentioning Settings/Setup Wizard
- Each provider type with missing credentials gives actionable guidance
- Test-provider endpoint classifies common HTTP errors with helpful hints
- Error types (ValueError, ImportError) remain unchanged
- ProviderError class and _classify_provider_error function
- ProviderError is caught by web routes and shown as flash messages
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from src.llm_provider import (
    AnthropicProvider,
    ProviderError,
    VertexAIProvider,
    VertexAnthropicProvider,
    _classify_provider_error,
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
# 2. ProviderError class and error classification
# ---------------------------------------------------------------------------


class TestProviderErrorClass:
    """Test the ProviderError exception class."""

    def test_provider_error_has_user_message(self):
        err = ProviderError("Something went wrong", provider_name="gemini", error_code="auth")
        assert err.user_message == "Something went wrong"
        assert err.provider_name == "gemini"
        assert err.error_code == "auth"

    def test_provider_error_is_exception(self):
        err = ProviderError("test message")
        assert isinstance(err, Exception)
        assert str(err) == "test message"

    def test_provider_error_default_attributes(self):
        err = ProviderError("msg")
        assert err.provider_name == ""
        assert err.error_code == ""


class TestClassifyProviderError:
    """Test _classify_provider_error for common HTTP and network errors."""

    def test_401_unauthorized(self):
        err = _classify_provider_error(Exception("HTTP 401 Unauthorized"), "Gemini")
        assert isinstance(err, ProviderError)
        assert err.error_code == "auth"
        assert "incorrect or expired" in err.user_message
        assert "Setup Wizard" in err.user_message

    def test_invalid_api_key(self):
        err = _classify_provider_error(Exception("Invalid API key provided"), "Gemini")
        assert err.error_code == "auth"

    def test_403_forbidden(self):
        err = _classify_provider_error(Exception("HTTP 403 Forbidden"), "OpenAI")
        assert err.error_code == "permission"
        assert "permission" in err.user_message

    def test_404_not_found(self):
        err = _classify_provider_error(Exception("HTTP 404 Not Found"), "Gemini")
        assert err.error_code == "not_found"
        assert "Model not found" in err.user_message

    def test_429_rate_limit(self):
        err = _classify_provider_error(Exception("HTTP 429 Too Many Requests"), "Gemini")
        assert err.error_code == "rate_limit"
        assert "Rate limit" in err.user_message or "quota" in err.user_message

    def test_quota_exhausted(self):
        err = _classify_provider_error(Exception("Resource exhausted: quota"), "Gemini")
        assert err.error_code == "rate_limit"

    def test_timeout(self):
        err = _classify_provider_error(Exception("Request timed out"), "Anthropic")
        assert err.error_code == "timeout"
        assert "internet connection" in err.user_message

    def test_deadline_exceeded(self):
        err = _classify_provider_error(Exception("Deadline exceeded"), "Gemini")
        assert err.error_code == "timeout"

    def test_connection_refused(self):
        err = _classify_provider_error(Exception("Connection refused"), "OpenAI-compatible")
        assert err.error_code == "connection"
        assert "internet connection" in err.user_message

    def test_dns_resolution_failure(self):
        err = _classify_provider_error(Exception("DNS resolution failed"), "Gemini")
        assert err.error_code == "connection"

    def test_billing_issue(self):
        err = _classify_provider_error(Exception("Billing account not active"), "Gemini")
        assert err.error_code == "billing"
        assert "payment" in err.user_message

    def test_unknown_error_fallback(self):
        err = _classify_provider_error(Exception("Something completely unknown"), "Gemini")
        assert err.error_code == "unknown"
        assert "Mock mode" in err.user_message
        assert "Gemini" in err.user_message

    def test_error_preserves_provider_name(self):
        err = _classify_provider_error(Exception("test"), "My Provider")
        assert err.provider_name == "My Provider"


# ---------------------------------------------------------------------------
# 3. Test-provider endpoint: error classification with helpful hints
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

        flask_app.config["WTF_CSRF_ENABLED"] = False
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
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        return c

    def test_401_error_adds_api_key_hint(self, client):
        """401 Unauthorized errors get a hint about checking the API key."""
        with patch("src.web.blueprints.settings.get_provider") as mock_gp:
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
        with patch("src.web.blueprints.settings.get_provider") as mock_gp:
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
        with patch("src.web.blueprints.settings.get_provider") as mock_gp:
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
        with patch("src.web.blueprints.settings.get_provider") as mock_gp:
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
        with patch("src.web.blueprints.settings.get_provider") as mock_gp:
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
        with patch("src.web.blueprints.settings.get_provider") as mock_gp:
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

    def test_provider_error_returns_error_code(self, client):
        """ProviderError includes error_code in JSON response."""
        with patch("src.web.blueprints.settings.get_provider") as mock_gp:
            pe = ProviderError("Auth failed", provider_name="gemini", error_code="auth")
            mock_gp.side_effect = pe
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "gemini", "api_key": "bad"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
            assert data["error_code"] == "auth"
            assert data["message"] == "Auth failed"


# ---------------------------------------------------------------------------
# 4. Last-used provider per task type
# ---------------------------------------------------------------------------


class TestLastUsedProvider:
    """Test that last-used provider is saved and pre-selected."""

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
        flask_app.config["WTF_CSRF_ENABLED"] = False
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
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        return c

    def test_quiz_generate_form_shows_last_provider(self, client, app):
        """Quiz generate form pre-selects the last-used provider."""
        # Set last_provider in config
        app.config["APP_CONFIG"]["last_provider"] = {"quiz": "gemini"}

        # Create a class first
        from src.database import get_session

        session = get_session(app.config["DB_ENGINE"])
        from src.classroom import create_class

        cls = create_class(session, "Test Class")

        response = client.get(f"/classes/{cls.id}/generate?skip_onboarding=1")
        assert response.status_code == 200
        html = response.data.decode()
        # The gemini option should have 'selected' attribute
        assert 'value="gemini"' in html
        # Check selected is on the gemini option line
        assert "selected" in html

    def test_study_generate_form_shows_last_provider(self, client, app):
        """Study generate form pre-selects the last-used provider."""
        app.config["APP_CONFIG"]["last_provider"] = {"study": "anthropic"}

        response = client.get("/study/generate?skip_onboarding=1")
        assert response.status_code == 200
        html = response.data.decode()
        assert 'value="anthropic"' in html

    def test_quiz_generation_saves_last_provider(self, client, app):
        """Successful quiz generation saves the provider to last_provider config."""
        from src.database import get_session

        session = get_session(app.config["DB_ENGINE"])
        from src.classroom import create_class

        cls = create_class(session, "Test Class 2")

        with patch("src.web.blueprints.quizzes.generate_quiz") as mock_gen:
            # Mock a successful quiz generation
            from unittest.mock import MagicMock

            mock_quiz = MagicMock()
            mock_quiz.id = 1
            mock_gen.return_value = mock_quiz

            with patch("src.web.blueprints.quizzes.save_config"):
                response = client.post(
                    f"/classes/{cls.id}/generate",
                    data={
                        "num_questions": "5",
                        "provider": "gemini",
                        "question_types": "mc",
                    },
                    follow_redirects=False,
                )

            # Config should have been updated
            config = app.config["APP_CONFIG"]
            assert config.get("last_provider", {}).get("quiz") == "gemini"

    def test_no_provider_override_does_not_save(self, client, app):
        """When no provider override is given, last_provider is not updated."""
        app.config["APP_CONFIG"].pop("last_provider", None)

        from src.database import get_session

        session = get_session(app.config["DB_ENGINE"])
        from src.classroom import create_class

        cls = create_class(session, "Test Class 3")

        with patch("src.web.blueprints.quizzes.generate_quiz") as mock_gen:
            from unittest.mock import MagicMock

            mock_quiz = MagicMock()
            mock_quiz.id = 1
            mock_gen.return_value = mock_quiz

            response = client.post(
                f"/classes/{cls.id}/generate",
                data={
                    "num_questions": "5",
                    "provider": "",  # empty = use default
                    "question_types": "mc",
                },
                follow_redirects=False,
            )

        # last_provider should not be set
        assert "last_provider" not in app.config["APP_CONFIG"] or \
               "quiz" not in app.config["APP_CONFIG"].get("last_provider", {})

    def test_config_last_provider_structure(self):
        """Verify the config structure for last_provider."""
        config = {
            "llm": {"provider": "mock"},
            "last_provider": {
                "quiz": "gemini",
                "study": "anthropic",
                "rubric": "gemini-3-flash",
                "lesson_plan": "mock",
                "reteach": "gemini",
            },
        }
        assert config["last_provider"]["quiz"] == "gemini"
        assert config["last_provider"]["study"] == "anthropic"
        assert config["last_provider"]["rubric"] == "gemini-3-flash"
        assert config["last_provider"]["lesson_plan"] == "mock"
        assert config["last_provider"]["reteach"] == "gemini"
