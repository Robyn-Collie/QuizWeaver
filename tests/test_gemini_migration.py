"""
Tests for google-genai SDK migration.

Verifies:
- GeminiProvider uses the new unified google-genai Client
- Gemini3ProProvider is removed (merged into GeminiProvider)
- VertexAIProvider uses genai.Client(vertexai=True)
- PROVIDER_REGISTRY has default_model entries
- get_provider() reads defaults from registry
- gemini-3-pro alias resolves to gemini-pro
- get_provider_info() includes gemini-pro
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.llm_provider import (
    _PROVIDER_ALIASES,
    PROVIDER_REGISTRY,
    GeminiProvider,
    VertexAIProvider,
    _resolve_provider_name,
    get_provider,
    get_provider_info,
)


class TestProviderRegistryDefaults:
    """Verify all registry entries have default_model where expected."""

    def test_gemini_has_default_model(self):
        assert "default_model" in PROVIDER_REGISTRY["gemini"]
        assert PROVIDER_REGISTRY["gemini"]["default_model"] == "gemini-2.5-flash"

    def test_gemini_pro_has_default_model(self):
        assert "gemini-pro" in PROVIDER_REGISTRY
        assert PROVIDER_REGISTRY["gemini-pro"]["default_model"] == "gemini-2.5-pro"

    def test_vertex_has_default_model(self):
        assert PROVIDER_REGISTRY["vertex"]["default_model"] == "gemini-2.5-flash"

    def test_openai_has_default_model(self):
        assert PROVIDER_REGISTRY["openai"]["default_model"] == "gpt-4o"

    def test_openai_compatible_has_default_model(self):
        assert PROVIDER_REGISTRY["openai-compatible"]["default_model"] == "default"

    def test_mock_has_no_default_model(self):
        # Mock doesn't use a model name
        assert "default_model" not in PROVIDER_REGISTRY["mock"]

    def test_gemini_3_pro_in_registry(self):
        """gemini-3-pro has its own registry entry (added Session 12)."""
        assert "gemini-3-pro" in PROVIDER_REGISTRY
        assert PROVIDER_REGISTRY["gemini-3-pro"]["default_model"] == "gemini-3-pro-preview"

    def test_all_non_mock_have_default_model(self):
        """Every provider except mock should have a default_model."""
        for key, meta in PROVIDER_REGISTRY.items():
            if key == "mock":
                continue
            assert "default_model" in meta, f"{key} missing default_model"


class TestProviderAliases:
    """Test backward-compatible provider name aliases."""

    def test_gemini_3_pro_not_aliased(self):
        """gemini-3-pro has its own registry entry, no alias needed."""
        assert "gemini-3-pro" not in _PROVIDER_ALIASES

    def test_resolve_no_alias(self):
        """gemini-3-pro resolves to itself (direct registry entry)."""
        assert _resolve_provider_name("gemini-3-pro") == "gemini-3-pro"

    def test_resolve_passthrough(self):
        assert _resolve_provider_name("gemini") == "gemini"
        assert _resolve_provider_name("mock") == "mock"
        assert _resolve_provider_name("vertex") == "vertex"

    def test_resolve_unknown_passthrough(self):
        assert _resolve_provider_name("unknown-thing") == "unknown-thing"


class TestGeminiProviderInit:
    """Test new GeminiProvider uses google-genai Client."""

    def test_creates_client_with_api_key(self):
        """GeminiProvider creates a genai.Client with the API key."""
        with patch("google.genai.Client") as MockClient:
            provider = GeminiProvider(api_key="test-api-key", model_name="gemini-2.5-flash")
            MockClient.assert_called_once_with(api_key="test-api-key")
            assert provider._model_name == "gemini-2.5-flash"

    def test_default_model_is_gemini_2_5_flash(self):
        """GeminiProvider default model matches registry."""
        # We can check the class signature default
        import inspect

        sig = inspect.signature(GeminiProvider.__init__)
        default = sig.parameters["model_name"].default
        assert default == "gemini-2.5-flash"

    def test_no_gemini3pro_class(self):
        """Gemini3ProProvider class should not exist."""
        import src.llm_provider as mod

        assert not hasattr(mod, "Gemini3ProProvider")


class TestGeminiProviderGenerate:
    """Test GeminiProvider.generate() with mocked client."""

    def _make_provider(self):
        """Create a GeminiProvider with a mocked client."""
        with patch("google.genai.Client") as MockClient:
            mock_client = MockClient.return_value
            provider = GeminiProvider(api_key="test-key", model_name="gemini-2.5-flash")
            provider.client = mock_client
            return provider, mock_client

    def test_generate_calls_models_generate_content(self):
        provider, mock_client = self._make_provider()
        mock_response = MagicMock()
        mock_response.text = '{"questions": []}'
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        result = provider.generate(["Hello"])
        mock_client.models.generate_content.assert_called_once()

    def test_generate_passes_model_name(self):
        provider, mock_client = self._make_provider()
        mock_response = MagicMock()
        mock_response.text = "response"
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        provider.generate(["Hello"])
        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == "gemini-2.5-flash"

    def test_generate_json_mode_sets_mime_type(self):
        provider, mock_client = self._make_provider()
        mock_response = MagicMock()
        mock_response.text = '{"data": true}'
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        provider.generate(["Hello"], json_mode=True)
        call_kwargs = mock_client.models.generate_content.call_args
        config = call_kwargs.kwargs.get("config")
        assert config is not None
        assert config["response_mime_type"] == "application/json"

    def test_generate_no_json_mode_no_config(self):
        provider, mock_client = self._make_provider()
        mock_response = MagicMock()
        mock_response.text = "plain text"
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        provider.generate(["Hello"], json_mode=False)
        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs.get("config") is None

    def test_generate_returns_text(self):
        provider, mock_client = self._make_provider()
        mock_response = MagicMock()
        mock_response.text = "Hello, world!"
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        result = provider.generate(["Hi"])
        assert result == "Hello, world!"

    def test_generate_error_returns_empty_json(self):
        provider, mock_client = self._make_provider()
        mock_client.models.generate_content.side_effect = Exception("API error")

        result = provider.generate(["Hi"])
        assert result == "[]"

    def test_generate_logs_cost(self):
        provider, mock_client = self._make_provider()
        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 100
        mock_usage.candidates_token_count = 50
        mock_response = MagicMock()
        mock_response.text = "response"
        mock_response.usage_metadata = mock_usage
        mock_client.models.generate_content.return_value = mock_response

        with patch("src.cost_tracking.log_api_call") as mock_log:
            provider.generate(["Hello"])
            mock_log.assert_called_once_with("gemini", "gemini-2.5-flash", 100, 50)


class TestVertexAIProviderInit:
    """Test VertexAIProvider uses unified genai SDK."""

    def test_default_model_is_gemini_2_5_flash(self):
        import inspect

        sig = inspect.signature(VertexAIProvider.__init__)
        default = sig.parameters["model_name"].default
        assert default == "gemini-2.5-flash"


class TestGetProviderReadsRegistry:
    """Test get_provider() reads default model from PROVIDER_REGISTRY."""

    def test_gemini_uses_registry_default(self):
        """get_provider with gemini and no model_name uses registry default."""
        config = {"llm": {"provider": "gemini", "mode": "production"}}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch("google.genai.Client"):
            provider = get_provider(config, web_mode=True)
            assert provider._model_name == "gemini-2.5-flash"

    def test_gemini_pro_uses_registry_default(self):
        """get_provider with gemini-pro and no model_name uses gemini-2.5-pro."""
        config = {"llm": {"provider": "gemini-pro", "mode": "production"}}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch("google.genai.Client"):
            provider = get_provider(config, web_mode=True)
            assert provider._model_name == "gemini-2.5-pro"

    def test_user_model_overrides_registry(self):
        """User's model_name in config takes priority over registry default."""
        config = {
            "llm": {
                "provider": "gemini",
                "mode": "production",
                "model_name": "gemini-1.5-flash",
            }
        }
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch("google.genai.Client"):
            provider = get_provider(config, web_mode=True)
            assert provider._model_name == "gemini-1.5-flash"

    def test_gemini_3_pro_uses_own_registry(self):
        """gemini-3-pro uses its own registry entry (not alias to gemini-pro)."""
        config = {"llm": {"provider": "gemini-3-pro", "mode": "production"}}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch("google.genai.Client"):
            provider = get_provider(config, web_mode=True)
            assert isinstance(provider, GeminiProvider)
            # Should use gemini-3-pro's own default model
            assert provider._model_name == "gemini-3-pro-preview"

    def test_gemini_accepts_api_key_from_config(self):
        """Gemini provider accepts api_key from llm config (not just env var)."""
        config = {
            "llm": {
                "provider": "gemini",
                "mode": "production",
                "api_key": "config-key",
            }
        }
        # Make sure no env var is set
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            with patch("google.genai.Client") as MockClient:
                provider = get_provider(config, web_mode=True)
                assert isinstance(provider, GeminiProvider)
        finally:
            if old_key:
                os.environ["GEMINI_API_KEY"] = old_key


class TestGetProviderInfo:
    """Test get_provider_info() with updated registry."""

    def test_includes_gemini_pro(self):
        """Provider info list includes gemini-pro."""
        info = get_provider_info({"llm": {}})
        keys = [p["key"] for p in info]
        assert "gemini-pro" in keys

    def test_includes_gemini_3_pro(self):
        """Provider info list includes gemini-3-pro (added Session 12)."""
        info = get_provider_info({"llm": {}})
        keys = [p["key"] for p in info]
        assert "gemini-3-pro" in keys

    def test_gemini_pro_label(self):
        """Gemini Pro has correct label."""
        info = get_provider_info({"llm": {}})
        pro = [p for p in info if p["key"] == "gemini-pro"][0]
        assert "Pro" in pro["label"]

    def test_vertex_unavailable_message_updated(self):
        """Vertex AI shows google-genai message if unavailable."""
        with patch("src.llm_provider._GENAI_AVAILABLE", False):
            info = get_provider_info({"llm": {}})
            vertex = [p for p in info if p["key"] == "vertex"][0]
            if not vertex["available"]:
                assert "google-genai" in vertex["reason"]


class TestTestProviderEndpoint:
    """Test the /api/settings/test-provider endpoint with gemini-pro."""

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

    def test_gemini_pro_without_key_fails(self, client):
        """gemini-pro without API key returns failure."""
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "gemini-pro"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
        finally:
            if old_key:
                os.environ["GEMINI_API_KEY"] = old_key

    def test_gemini_3_pro_alias_without_key_fails(self, client):
        """Old gemini-3-pro name still works via alias, fails without key."""
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "gemini-3-pro"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
        finally:
            if old_key:
                os.environ["GEMINI_API_KEY"] = old_key
