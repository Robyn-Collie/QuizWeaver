"""
Tests for BL-027: Responsive Navigation.
Verifies grouped nav structure, dropdown classes, and proper links.
"""
import os
import tempfile
import json

import pytest
from src.database import Base, Class, get_engine, get_session


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)
    cls = Class(
        name="Test Class",
        grade_level="7th Grade",
        subject="Math",
        standards=json.dumps([]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()
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
    c = app.test_client()
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


class TestNavDropdownStructure:
    """Nav uses grouped dropdown menus."""

    def test_nav_has_dropdown_class(self, client):
        """Navigation contains nav-dropdown elements."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert "nav-dropdown" in html

    def test_nav_has_dropdown_toggle(self, client):
        """Navigation contains dropdown toggle links."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert "nav-dropdown-toggle" in html

    def test_nav_has_dropdown_menu(self, client):
        """Navigation contains dropdown menu lists."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert "nav-dropdown-menu" in html

    def test_generate_dropdown_exists(self, client):
        """A 'Generate' dropdown group exists in the nav."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert "Generate" in html

    def test_tools_dropdown_exists(self, client):
        """A 'Tools' dropdown group exists in the nav."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert "Tools" in html

    def test_dropdown_arrow_present(self, client):
        """Dropdown toggles have arrow indicators."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert "dropdown-arrow" in html


class TestNavLinksPresent:
    """All navigation links are still accessible."""

    def test_dashboard_link(self, client):
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/dashboard"' in html

    def test_classes_link(self, client):
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/classes"' in html

    def test_quizzes_link(self, client):
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/quizzes"' in html

    def test_question_bank_link(self, client):
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/question-bank"' in html

    def test_study_link(self, client):
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/study"' in html

    def test_costs_link(self, client):
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/costs"' in html

    def test_settings_link(self, client):
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/settings"' in html

    def test_help_link(self, client):
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/help"' in html

    def test_generate_quiz_link(self, client):
        """Quiz generation link is in the Generate dropdown."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/generate"' in html

    def test_study_generate_link(self, client):
        """Study materials generation link is in the Generate dropdown."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/study/generate"' in html

    def test_topics_generation_link(self, client):
        """Topic-based generation link is in the Generate dropdown."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/generate/topics"' in html

    def test_standards_link(self, client):
        """Standards link is in the Tools dropdown."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/standards"' in html

    def test_analytics_link(self, client):
        """Analytics link is in the Tools dropdown."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/analytics"' in html


class TestNavUserSection:
    """User info is in a separate section from main nav."""

    def test_user_section_exists(self, client):
        """Nav has a separate user section."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert "nav-user-section" in html

    def test_logout_link_present(self, client):
        """Logout link is present."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        assert 'href="/logout"' in html

    def test_logout_outside_nav_links(self, client):
        """Logout is in the user section, not in the main nav-links."""
        resp = client.get("/dashboard?skip_onboarding=1")
        html = resp.data.decode()
        # The logout link should appear after nav-user-section
        user_section_idx = html.find("nav-user-section")
        logout_idx = html.find('href="/logout"')
        assert user_section_idx != -1
        assert logout_idx != -1
        assert logout_idx > user_section_idx
