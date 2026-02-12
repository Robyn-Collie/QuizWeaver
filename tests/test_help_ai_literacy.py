"""
Tests for BL-020: Help Page AI Literacy Section.

Verifies the 'Understanding AI in QuizWeaver' section exists
with all required content: generative AI explanation, human review,
glass box, deterministic layers, privacy, costs, and source links.
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


class TestAILiteracySection:
    """Test the Understanding AI in QuizWeaver section."""

    def test_section_exists(self, client):
        """The AI literacy section is present on the help page."""
        response = client.get("/help")
        html = response.data.decode()
        assert "understanding-ai" in html
        assert "Understanding AI in QuizWeaver" in html

    def test_toc_link_exists(self, client):
        """Table of contents includes link to AI literacy section."""
        response = client.get("/help")
        html = response.data.decode()
        assert 'href="#understanding-ai"' in html
        assert "Understanding AI" in html

    def test_generative_ai_explanation(self, client):
        """Section explains what generative AI is."""
        response = client.get("/help")
        html = response.data.decode()
        assert "What is generative AI" in html
        assert "patterns" in html.lower()

    def test_human_review_explanation(self, client):
        """Section explains why human review matters."""
        response = client.get("/help")
        html = response.data.decode()
        assert "human review" in html.lower()
        assert "draft" in html.lower()
        assert "hallucination" in html.lower()

    def test_glass_box_explanation(self, client):
        """Section explains the glass box principle."""
        response = client.get("/help")
        html = response.data.decode()
        assert "Glass Box" in html
        assert "transparent" in html.lower()

    def test_deterministic_layers_explanation(self, client):
        """Section explains deterministic layers."""
        response = client.get("/help")
        html = response.data.decode()
        assert "deterministic" in html.lower()
        assert "Bloom" in html
        assert "DOK" in html

    def test_privacy_explanation(self, client):
        """Section explains privacy protections."""
        response = client.get("/help")
        html = response.data.decode()
        assert "privacy" in html.lower()
        assert "local" in html.lower()
        assert "PII" in html or "personally identifiable" in html.lower()

    def test_cost_explanation(self, client):
        """Section explains AI costs and tokens."""
        response = client.get("/help")
        html = response.data.decode()
        assert "token" in html.lower()
        assert "Mock mode" in html or "mock mode" in html.lower()

    def test_accordion_markup(self, client):
        """Section uses accordion markup for readability."""
        response = client.get("/help")
        html = response.data.decode()
        assert "help-accordion" in html
        assert "help-accordion-toggle" in html
        assert "help-accordion-body" in html

    def test_empowering_tone(self, client):
        """Section uses empowering, non-intimidating language."""
        response = client.get("/help")
        html = response.data.decode()
        assert (
            "do not need to be a tech expert" in html.lower()
            or "don&#39;t need to be a tech expert" in html.lower()
            or "do not need to be a tech expert" in html
        )

    def test_source_links_present(self, client):
        """Section includes links to authoritative sources."""
        response = client.get("/help")
        html = response.data.decode()
        assert "unesco.org" in html.lower()
        assert "ed.gov" in html.lower()
        assert "iste.org" in html.lower()
        assert "digitalpromise.org" in html.lower()
        assert "sciencedirect.com" in html.lower()

    def test_source_links_open_in_new_tab(self, client):
        """Source links open in a new tab for safety."""
        response = client.get("/help")
        html = response.data.decode()
        # All source links should have target="_blank" and rel="noopener"
        assert 'target="_blank"' in html
        assert 'rel="noopener"' in html

    def test_six_accordion_items(self, client):
        """There are exactly six accordion items for the six AI topics."""
        response = client.get("/help")
        html = response.data.decode()
        count = html.count('data-accordion="ai-literacy"')
        assert count == 6

    def test_aria_expanded_attribute(self, client):
        """Accordion toggles have aria-expanded for accessibility."""
        response = client.get("/help")
        html = response.data.decode()
        assert "aria-expanded" in html
