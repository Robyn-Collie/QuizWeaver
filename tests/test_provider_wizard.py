"""
Tests for BL-018: Provider Setup Wizard.

Verifies the wizard route exists, renders properly, and contains
all required steps: provider selection, instructions, connect/test, and success.
"""

import os
import tempfile

import pytest

from src.database import Base, get_engine, get_session

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


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


class TestWizardRoute:
    """Test the wizard route exists and renders."""

    def test_wizard_returns_200(self, client):
        """Wizard page loads successfully."""
        response = client.get("/settings/wizard")
        assert response.status_code == 200

    def test_wizard_requires_login(self, app):
        """Wizard requires authentication."""
        c = app.test_client()
        response = c.get("/settings/wizard")
        assert response.status_code in (302, 303)

    def test_wizard_title(self, client):
        """Wizard page has correct title."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "Provider Setup Wizard" in html


class TestWizardStep1:
    """Test Step 1: Provider selection."""

    def test_has_provider_cards(self, client):
        """Step 1 shows provider selection cards."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "wizard-provider-card" in html

    def test_has_gemini_option(self, client):
        """Step 1 includes Google Gemini option."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "Google Gemini" in html
        assert 'value="gemini"' in html

    def test_has_openai_option(self, client):
        """Step 1 includes OpenAI option."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "OpenAI" in html
        assert 'value="openai"' in html

    def test_has_local_option(self, client):
        """Step 1 includes local model (Ollama) option."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "Ollama" in html
        assert 'value="openai-compatible"' in html

    def test_explains_api_key(self, client):
        """Step 1 explains what an API key is."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "API key" in html
        assert "stored" in html.lower()


class TestWizardStep2:
    """Test Step 2: Provider-specific instructions."""

    def test_has_gemini_instructions(self, client):
        """Wizard has Gemini setup instructions."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "instructions-gemini" in html
        assert "aistudio.google.com" in html

    def test_has_openai_instructions(self, client):
        """Wizard has OpenAI setup instructions."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "instructions-openai" in html
        assert "platform.openai.com" in html

    def test_has_ollama_instructions(self, client):
        """Wizard has Ollama setup instructions."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "instructions-openai-compatible" in html
        assert "ollama.com" in html

    def test_includes_cost_info(self, client):
        """Instructions include cost information."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "cost" in html.lower()
        assert "/costs" in html


class TestWizardStep3:
    """Test Step 3: Connect and test."""

    def test_has_api_key_input(self, client):
        """Step 3 has API key input field."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "wizard_api_key" in html

    def test_has_test_button(self, client):
        """Step 3 has test connection button."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "wizard-test-btn" in html
        assert "Test Connection" in html

    def test_uses_existing_test_endpoint(self, client):
        """Step 3 JS uses the existing test-provider API endpoint."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "/api/settings/test-provider" in html

    def test_has_save_button(self, client):
        """Step 3 has save button (initially disabled)."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "wizard-save-btn" in html


class TestWizardStep4:
    """Test Step 4: Success screen."""

    def test_has_success_message(self, client):
        """Step 4 has success message."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "Provider Connected" in html

    def test_has_dashboard_link(self, client):
        """Step 4 links to dashboard."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "/dashboard" in html
        assert "Go to Dashboard" in html

    def test_has_review_reminder(self, client):
        """Step 4 reminds teachers to review AI output."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "draft" in html.lower()
        assert "review" in html.lower()


class TestWizardProgressBar:
    """Test the wizard progress indicators."""

    def test_has_four_steps(self, client):
        """Progress bar has 4 step indicators."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert html.count("wizard-step-indicator") >= 4

    def test_step_labels(self, client):
        """Progress bar has descriptive step labels."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "Choose Provider" in html
        assert "Get API Key" in html
        assert "Connect" in html
        assert "Done" in html


class TestWizardAILiteracy:
    """Test AI literacy content in the wizard."""

    def test_privacy_info_for_local(self, client):
        """Wizard explains privacy advantage of local models."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "private" in html.lower() or "privacy" in html.lower()

    def test_links_to_help(self, client):
        """Wizard links to the AI literacy help section."""
        response = client.get("/settings/wizard")
        html = response.data.decode()
        assert "/help" in html


class TestDashboardWizardLink:
    """Test that the dashboard links to the wizard."""

    def test_dashboard_has_wizard_link(self, client):
        """Dashboard getting-started banner links to wizard."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert "/settings/wizard" in html
