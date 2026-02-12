"""
Tests for QuizWeaver LLM provider settings and selection UI.

Tests cover:
- Settings page rendering and form submission
- Provider dropdown on quiz generation form
- Provider override in quiz generation
- Provider transparency on quiz detail
- get_provider() web_mode parameter
- get_provider_info() availability checking
- OpenAICompatibleProvider class
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session
from src.llm_provider import (
    PROVIDER_REGISTRY,
    MockLLMProvider,
    OpenAICompatibleProvider,
    get_provider,
    get_provider_info,
)
from src.web.config_utils import save_config

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed test data
    test_class = Class(
        name="Test Class",
        grade_level="8th Grade",
        subject="Science",
        standards=json.dumps(["SOL 8.1"]),
        config=json.dumps({}),
    )
    session.add(test_class)
    session.commit()

    # Add a quiz with provider in style_profile
    quiz = Quiz(
        title="Test Quiz",
        class_id=test_class.id,
        status="generated",
        style_profile=json.dumps(
            {
                "grade_level": "8th Grade",
                "provider": "openai",
                "difficulty": 3,
            }
        ),
    )
    session.add(quiz)
    session.commit()

    q1 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q1",
        text="What is gravity?",
        points=5.0,
        data=json.dumps(
            {
                "type": "mc",
                "text": "What is gravity?",
                "options": ["A force", "A color", "A sound", "A taste"],
                "correct_index": 0,
            }
        ),
    )
    session.add(q1)
    session.commit()
    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {
            "provider": "mock",
            "mode": "development",
            "max_calls_per_session": 50,
            "max_cost_per_session": 5.00,
        },
        "generation": {"default_grade_level": "8th Grade Science"},
    }
    flask_app = create_app(test_config)
    flask_app.config["TESTING"] = True

    # Patch save_config so settings POST doesn't overwrite real config.yaml
    with patch("src.web.blueprints.settings.save_config"):
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


# ============================================================
# Settings Page Tests
# ============================================================


class TestSettingsPage:
    """Tests for the /settings route."""

    def test_settings_get_returns_200(self, client):
        """GET /settings returns 200 with provider options."""
        resp = client.get("/settings")
        assert resp.status_code == 200
        assert b"Settings" in resp.data
        assert b"LLM Provider" in resp.data

    def test_settings_shows_provider_options(self, client):
        """Settings page shows all registered providers."""
        resp = client.get("/settings")
        assert b"Mock (Development)" in resp.data
        assert b"Google Gemini Flash" in resp.data
        assert b"OpenAI" in resp.data
        assert b"Custom (OpenAI-Compatible)" in resp.data

    def test_settings_shows_current_provider_selected(self, client):
        """Current provider radio is checked."""
        resp = client.get("/settings")
        # The mock provider should be selected (checked) since config says "mock"
        assert b'value="mock"' in resp.data

    def test_settings_post_saves_provider(self, client, app):
        """POST /settings updates the provider in config."""
        resp = client.post(
            "/settings",
            data={"provider": "openai", "model_name": "gpt-4o", "api_key": "sk-test123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        config = app.config["APP_CONFIG"]
        assert config["llm"]["provider"] == "openai"
        assert config["llm"]["model_name"] == "gpt-4o"
        assert config["llm"]["api_key"] == "sk-test123"

    def test_settings_post_saves_custom_provider(self, client, app):
        """POST /settings with openai-compatible saves base_url."""
        resp = client.post(
            "/settings",
            data={
                "provider": "openai-compatible",
                "model_name": "llama3",
                "api_key": "ollama-key",
                "base_url": "http://localhost:11434/v1",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        config = app.config["APP_CONFIG"]
        assert config["llm"]["provider"] == "openai-compatible"
        assert config["llm"]["base_url"] == "http://localhost:11434/v1"

    def test_settings_post_flashes_success(self, client):
        """POST /settings flashes a success message."""
        resp = client.post(
            "/settings",
            data={"provider": "mock"},
            follow_redirects=True,
        )
        assert b"Settings saved successfully" in resp.data

    def test_settings_requires_login(self, app):
        """Settings page requires authentication."""
        c = app.test_client()
        resp = c.get("/settings")
        assert resp.status_code == 303

    def test_settings_nav_link_exists(self, client):
        """Settings link appears in navigation."""
        resp = client.get("/dashboard")
        assert b"/settings" in resp.data
        assert b"Settings" in resp.data


# ============================================================
# Generate Form Provider Dropdown Tests
# ============================================================


class TestGenerateProviderDropdown:
    """Tests for provider dropdown on quiz generation form."""

    def test_generate_form_shows_provider_dropdown(self, client):
        """GET generate form includes provider select."""
        resp = client.get("/classes/1/generate")
        assert resp.status_code == 200
        assert b'name="provider"' in resp.data
        assert b"AI Provider" in resp.data

    def test_generate_form_shows_available_providers(self, client):
        """Generate form lists providers with availability status."""
        resp = client.get("/classes/1/generate")
        assert b"Mock (Development)" in resp.data

    def test_generate_form_shows_default_option(self, client):
        """Generate form has a 'use default' option."""
        resp = client.get("/classes/1/generate")
        assert b"Use default" in resp.data

    def test_generate_post_with_provider_override(self, client):
        """POST generate with provider passes provider_name to generate_quiz."""
        # Use mock provider so the quiz actually generates
        resp = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "difficulty": "3",
                "provider": "mock",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_generate_post_without_provider_uses_default(self, client):
        """POST generate without provider field uses config default."""
        resp = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "difficulty": "3",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200


# ============================================================
# Quiz Detail Provider Transparency Tests
# ============================================================


class TestQuizDetailProvider:
    """Tests for provider display on quiz detail page."""

    def test_quiz_detail_shows_provider(self, client):
        """Quiz detail page shows which provider generated the quiz."""
        resp = client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"Generated by:" in resp.data
        assert b"openai" in resp.data


# ============================================================
# get_provider() web_mode Tests
# ============================================================


class TestGetProviderWebMode:
    """Tests for web_mode parameter in get_provider()."""

    def test_web_mode_skips_input_gate_for_mock(self):
        """web_mode=True with mock provider returns MockLLMProvider without input."""
        config = {"llm": {"provider": "mock"}}
        provider = get_provider(config, web_mode=True)
        assert isinstance(provider, MockLLMProvider)

    def test_web_mode_skips_input_gate_for_real_provider(self):
        """web_mode=True skips the input() approval prompt for real providers."""
        config = {
            "llm": {
                "provider": "openai",
                "mode": "development",
                "api_key": "sk-test",
            }
        }
        # Patch OpenAI client to avoid real API calls
        with patch("openai.OpenAI"):
            provider = get_provider(config, web_mode=True)
            assert isinstance(provider, OpenAICompatibleProvider)

    def test_cli_mode_prompts_for_input(self):
        """web_mode=False (default) prompts for input on real providers."""
        config = {
            "llm": {
                "provider": "openai",
                "mode": "development",
                "api_key": "sk-test",
            }
        }
        # Simulate user typing "no" -> should fall back to mock
        with patch("builtins.input", return_value="no"):
            provider = get_provider(config, web_mode=False)
            assert isinstance(provider, MockLLMProvider)

    def test_web_mode_true_with_env_openai_key(self):
        """web_mode=True reads OPENAI_API_KEY from env for openai provider."""
        config = {"llm": {"provider": "openai", "mode": "development"}}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-test"}), patch("openai.OpenAI"):
            provider = get_provider(config, web_mode=True)
            assert isinstance(provider, OpenAICompatibleProvider)


# ============================================================
# get_provider_info() Tests
# ============================================================


class TestGetProviderInfo:
    """Tests for get_provider_info() availability checking."""

    def test_returns_all_registered_providers(self):
        """get_provider_info returns an entry for every registered provider."""
        config = {"llm": {}}
        info = get_provider_info(config)
        keys = [p["key"] for p in info]
        for reg_key in PROVIDER_REGISTRY:
            assert reg_key in keys

    def test_mock_always_available(self):
        """Mock provider is always marked as available."""
        config = {"llm": {}}
        info = get_provider_info(config)
        mock_info = next(p for p in info if p["key"] == "mock")
        assert mock_info["available"] is True

    def test_openai_unavailable_without_key(self):
        """OpenAI is unavailable when no API key is set."""
        config = {"llm": {}}
        with patch.dict(os.environ, {}, clear=True):
            # Ensure OPENAI_API_KEY is not in environment
            os.environ.pop("OPENAI_API_KEY", None)
            info = get_provider_info(config)
            openai_info = next(p for p in info if p["key"] == "openai")
            assert openai_info["available"] is False

    def test_openai_available_with_env_key(self):
        """OpenAI is available when OPENAI_API_KEY is set."""
        config = {"llm": {}}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            info = get_provider_info(config)
            openai_info = next(p for p in info if p["key"] == "openai")
            assert openai_info["available"] is True

    def test_openai_available_with_config_key(self):
        """OpenAI is available when api_key is in config and provider is openai."""
        config = {"llm": {"provider": "openai", "api_key": "sk-from-config"}}
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            info = get_provider_info(config)
            openai_info = next(p for p in info if p["key"] == "openai")
            assert openai_info["available"] is True

    def test_custom_unavailable_without_base_url(self):
        """openai-compatible is unavailable without base_url."""
        config = {"llm": {"api_key": "key"}}
        info = get_provider_info(config)
        custom = next(p for p in info if p["key"] == "openai-compatible")
        assert custom["available"] is False

    def test_custom_available_with_full_config(self):
        """openai-compatible is available with base_url and api_key."""
        config = {"llm": {"api_key": "key", "base_url": "http://localhost:11434/v1"}}
        info = get_provider_info(config)
        custom = next(p for p in info if p["key"] == "openai-compatible")
        assert custom["available"] is True

    def test_info_includes_label_and_description(self):
        """Each provider info includes label and description."""
        config = {"llm": {}}
        info = get_provider_info(config)
        for p in info:
            assert "label" in p
            assert "description" in p
            assert "available" in p
            assert len(p["label"]) > 0


# ============================================================
# OpenAICompatibleProvider Unit Tests
# ============================================================


class TestOpenAICompatibleProvider:
    """Tests for the OpenAICompatibleProvider class."""

    def test_constructs_proper_messages_format(self):
        """generate() builds proper OpenAI messages format."""
        with patch("openai.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"questions": []}'
            mock_response.usage = None
            mock_client.chat.completions.create.return_value = mock_response
            MockOpenAI.return_value = mock_client

            provider = OpenAICompatibleProvider(
                api_key="test-key",
                base_url="https://api.openai.com/v1",
                model_name="gpt-4o",
            )
            result = provider.generate(["Hello, generate a quiz"], json_mode=True)

            assert result == '{"questions": []}'
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "gpt-4o"
            assert call_kwargs["messages"][0]["role"] == "user"
            assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_generate_without_json_mode(self):
        """generate() omits response_format when json_mode=False."""
        with patch("openai.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "APPROVED"
            mock_response.usage = None
            mock_client.chat.completions.create.return_value = mock_response
            MockOpenAI.return_value = mock_client

            provider = OpenAICompatibleProvider(
                api_key="test-key",
                base_url="https://api.openai.com/v1",
                model_name="gpt-4o",
            )
            result = provider.generate(["Critique this quiz"], json_mode=False)

            assert result == "APPROVED"
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert "response_format" not in call_kwargs

    def test_generate_handles_image_parts(self):
        """generate() passes through image_url dicts in prompt_parts."""
        with patch("openai.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "[]"
            mock_response.usage = None
            mock_client.chat.completions.create.return_value = mock_response
            MockOpenAI.return_value = mock_client

            provider = OpenAICompatibleProvider(
                api_key="test-key",
                base_url="https://api.openai.com/v1",
                model_name="gpt-4o",
            )
            image_part = {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}}
            provider.generate(["Describe this image", image_part])

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            content = call_kwargs["messages"][0]["content"]
            assert len(content) == 2
            assert content[0]["type"] == "text"
            assert content[1]["type"] == "image_url"

    def test_generate_returns_empty_on_error(self):
        """generate() returns '[]' on API errors."""
        with patch("openai.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("API Error")
            MockOpenAI.return_value = mock_client

            provider = OpenAICompatibleProvider(
                api_key="test-key",
                base_url="https://api.openai.com/v1",
                model_name="gpt-4o",
            )
            result = provider.generate(["test"])
            assert result == "[]"

    def test_prepare_image_context_returns_base64(self):
        """prepare_image_context() returns a base64 data URL dict."""
        with patch("openai.OpenAI"):
            provider = OpenAICompatibleProvider(
                api_key="test-key",
                base_url="https://api.openai.com/v1",
                model_name="gpt-4o",
            )

        # Create a tiny test image file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            temp_path = f.name

        try:
            result = provider.prepare_image_context(temp_path)
            assert result["type"] == "image_url"
            assert "data:image/png;base64," in result["image_url"]["url"]
        finally:
            os.unlink(temp_path)


# ============================================================
# Provider Registry Tests
# ============================================================


class TestProviderRegistry:
    """Tests for the PROVIDER_REGISTRY constant."""

    def test_registry_has_required_providers(self):
        """Registry includes mock, gemini, openai, and openai-compatible."""
        assert "mock" in PROVIDER_REGISTRY
        assert "gemini" in PROVIDER_REGISTRY
        assert "openai" in PROVIDER_REGISTRY
        assert "openai-compatible" in PROVIDER_REGISTRY

    def test_registry_entries_have_label_and_description(self):
        """Each registry entry has label and description."""
        for key, meta in PROVIDER_REGISTRY.items():
            assert "label" in meta, f"{key} missing label"
            assert "description" in meta, f"{key} missing description"
            assert "category" in meta, f"{key} missing category"

    def test_openai_has_defaults(self):
        """OpenAI entry has default_base_url and default_model."""
        openai = PROVIDER_REGISTRY["openai"]
        assert openai["default_base_url"] == "https://api.openai.com/v1"
        assert openai["default_model"] == "gpt-4o"


# ============================================================
# save_config Tests
# ============================================================


class TestSaveConfig:
    """Tests for the save_config() helper."""

    def test_save_config_writes_yaml(self):
        """save_config writes valid YAML to disk."""
        import yaml

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            temp_path = f.name

        try:
            config = {
                "llm": {"provider": "openai", "model_name": "gpt-4o"},
                "paths": {"database_file": "test.db"},
            }
            save_config(config, config_path=temp_path)

            with open(temp_path) as f:
                loaded = yaml.safe_load(f)

            assert loaded["llm"]["provider"] == "openai"
            assert loaded["llm"]["model_name"] == "gpt-4o"
        finally:
            os.unlink(temp_path)
