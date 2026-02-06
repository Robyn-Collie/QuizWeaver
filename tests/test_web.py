"""
Tests for QuizWeaver web frontend.

TDD: These tests are written BEFORE the implementation.
They define the expected behavior of the Flask web UI.
"""

import os
import json
import tempfile
import pytest
from datetime import date, datetime, timedelta

# Import database models for test setup
from src.database import Base, Class, LessonLog, Quiz, Question, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database."""
    # Create a temp database file
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    # Set up the database
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed test data
    legacy_class = Class(
        name="Legacy Class",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({"assumed_knowledge": {
            "photosynthesis": {"depth": 3, "last_taught": "2026-02-01", "mention_count": 3},
            "cell division": {"depth": 1, "last_taught": "2026-02-05", "mention_count": 1},
        }}),
    )
    block_a = Class(
        name="7th Grade Science - Block A",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1", "SOL 7.2"]),
        config=json.dumps({}),
    )
    session.add(legacy_class)
    session.add(block_a)
    session.commit()

    # Add lesson logs for the legacy class across multiple days
    lesson1 = LessonLog(
        class_id=legacy_class.id,
        date=date(2026, 2, 1),
        content="Today we covered photosynthesis and how plants convert sunlight to energy.",
        topics=json.dumps(["photosynthesis"]),
        notes="Students engaged well",
    )
    lesson2 = LessonLog(
        class_id=legacy_class.id,
        date=date(2026, 2, 5),
        content="Introduction to cell division and mitosis.",
        topics=json.dumps(["cell division", "mitosis"]),
        notes=None,
    )
    session.add(lesson1)
    session.add(lesson2)
    session.commit()

    # Add a quiz
    quiz = Quiz(
        title="Change Over Time Retake",
        class_id=legacy_class.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "7th Grade"}),
    )
    session.add(quiz)
    session.commit()

    # Add questions to the quiz
    q1 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q1",
        text="What is the process by which plants make food?",
        points=5.0,
        data=json.dumps({
            "type": "mc",
            "text": "What is the process by which plants make food?",
            "options": ["Photosynthesis", "Respiration", "Fermentation", "Digestion"],
            "correct_index": 0,
        }),
    )
    session.add(q1)
    session.commit()

    session.close()
    engine.dispose()

    # Create the Flask app
    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock", "max_calls_per_session": 50, "max_cost_per_session": 5.00},
        "generation": {"default_grade_level": "7th Grade Science"},
    }
    flask_app = create_app(test_config)
    flask_app.config["TESTING"] = True

    yield flask_app

    # Cleanup: dispose engine before removing file (Windows file locking)
    flask_app.config["DB_ENGINE"].dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def client(app):
    """Create a logged-in test client (most tests need auth)."""
    c = app.test_client()
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


@pytest.fixture
def anon_client(app):
    """Create an unauthenticated test client for auth tests."""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Alias for logged-in client (used by auth tests)."""
    c = app.test_client()
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


# ============================================================
# Task 1: Flask App Setup Tests
# ============================================================


class TestAppSetup:
    """Test that the Flask app is properly configured."""

    def test_app_exists(self, app):
        """App factory creates a Flask app."""
        assert app is not None

    def test_app_is_testing(self, app):
        """App is in testing mode."""
        assert app.config["TESTING"] is True

    def test_index_redirects_to_dashboard(self, client):
        """Root URL redirects to dashboard."""
        response = client.get("/")
        assert response.status_code in (302, 308)
        assert "/dashboard" in response.headers["Location"]

    def test_dashboard_returns_200(self, client):
        """Dashboard page loads successfully."""
        response = client.get("/dashboard")
        assert response.status_code == 200

    def test_404_for_unknown_route(self, client):
        """Unknown routes return 404."""
        response = client.get("/nonexistent-page")
        assert response.status_code == 404


# ============================================================
# Task 2: Dashboard Tests
# ============================================================


class TestDashboard:
    """Test dashboard page content and behavior."""

    def test_dashboard_shows_app_name(self, client):
        """Dashboard contains the app name."""
        response = client.get("/dashboard")
        assert b"QuizWeaver" in response.data

    def test_dashboard_shows_class_count(self, client):
        """Dashboard shows how many classes exist."""
        response = client.get("/dashboard")
        html = response.data.decode()
        # Should show 2 classes (Legacy + Block A)
        assert "2" in html

    def test_dashboard_shows_class_names(self, client):
        """Dashboard lists class names."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "Legacy Class" in html
        assert "7th Grade Science - Block A" in html

    def test_dashboard_shows_lesson_count(self, client):
        """Dashboard shows total lesson count."""
        response = client.get("/dashboard")
        html = response.data.decode()
        # We seeded 2 lessons
        assert "2" in html

    def test_dashboard_shows_quiz_count(self, client):
        """Dashboard shows total quiz count."""
        response = client.get("/dashboard")
        html = response.data.decode()
        # We seeded 1 quiz
        assert "1" in html

    def test_dashboard_shows_provider_status(self, client):
        """Dashboard shows current LLM provider (mock)."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "mock" in html.lower()


# ============================================================
# Task 3: Classes Management Tests
# ============================================================


class TestClasses:
    """Test class listing, creation, and detail pages."""

    def test_classes_list_returns_200(self, client):
        """Classes list page loads successfully."""
        response = client.get("/classes")
        assert response.status_code == 200

    def test_classes_list_shows_all_classes(self, client):
        """Classes list shows all seeded classes."""
        response = client.get("/classes")
        html = response.data.decode()
        assert "Legacy Class" in html
        assert "7th Grade Science - Block A" in html

    def test_classes_list_shows_grade_level(self, client):
        """Classes list shows grade levels."""
        response = client.get("/classes")
        html = response.data.decode()
        assert "7th Grade" in html

    def test_classes_list_shows_lesson_count(self, client):
        """Classes list shows lesson count per class."""
        response = client.get("/classes")
        html = response.data.decode()
        # Legacy class has 2 lessons
        assert "2" in html

    def test_class_detail_returns_200(self, client):
        """Class detail page loads for a valid class."""
        response = client.get("/classes/1")
        assert response.status_code == 200

    def test_class_detail_shows_name(self, client):
        """Class detail shows the class name."""
        response = client.get("/classes/1")
        html = response.data.decode()
        assert "Legacy Class" in html

    def test_class_detail_shows_knowledge(self, client):
        """Class detail shows assumed knowledge topics."""
        response = client.get("/classes/1")
        html = response.data.decode()
        assert "photosynthesis" in html

    def test_class_detail_404_for_invalid_id(self, client):
        """Class detail returns 404 for nonexistent class."""
        response = client.get("/classes/999")
        assert response.status_code == 404

    def test_class_create_form_returns_200(self, client):
        """Class creation form page loads."""
        response = client.get("/classes/new")
        assert response.status_code == 200

    def test_class_create_form_has_fields(self, client):
        """Class creation form has required fields."""
        response = client.get("/classes/new")
        html = response.data.decode()
        assert 'name="name"' in html
        assert 'name="grade_level"' in html
        assert 'name="subject"' in html

    def test_class_create_post_creates_class(self, client):
        """POST to /classes/new creates a new class."""
        response = client.post("/classes/new", data={
            "name": "8th Grade Biology - Block B",
            "grade_level": "8th Grade",
            "subject": "Biology",
            "standards": "SOL 8.1, SOL 8.2",
        }, follow_redirects=False)
        # Should redirect to classes list or detail
        assert response.status_code in (302, 303)

        # Verify class was created
        response = client.get("/classes")
        html = response.data.decode()
        assert "8th Grade Biology - Block B" in html

    def test_class_create_post_requires_name(self, client):
        """POST to /classes/new without name shows error."""
        response = client.post("/classes/new", data={
            "name": "",
            "grade_level": "8th Grade",
        })
        # Should stay on form or show error
        assert response.status_code in (200, 400)
        html = response.data.decode()
        assert "required" in html.lower() or "name" in html.lower()


# ============================================================
# Task 4: Lesson Tracking Tests
# ============================================================


class TestLessons:
    """Test lesson listing and logging pages."""

    def test_lessons_list_returns_200(self, client):
        """Lessons list page for a class loads."""
        response = client.get("/classes/1/lessons")
        assert response.status_code == 200

    def test_lessons_list_shows_lessons(self, client):
        """Lessons list shows seeded lessons."""
        response = client.get("/classes/1/lessons")
        html = response.data.decode()
        assert "photosynthesis" in html

    def test_lessons_list_shows_dates(self, client):
        """Lessons list shows lesson dates."""
        response = client.get("/classes/1/lessons")
        html = response.data.decode()
        assert "2026-02-01" in html or "Feb" in html

    def test_lessons_list_shows_notes(self, client):
        """Lessons list shows teacher notes."""
        response = client.get("/classes/1/lessons")
        html = response.data.decode()
        assert "Students engaged well" in html

    def test_lessons_list_404_for_invalid_class(self, client):
        """Lessons list returns 404 for nonexistent class."""
        response = client.get("/classes/999/lessons")
        assert response.status_code == 404

    def test_lesson_log_form_returns_200(self, client):
        """Lesson log form loads."""
        response = client.get("/classes/1/lessons/new")
        assert response.status_code == 200

    def test_lesson_log_form_has_fields(self, client):
        """Lesson log form has required fields."""
        response = client.get("/classes/1/lessons/new")
        html = response.data.decode()
        assert 'name="content"' in html
        assert 'name="notes"' in html

    def test_lesson_log_post_creates_lesson(self, client):
        """POST to lesson log creates a new lesson."""
        response = client.post("/classes/1/lessons/new", data={
            "content": "Today we studied ecosystems and food webs.",
            "notes": "Used interactive simulation",
            "topics": "ecosystems, food web",
        }, follow_redirects=False)
        assert response.status_code in (302, 303)

        # Verify lesson was created
        response = client.get("/classes/1/lessons")
        html = response.data.decode()
        assert "ecosystems" in html

    def test_lesson_log_empty_class(self, client):
        """Lessons list for class with no lessons shows empty message."""
        response = client.get("/classes/2/lessons")
        html = response.data.decode()
        assert response.status_code == 200
        assert "No lessons" in html or "no lessons" in html


# ============================================================
# Task 5: Quiz Pages Tests
# ============================================================


class TestQuizzes:
    """Test quiz listing and detail pages."""

    def test_quizzes_list_returns_200(self, client):
        """Quizzes list page loads."""
        response = client.get("/quizzes")
        assert response.status_code == 200

    def test_quizzes_list_shows_quizzes(self, client):
        """Quizzes list shows seeded quizzes."""
        response = client.get("/quizzes")
        html = response.data.decode()
        assert "Change Over Time Retake" in html

    def test_quizzes_list_shows_status(self, client):
        """Quizzes list shows quiz status."""
        response = client.get("/quizzes")
        html = response.data.decode()
        assert "generated" in html.lower()

    def test_quiz_detail_returns_200(self, client):
        """Quiz detail page loads for a valid quiz."""
        response = client.get("/quizzes/1")
        assert response.status_code == 200

    def test_quiz_detail_shows_title(self, client):
        """Quiz detail shows the quiz title."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert "Change Over Time Retake" in html

    def test_quiz_detail_shows_questions(self, client):
        """Quiz detail shows questions."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert "plants make food" in html

    def test_quiz_detail_404_for_invalid_id(self, client):
        """Quiz detail returns 404 for nonexistent quiz."""
        response = client.get("/quizzes/999")
        assert response.status_code == 404

    def test_quizzes_for_class(self, client):
        """Quizzes can be filtered by class."""
        response = client.get("/classes/1/quizzes")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Change Over Time Retake" in html


# ============================================================
# Task 6: Cost Tracking Tests
# ============================================================


class TestCostTracking:
    """Test cost tracking display page."""

    def test_costs_page_returns_200(self, client):
        """Costs page loads successfully."""
        response = client.get("/costs")
        assert response.status_code == 200

    def test_costs_page_shows_provider(self, client):
        """Costs page shows current provider."""
        response = client.get("/costs")
        html = response.data.decode()
        assert "mock" in html.lower()

    def test_costs_page_shows_zero_when_mock(self, client):
        """Costs page shows zero costs when using mock provider."""
        response = client.get("/costs")
        html = response.data.decode()
        assert "$0" in html or "0.00" in html or "No API calls" in html or "no api calls" in html.lower()


# ============================================================
# Navigation Tests
# ============================================================


class TestNavigation:
    """Test that navigation links exist across all pages."""

    def test_dashboard_has_nav_links(self, client):
        """Dashboard has navigation to other sections."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "/classes" in html
        assert "/quizzes" in html

    def test_classes_page_has_nav(self, client):
        """Classes page has navigation."""
        response = client.get("/classes")
        html = response.data.decode()
        assert "/dashboard" in html

    def test_quizzes_page_has_nav(self, client):
        """Quizzes page has navigation."""
        response = client.get("/quizzes")
        html = response.data.decode()
        assert "/dashboard" in html


# ============================================================
# Task 8: Quiz Generation Page Tests
# ============================================================


class TestQuizGeneration:
    """Test quiz generation form and triggering from web."""

    def test_generate_form_returns_200(self, client):
        """Quiz generation form page loads."""
        response = client.get("/classes/1/generate")
        assert response.status_code == 200

    def test_generate_form_has_fields(self, client):
        """Quiz generation form has configuration fields."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert 'name="num_questions"' in html
        assert 'name="grade_level"' in html

    def test_generate_form_shows_class_name(self, client):
        """Quiz generation form shows which class it's for."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "Legacy Class" in html

    def test_generate_form_404_for_invalid_class(self, client):
        """Quiz generation returns 404 for nonexistent class."""
        response = client.get("/classes/999/generate")
        assert response.status_code == 404

    def test_generate_post_creates_quiz(self, client):
        """POST to generate creates a quiz and redirects to it."""
        response = client.post("/classes/1/generate", data={
            "num_questions": "5",
            "grade_level": "7th Grade",
            "sol_standards": "SOL 7.1",
        }, follow_redirects=False)
        # Should redirect to the new quiz detail
        assert response.status_code in (302, 303)
        assert "/quizzes/" in response.headers["Location"]

    def test_generate_post_quiz_appears_in_list(self, client):
        """After generating, quiz appears in the quizzes list."""
        client.post("/classes/1/generate", data={
            "num_questions": "5",
            "grade_level": "7th Grade",
        })
        response = client.get("/quizzes")
        html = response.data.decode()
        assert "generated" in html.lower()

    def test_generate_post_default_questions(self, client):
        """Generate with default num_questions works."""
        response = client.post("/classes/1/generate", data={
            "grade_level": "7th Grade",
        }, follow_redirects=False)
        assert response.status_code in (302, 303)

    def test_class_detail_has_generate_link(self, client):
        """Class detail page has a link to generate a quiz."""
        response = client.get("/classes/1")
        html = response.data.decode()
        assert "/classes/1/generate" in html


# ============================================================
# Task 9: Dashboard Charts / Stats API Tests
# ============================================================


class TestDashboardCharts:
    """Test dashboard stats API and chart rendering."""

    def test_stats_api_returns_json(self, client):
        """Stats API endpoint returns JSON."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_stats_api_has_lessons_by_date(self, client):
        """Stats API includes lessons grouped by date."""
        response = client.get("/api/stats")
        data = response.get_json()
        assert "lessons_by_date" in data

    def test_stats_api_has_quizzes_by_class(self, client):
        """Stats API includes quizzes grouped by class."""
        response = client.get("/api/stats")
        data = response.get_json()
        assert "quizzes_by_class" in data

    def test_stats_api_lessons_data_correct(self, client):
        """Stats API lessons by date contains correct data."""
        response = client.get("/api/stats")
        data = response.get_json()
        # We seeded lessons on 2026-02-01 and 2026-02-05
        dates = [entry["date"] for entry in data["lessons_by_date"]]
        assert "2026-02-01" in dates
        assert "2026-02-05" in dates

    def test_stats_api_quizzes_data_correct(self, client):
        """Stats API quizzes by class contains correct data."""
        response = client.get("/api/stats")
        data = response.get_json()
        class_names = [entry["class_name"] for entry in data["quizzes_by_class"]]
        assert "Legacy Class" in class_names

    def test_dashboard_has_chart_canvas(self, client):
        """Dashboard includes canvas elements for charts."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "lessonsChart" in html or "lessons-chart" in html


# ============================================================
# Task 10: Authentication Tests
# ============================================================


class TestAuthentication:
    """Test basic authentication for the web UI."""

    def test_login_page_returns_200(self, anon_client):
        """Login page loads."""
        response = anon_client.get("/login")
        assert response.status_code == 200

    def test_login_page_has_form(self, anon_client):
        """Login page has username and password fields."""
        response = anon_client.get("/login")
        html = response.data.decode()
        assert 'name="username"' in html
        assert 'name="password"' in html

    def test_login_with_valid_credentials(self, anon_client):
        """Login with valid credentials redirects to dashboard."""
        response = anon_client.post("/login", data={
            "username": "teacher",
            "password": "quizweaver",
        }, follow_redirects=False)
        assert response.status_code in (302, 303)
        assert "/dashboard" in response.headers["Location"]

    def test_login_with_invalid_credentials(self, anon_client):
        """Login with bad credentials shows error."""
        response = anon_client.post("/login", data={
            "username": "teacher",
            "password": "wrongpassword",
        })
        html = response.data.decode()
        assert response.status_code in (200, 401)
        assert "invalid" in html.lower() or "incorrect" in html.lower()

    def test_logout_redirects_to_login(self, client):
        """Logout clears session and redirects to login."""
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code in (302, 303)
        assert "/login" in response.headers["Location"]

    def test_protected_route_requires_login(self, anon_client):
        """Dashboard requires login when auth is enabled."""
        response = anon_client.get("/dashboard", follow_redirects=False)
        assert response.status_code in (302, 303)
        assert "/login" in response.headers["Location"]

    def test_authenticated_user_can_access_dashboard(self, auth_client):
        """Logged-in user can access dashboard."""
        response = auth_client.get("/dashboard")
        assert response.status_code == 200
        assert b"QuizWeaver" in response.data

    def test_authenticated_user_can_access_classes(self, auth_client):
        """Logged-in user can access classes."""
        response = auth_client.get("/classes")
        assert response.status_code == 200


# ============================================================
# Task 11: Edit/Delete Actions Tests
# ============================================================


class TestEditDeleteActions:
    """Test class edit, class delete, and lesson delete actions."""

    def test_class_edit_form_returns_200(self, client):
        """Class edit form loads."""
        response = client.get("/classes/1/edit")
        assert response.status_code == 200

    def test_class_edit_form_prefilled(self, client):
        """Class edit form is pre-filled with current values."""
        response = client.get("/classes/1/edit")
        html = response.data.decode()
        assert "Legacy Class" in html
        assert "7th Grade" in html

    def test_class_edit_post_updates_class(self, client):
        """POST to class edit updates the class."""
        response = client.post("/classes/1/edit", data={
            "name": "Updated Class Name",
            "grade_level": "8th Grade",
            "subject": "Biology",
        }, follow_redirects=False)
        assert response.status_code in (302, 303)

        # Verify update
        response = client.get("/classes/1")
        html = response.data.decode()
        assert "Updated Class Name" in html

    def test_class_edit_404_for_invalid_id(self, client):
        """Class edit returns 404 for nonexistent class."""
        response = client.get("/classes/999/edit")
        assert response.status_code == 404

    def test_class_delete_post_removes_class(self, client):
        """POST to class delete removes the class."""
        # Delete Block A (class 2)
        response = client.post("/classes/2/delete", follow_redirects=False)
        assert response.status_code in (302, 303)

        # Verify it's gone
        response = client.get("/classes/2")
        assert response.status_code == 404

    def test_class_delete_404_for_invalid_id(self, client):
        """Delete returns 404 for nonexistent class."""
        response = client.post("/classes/999/delete")
        assert response.status_code == 404

    def test_lesson_delete_post_removes_lesson(self, client):
        """POST to lesson delete removes the lesson."""
        # Delete lesson 1
        response = client.post("/classes/1/lessons/1/delete", follow_redirects=False)
        assert response.status_code in (302, 303)

        # Verify lesson count decreased
        response = client.get("/classes/1/lessons")
        html = response.data.decode()
        # Only 1 lesson should remain (originally 2)
        assert "cell division" in html
        # photosynthesis lesson was deleted
        assert "Students engaged well" not in html

    def test_lesson_delete_404_for_invalid_id(self, client):
        """Lesson delete returns 404 for nonexistent lesson."""
        response = client.post("/classes/1/lessons/999/delete")
        assert response.status_code == 404

    def test_class_detail_has_edit_link(self, client):
        """Class detail page has an edit link."""
        response = client.get("/classes/1")
        html = response.data.decode()
        assert "/classes/1/edit" in html

    def test_class_detail_has_delete_button(self, client):
        """Class detail page has a delete button."""
        response = client.get("/classes/1")
        html = response.data.decode()
        assert "/classes/1/delete" in html or "delete" in html.lower()


# ============================================================
# Task 12: Responsive Design Tests
# ============================================================


class TestResponsiveDesign:
    """Test responsive design elements are present."""

    def test_viewport_meta_tag(self, client):
        """Pages include viewport meta tag for mobile."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert 'name="viewport"' in html
        assert "width=device-width" in html

    def test_nav_has_mobile_toggle(self, client):
        """Navigation has a mobile toggle element."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "nav-toggle" in html or "hamburger" in html or "menu-toggle" in html

    def test_css_has_mobile_breakpoints(self, client):
        """CSS file includes mobile media queries."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.data.decode()
        assert "@media" in css
        assert "max-width" in css

    def test_form_inputs_have_proper_types(self, client):
        """Form inputs use appropriate HTML5 types for mobile."""
        response = client.get("/classes/new")
        html = response.data.decode()
        assert 'type="text"' in html
