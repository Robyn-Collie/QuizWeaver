"""
Tests for Session 7 dashboard redesign.

Verifies the new dashboard layout: classes at top, tool cards,
recent activity feed, and removal of old stat cards + chart.
"""

import json
import os
import tempfile
from datetime import date

import pytest

from src.database import Base, Class, LessonLog, Quiz, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed test data: 2 classes
    cls1 = Class(
        name="Algebra Block 1",
        grade_level="8th Grade",
        subject="Math",
        standards=json.dumps(["SOL 8.1"]),
        config=json.dumps({}),
    )
    cls2 = Class(
        name="Algebra Block 2",
        grade_level="8th Grade",
        subject="Math",
        standards=json.dumps([]),
        config=json.dumps({}),
    )
    session.add(cls1)
    session.add(cls2)
    session.commit()

    # Add lessons
    lesson1 = LessonLog(
        class_id=cls1.id,
        date=date(2026, 2, 3),
        content="Introduction to linear equations and slope.",
        topics=json.dumps(["linear equations", "slope"]),
        notes=None,
    )
    lesson2 = LessonLog(
        class_id=cls1.id,
        date=date(2026, 2, 5),
        content="Graphing linear functions on coordinate plane.",
        topics=json.dumps(["graphing", "functions"]),
        notes=None,
    )
    session.add(lesson1)
    session.add(lesson2)
    session.commit()

    # Add a quiz
    quiz = Quiz(
        title="Linear Equations Quiz",
        class_id=cls1.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "8th Grade"}),
    )
    session.add(quiz)
    session.commit()

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "8th Grade"},
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
def client(app):
    """Create a logged-in test client."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
    return c


class TestDashboardLayout:
    """Test the new dashboard layout."""

    def test_dashboard_returns_200(self, client):
        """Dashboard loads successfully."""
        response = client.get("/dashboard")
        assert response.status_code == 200

    def test_classes_section_at_top(self, client):
        """Classes section appears on dashboard with class names."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "Your Classes" in html
        assert "Algebra Block 1" in html
        assert "Algebra Block 2" in html

    def test_new_class_button_present(self, client):
        """New Class button appears in the classes section header."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "New Class" in html
        assert "/classes/new" in html

    def test_tool_cards_present(self, client):
        """Tool cards for key workflows are shown."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "Generate Quiz" in html
        assert "Study Materials" in html
        assert "Analytics" in html
        assert "Log a Lesson" in html
        assert "Settings" in html
        assert "Variants" in html

    def test_tool_card_links_correct(self, client):
        """Tool cards link to correct pages."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "/generate" in html
        assert "/study/generate" in html
        assert "/quizzes" in html
        assert "/analytics" in html
        assert "/lessons/new" in html
        assert "/settings" in html

    def test_no_provider_stat_card(self, client):
        """Old provider stat card is no longer shown."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "LLM Provider" not in html
        # The stats-grid with stat-card elements should be gone
        assert "stat-card" not in html

    def test_no_quizzes_generated_stat(self, client):
        """Old 'Quizzes Generated' stat card is gone."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "Quizzes Generated" not in html

    def test_no_chart_canvas(self, client):
        """Old Chart.js canvas and CDN script are removed from dashboard."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "lessonsChart" not in html
        assert "cdn.jsdelivr.net/npm/chart.js" not in html

    def test_recent_lessons_shown(self, client):
        """Recent lessons appear in activity feed."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "Recent Activity" in html
        assert "Algebra Block 1" in html

    def test_recent_quizzes_shown(self, client):
        """Recent quizzes appear in activity feed."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "Linear Equations Quiz" in html

    def test_getting_started_banner_present(self, client):
        """Getting started banner is still present."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "Welcome to QuizWeaver" in html
        assert "gettingStarted" in html


class TestDashboardEmptyState:
    """Test dashboard when no classes exist."""

    @pytest.fixture
    def empty_app(self):
        """Create a Flask test app with no classes."""
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

        flask_app.config["WTF_CSRF_ENABLED"] = False

        yield flask_app

        flask_app.config["DB_ENGINE"].dispose()
        os.close(db_fd)
        try:
            os.unlink(db_path)
        except PermissionError:
            pass

    @pytest.fixture
    def empty_client(self, empty_app):
        """Create a logged-in client for the empty app."""
        c = empty_app.test_client()
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        return c

    def test_empty_state_redirects_to_onboarding(self, empty_client):
        """Redirects to onboarding when no classes exist."""
        response = empty_client.get("/dashboard")
        assert response.status_code == 302
        assert "/onboarding" in response.headers["Location"]

    def test_empty_state_no_tool_cards(self, empty_client):
        """Tool cards are hidden when no classes exist."""
        response = empty_client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert "tool-card" not in html

    def test_empty_state_create_prompt(self, empty_client):
        """Shows prompt to create first class when none exist."""
        response = empty_client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert "Create your first class" in html

    def test_empty_state_no_activity(self, empty_client):
        """No activity feed when no data exists."""
        response = empty_client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert "Recent Activity" not in html
