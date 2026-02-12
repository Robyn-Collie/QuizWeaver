"""
Tests for Anthropic Claude provider support.

Verifies:
- AnthropicProvider uses the anthropic SDK
- VertexAnthropicProvider uses AnthropicVertex
- PROVIDER_REGISTRY has entries for both
- get_provider() returns correct classes
- get_provider_info() includes both providers
- Test-provider endpoint handles anthropic
"""

import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from src.llm_provider import (
    AnthropicProvider,
    VertexAnthropicProvider,
    MockLLMProvider,
    PROVIDER_REGISTRY,
    get_provider,
    get_provider_info,
    _ANTHROPIC_AVAILABLE,
)


class TestProviderRegistryEntries:
    """Verify registry entries for Anthropic providers."""

    def test_anthropic_in_registry(self):
        assert "anthropic" in PROVIDER_REGISTRY

    def test_anthropic_has_default_model(self):
        assert "default_model" in PROVIDER_REGISTRY["anthropic"]
        assert "claude" in PROVIDER_REGISTRY["anthropic"]["default_model"]

    def test_anthropic_has_env_var(self):
        assert PROVIDER_REGISTRY["anthropic"]["env_var"] == "ANTHROPIC_API_KEY"

    def test_vertex_anthropic_in_registry(self):
        assert "vertex-anthropic" in PROVIDER_REGISTRY

    def test_vertex_anthropic_has_default_model(self):
        assert "default_model" in PROVIDER_REGISTRY["vertex-anthropic"]
        assert "claude" in PROVIDER_REGISTRY["vertex-anthropic"]["default_model"]

    def test_vertex_anthropic_requires_config(self):
        meta = PROVIDER_REGISTRY["vertex-anthropic"]
        assert "requires_config" in meta
        assert "vertex_project_id" in meta["requires_config"]
        assert "vertex_location" in meta["requires_config"]


class TestAnthropicProviderInit:
    """Test AnthropicProvider initialization."""

    def test_creates_client_with_api_key(self):
        with patch("anthropic.Anthropic") as MockClient:
            provider = AnthropicProvider(api_key="test-key")
            MockClient.assert_called_once_with(api_key="test-key")

    def test_stores_model_name(self):
        with patch("anthropic.Anthropic"):
            provider = AnthropicProvider(api_key="test-key", model_name="claude-opus-4-20250514")
            assert provider._model_name == "claude-opus-4-20250514"

    def test_default_model(self):
        import inspect
        sig = inspect.signature(AnthropicProvider.__init__)
        default = sig.parameters["model_name"].default
        assert "claude" in default


class TestAnthropicProviderGenerate:
    """Test AnthropicProvider.generate() with mocked client."""

    def _make_provider(self):
        with patch("anthropic.Anthropic") as MockClient:
            mock_client = MockClient.return_value
            provider = AnthropicProvider(api_key="test-key")
            provider.client = mock_client
            return provider, mock_client

    def test_generate_calls_messages_create(self):
        provider, mock_client = self._make_provider()
        mock_content = MagicMock()
        mock_content.text = "Hello!"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = None
        mock_client.messages.create.return_value = mock_response

        result = provider.generate(["Hello"])
        mock_client.messages.create.assert_called_once()
        assert result == "Hello!"

    def test_generate_json_mode_adds_system_prompt(self):
        provider, mock_client = self._make_provider()
        mock_content = MagicMock()
        mock_content.text = '{"data": true}'
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = None
        mock_client.messages.create.return_value = mock_response

        provider.generate(["Hello"], json_mode=True)
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs.get("system") == "Respond only with valid JSON."

    def test_generate_no_json_mode_no_system(self):
        provider, mock_client = self._make_provider()
        mock_content = MagicMock()
        mock_content.text = "plain text"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = None
        mock_client.messages.create.return_value = mock_response

        provider.generate(["Hello"], json_mode=False)
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "system" not in call_kwargs

    def test_generate_error_returns_empty_json(self):
        provider, mock_client = self._make_provider()
        mock_client.messages.create.side_effect = Exception("API error")

        result = provider.generate(["Hi"])
        assert result == "[]"

    def test_generate_logs_cost(self):
        provider, mock_client = self._make_provider()
        mock_usage = MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50
        mock_content = MagicMock()
        mock_content.text = "response"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = mock_usage
        mock_client.messages.create.return_value = mock_response

        with patch("src.cost_tracking.log_api_call") as mock_log:
            provider.generate(["Hello"])
            mock_log.assert_called_once_with(
                "anthropic", provider._model_name, 100, 50
            )


class TestAnthropicProviderImage:
    """Test AnthropicProvider.prepare_image_context()."""

    def test_image_context_format(self, tmp_path):
        with patch("anthropic.Anthropic"):
            provider = AnthropicProvider(api_key="test-key")

        # Create a tiny PNG file
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

        result = provider.prepare_image_context(str(img_path))
        assert result["type"] == "image"
        assert result["source"]["type"] == "base64"
        assert result["source"]["media_type"] == "image/png"
        assert len(result["source"]["data"]) > 0


class TestVertexAnthropicProviderInit:
    """Test VertexAnthropicProvider initialization."""

    def test_creates_vertex_client(self):
        with patch("anthropic.AnthropicVertex") as MockVertex:
            provider = VertexAnthropicProvider(
                project_id="my-project", location="us-east5"
            )
            MockVertex.assert_called_once_with(
                project_id="my-project", region="us-east5"
            )

    def test_stores_model_name(self):
        with patch("anthropic.AnthropicVertex"):
            provider = VertexAnthropicProvider(
                project_id="proj", location="us-east5",
                model_name="claude-opus-4@20250514"
            )
            assert provider._model_name == "claude-opus-4@20250514"

    def test_generate_logs_vertex_anthropic(self):
        with patch("anthropic.AnthropicVertex"):
            provider = VertexAnthropicProvider(
                project_id="proj", location="us-east5"
            )
        mock_client = MagicMock()
        provider.client = mock_client
        mock_usage = MagicMock()
        mock_usage.input_tokens = 200
        mock_usage.output_tokens = 100
        mock_content = MagicMock()
        mock_content.text = "response"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = mock_usage
        mock_client.messages.create.return_value = mock_response

        with patch("src.cost_tracking.log_api_call") as mock_log:
            provider.generate(["Hello"])
            mock_log.assert_called_once_with(
                "vertex-anthropic", provider._model_name, 200, 100
            )


class TestGetProviderFactory:
    """Test get_provider() returns correct Anthropic classes."""

    def test_anthropic_returns_anthropic_provider(self):
        config = {"llm": {"provider": "anthropic", "mode": "production"}}
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic"):
                provider = get_provider(config, web_mode=True)
                assert isinstance(provider, AnthropicProvider)

    def test_anthropic_uses_registry_default_model(self):
        config = {"llm": {"provider": "anthropic", "mode": "production"}}
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic"):
                provider = get_provider(config, web_mode=True)
                assert provider._model_name == PROVIDER_REGISTRY["anthropic"]["default_model"]

    def test_anthropic_error_on_missing_key(self):
        config = {"llm": {"provider": "anthropic", "mode": "production"}}
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                get_provider(config, web_mode=True)
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key

    def test_vertex_anthropic_error_on_missing_config(self):
        config = {"llm": {"provider": "vertex-anthropic", "mode": "production"}}
        with pytest.raises(ValueError, match="Project ID"):
            get_provider(config, web_mode=True)


class TestGetProviderInfo:
    """Test get_provider_info() includes Anthropic providers."""

    def test_includes_anthropic(self):
        info = get_provider_info({"llm": {}})
        keys = [p["key"] for p in info]
        assert "anthropic" in keys

    def test_includes_vertex_anthropic(self):
        info = get_provider_info({"llm": {}})
        keys = [p["key"] for p in info]
        assert "vertex-anthropic" in keys

    def test_anthropic_unavailable_without_key(self):
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            info = get_provider_info({"llm": {}})
            anthropic = [p for p in info if p["key"] == "anthropic"][0]
            assert anthropic["available"] is False
            assert "ANTHROPIC_API_KEY" in anthropic["reason"]
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key

    def test_vertex_anthropic_unavailable_without_config(self):
        info = get_provider_info({"llm": {}})
        va = [p for p in info if p["key"] == "vertex-anthropic"][0]
        if _ANTHROPIC_AVAILABLE:
            assert va["available"] is False
            assert "Missing config" in va["reason"]


class TestTestProviderEndpoint:
    """Test the /api/settings/test-provider endpoint with anthropic."""

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

    def test_anthropic_without_key_fails(self, client):
        """anthropic without API key returns failure."""
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            response = client.post(
                "/api/settings/test-provider",
                data=json.dumps({"provider": "anthropic"}),
                content_type="application/json",
            )
            data = response.get_json()
            assert data["success"] is False
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key

    def test_vertex_anthropic_without_config_fails(self, client):
        """vertex-anthropic without project config returns failure."""
        response = client.post(
            "/api/settings/test-provider",
            data=json.dumps({"provider": "vertex-anthropic"}),
            content_type="application/json",
        )
        data = response.get_json()
        assert data["success"] is False
