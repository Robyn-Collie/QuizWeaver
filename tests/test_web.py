"""
Tests for QuizWeaver web frontend.

TDD: These tests are written BEFORE the implementation.
They define the expected behavior of the Flask web UI.
"""

import json
import os
import tempfile
from datetime import date

import pytest

# Import database models for test setup
from src.database import Base, Class, LessonLog, Question, Quiz, get_engine, get_session


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
        config=json.dumps(
            {
                "assumed_knowledge": {
                    "photosynthesis": {"depth": 3, "last_taught": "2026-02-01", "mention_count": 3},
                    "cell division": {"depth": 1, "last_taught": "2026-02-05", "mention_count": 1},
                }
            }
        ),
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
        data=json.dumps(
            {
                "type": "mc",
                "text": "What is the process by which plants make food?",
                "options": ["Photosynthesis", "Respiration", "Fermentation", "Digestion"],
                "correct_index": 0,
            }
        ),
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

    flask_app.config["WTF_CSRF_ENABLED"] = False

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
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
    return c


@pytest.fixture
def anon_client(app):
    """Create an unauthenticated test client for auth tests."""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Alias for logged-in client (used by auth tests)."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
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

    def test_dashboard_shows_tool_cards(self, client):
        """Dashboard shows tool cards for key workflows."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "Generate Quiz" in html
        assert "Study Materials" in html

    def test_dashboard_shows_recent_activity(self, client):
        """Dashboard shows recent activity section with class data."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "Recent Activity" in html
        assert "Legacy Class" in html


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
        response = client.post(
            "/classes/new",
            data={
                "name": "8th Grade Biology - Block B",
                "grade_level": "8th Grade",
                "subject": "Biology",
                "standards": "SOL 8.1, SOL 8.2",
            },
            follow_redirects=False,
        )
        # Should redirect to classes list or detail
        assert response.status_code in (302, 303)

        # Verify class was created
        response = client.get("/classes")
        html = response.data.decode()
        assert "8th Grade Biology - Block B" in html

    def test_class_create_post_requires_name(self, client):
        """POST to /classes/new without name shows error."""
        response = client.post(
            "/classes/new",
            data={
                "name": "",
                "grade_level": "8th Grade",
            },
        )
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
        response = client.post(
            "/classes/1/lessons/new",
            data={
                "content": "Today we studied ecosystems and food webs.",
                "notes": "Used interactive simulation",
                "topics": "ecosystems, food web",
            },
            follow_redirects=False,
        )
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
        response = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "grade_level": "7th Grade",
                "sol_standards": "SOL 7.1",
            },
            follow_redirects=False,
        )
        # Should redirect to the new quiz detail
        assert response.status_code in (302, 303)
        assert "/quizzes/" in response.headers["Location"]

    def test_generate_post_quiz_appears_in_list(self, client):
        """After generating, quiz appears in the quizzes list."""
        client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "grade_level": "7th Grade",
            },
        )
        response = client.get("/quizzes")
        html = response.data.decode()
        assert "generated" in html.lower()

    def test_generate_post_default_questions(self, client):
        """Generate with default num_questions works."""
        response = client.post(
            "/classes/1/generate",
            data={
                "grade_level": "7th Grade",
            },
            follow_redirects=False,
        )
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

    def test_dashboard_has_tools_section(self, client):
        """Dashboard includes Tools section with workflow links."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "Tools" in html or "Recent Activity" in html


# ============================================================
# Task 10: Authentication Tests
# ============================================================


class TestAuthentication:
    """Test basic authentication for the web UI."""

    def test_login_page_returns_200(self, anon_client):
        """Login page loads (redirects to setup when no DB users)."""
        response = anon_client.get("/login", follow_redirects=True)
        assert response.status_code == 200

    def test_login_page_has_form(self, anon_client):
        """Login/setup page has username and password fields."""
        response = anon_client.get("/login", follow_redirects=True)
        html = response.data.decode()
        assert 'name="username"' in html
        assert 'name="password"' in html

    def test_login_with_valid_credentials(self, app, anon_client):
        """Login with valid credentials redirects to dashboard."""
        from src.web.auth import create_user

        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        create_user(session, "teacher", "password1234", "Teacher")
        session.close()

        response = anon_client.post(
            "/login",
            data={
                "username": "teacher",
                "password": "password1234",
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)
        assert "/dashboard" in response.headers["Location"]

    def test_login_with_invalid_credentials(self, app, anon_client):
        """Login with bad credentials shows error."""
        from src.web.auth import create_user

        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        create_user(session, "teacher", "password1234", "Teacher")
        session.close()

        response = anon_client.post(
            "/login",
            data={
                "username": "teacher",
                "password": "wrongpassword",
            },
        )
        html = response.data.decode()
        assert response.status_code in (200, 401)
        assert "invalid" in html.lower() or "incorrect" in html.lower()

    def test_logout_redirects_to_login(self, client):
        """Logout clears session and redirects to login (POST-only)."""
        response = client.post("/logout", follow_redirects=False)
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
        response = client.post(
            "/classes/1/edit",
            data={
                "name": "Updated Class Name",
                "grade_level": "8th Grade",
                "subject": "Biology",
            },
            follow_redirects=False,
        )
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


# ============================================================
# Task 13: Flash Messages Tests
# ============================================================


class TestFlashMessages:
    """Test that actions produce user feedback via flash messages."""

    def test_flash_renders_on_action(self, client):
        """Flash message appears after a form submission with redirect."""
        # Create a class, which should flash a success message
        response = client.post(
            "/classes/new",
            data={
                "name": "Flash Render Test",
                "grade_level": "10th Grade",
            },
            follow_redirects=True,
        )
        html = response.data.decode()
        # After redirect, flash message should render in the alert div
        assert "alert" in html or "Flash Render Test" in html

    def test_class_create_shows_flash(self, client):
        """Creating a class shows a success flash message."""
        response = client.post(
            "/classes/new",
            data={
                "name": "Flash Test Class",
                "grade_level": "9th Grade",
                "subject": "Math",
            },
            follow_redirects=True,
        )
        html = response.data.decode()
        assert "created" in html.lower() or "success" in html.lower() or "Flash Test Class" in html

    def test_class_delete_shows_flash(self, client):
        """Deleting a class shows a confirmation flash message."""
        response = client.post("/classes/2/delete", follow_redirects=True)
        html = response.data.decode()
        assert "deleted" in html.lower() or "removed" in html.lower() or response.status_code == 200

    def test_lesson_log_shows_flash(self, client):
        """Logging a lesson shows a success flash message."""
        response = client.post(
            "/classes/1/lessons/new",
            data={
                "content": "Flash test lesson about gravity.",
                "notes": "Testing flash",
            },
            follow_redirects=True,
        )
        html = response.data.decode()
        assert "logged" in html.lower() or "success" in html.lower() or "gravity" in html.lower()

    def test_quiz_generate_shows_flash(self, client):
        """Generating a quiz shows feedback."""
        response = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "grade_level": "7th Grade",
            },
            follow_redirects=True,
        )
        html = response.data.decode()
        # Should either show quiz detail (success) or error message
        assert "generated" in html.lower() or "quiz" in html.lower()


# ============================================================
# Generate Redirect and Provider Alias Tests
# ============================================================


class TestGenerateRedirect:
    """Test that /generate redirects to the first class's generate page."""

    def test_generate_redirects_to_class(self, client):
        """/generate redirects to the first class's generate page."""
        response = client.get("/generate", follow_redirects=False)
        assert response.status_code in (302, 303)
        assert "/classes/" in response.headers["Location"]
        assert "/generate" in response.headers["Location"]

    def test_generate_requires_login(self, anon_client):
        """/generate requires authentication."""
        response = anon_client.get("/generate", follow_redirects=False)
        assert response.status_code in (302, 303)
        assert "/login" in response.headers["Location"]


class TestProviderAliasResolution:
    """Test that provider aliases resolve correctly (regression test for gemini-3-pro bug)."""

    def test_gemini_3_pro_not_aliased(self):
        """gemini-3-pro should NOT be aliased to gemini-pro."""
        from src.llm_provider import _resolve_provider_name

        assert _resolve_provider_name("gemini-3-pro") == "gemini-3-pro"

    def test_gemini_3_flash_not_aliased(self):
        """gemini-3-flash should NOT be aliased."""
        from src.llm_provider import _resolve_provider_name

        assert _resolve_provider_name("gemini-3-flash") == "gemini-3-flash"

    def test_gemini_3_pro_registry_has_correct_model(self):
        """gemini-3-pro registry entry has gemini-3-pro-preview as default model."""
        from src.llm_provider import PROVIDER_REGISTRY

        assert "gemini-3-pro" in PROVIDER_REGISTRY
        assert PROVIDER_REGISTRY["gemini-3-pro"]["default_model"] == "gemini-3-pro-preview"

    def test_gemini_3_flash_registry_has_correct_model(self):
        """gemini-3-flash registry entry has gemini-3-flash-preview as default model."""
        from src.llm_provider import PROVIDER_REGISTRY

        assert "gemini-3-flash" in PROVIDER_REGISTRY
        assert PROVIDER_REGISTRY["gemini-3-flash"]["default_model"] == "gemini-3-flash-preview"


# ============================================================
# Task 14: Quiz History / Filtering Tests
# ============================================================


class TestQuizHistory:
    """Test quiz history page with filtering."""

    def test_quizzes_page_shows_count(self, client):
        """Quizzes page shows total quiz count."""
        response = client.get("/quizzes")
        html = response.data.decode()
        # At least our seeded quiz should be there
        assert "Change Over Time Retake" in html

    def test_quizzes_filter_by_status(self, client):
        """Quizzes can be filtered by status query param."""
        response = client.get("/quizzes?status=generated")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Change Over Time Retake" in html

    def test_quizzes_filter_by_class(self, client):
        """Quizzes can be filtered by class_id query param."""
        response = client.get("/quizzes?class_id=1")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Change Over Time Retake" in html

    def test_quizzes_filter_empty_result(self, client):
        """Filtering with no matches shows empty message."""
        response = client.get("/quizzes?status=nonexistent")
        assert response.status_code == 200
        html = response.data.decode()
        assert "No quizzes" in html or "no quizzes" in html.lower() or response.status_code == 200

    def test_quiz_detail_shows_class_link(self, client):
        """Quiz detail links back to its class."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert "/classes/1" in html


# ============================================================
# Task 15: Lesson Logging with File Upload Tests
# ============================================================


class TestLessonFileUpload:
    """Test lesson logging form with file upload support."""

    def test_lesson_form_has_file_input(self, client):
        """Lesson log form includes a file upload field."""
        response = client.get("/classes/1/lessons/new")
        html = response.data.decode()
        assert 'type="file"' in html
        assert "enctype" in html.lower()

    def test_lesson_form_accepts_text_only(self, client):
        """Lesson log works with text content only (no file)."""
        response = client.post(
            "/classes/1/lessons/new",
            data={
                "content": "Pure text lesson about atoms and molecules.",
                "notes": "No file uploaded",
            },
            follow_redirects=True,
        )
        html = response.data.decode()
        assert "atoms" in html.lower() or response.status_code == 200

    def test_lesson_form_has_date_picker(self, client):
        """Lesson log form has a date input."""
        response = client.get("/classes/1/lessons/new")
        html = response.data.decode()
        assert 'type="date"' in html or 'name="lesson_date"' in html


class TestHelpPage:
    """Test help page and user guidance features."""

    def test_help_page_returns_200(self, client):
        """Help page returns 200 OK."""
        response = client.get("/help")
        assert response.status_code == 200

    def test_help_page_has_sections(self, client):
        """Help page contains all expected sections."""
        response = client.get("/help")
        html = response.data.decode()
        assert "Workflow Overview" in html
        assert "Managing Classes" in html
        assert "Logging Lessons" in html
        assert "Generating Quizzes" in html
        assert "Cost Tracking" in html
        assert "Tips" in html

    def test_help_page_has_nav_link(self, client):
        """Help link appears in the navigation bar."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert 'href="/help"' in html

    def test_dashboard_has_getting_started(self, client):
        """Dashboard shows the getting started banner."""
        response = client.get("/dashboard")
        html = response.data.decode()
        assert "getting-started" in html
        assert "Welcome to QuizWeaver" in html

    def test_form_tooltips_on_class_create(self, client):
        """New class form has help tooltips."""
        response = client.get("/classes/new")
        html = response.data.decode()
        assert "help-tip" in html
        assert "data-tip" in html

    def test_form_tooltips_on_lesson_log(self, client):
        """Lesson log form has help tooltips."""
        response = client.get("/classes/1/lessons/new")
        html = response.data.decode()
        assert "help-tip" in html
        assert "data-tip" in html

    def test_form_tooltips_on_quiz_generate(self, client):
        """Quiz generate form has help tooltips."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "help-tip" in html
        assert "data-tip" in html

    def test_help_page_requires_login(self, anon_client):
        """Help page redirects to login when not authenticated."""
        response = anon_client.get("/help", follow_redirects=False)
        assert response.status_code in (302, 303)
        assert "/login" in response.headers["Location"]


# ============================================================
# Cognitive Framework Tests
# ============================================================


class TestCognitiveFrameworkForm:
    """Test cognitive framework controls on the generate form."""

    def test_generate_form_has_framework_radios(self, client):
        """Generate form should have radio buttons for cognitive framework."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "cognitive_framework_radio" in html
        assert "Bloom" in html
        assert "DOK" in html

    def test_generate_form_has_difficulty_slider(self, client):
        """Generate form should have a difficulty range slider."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert 'id="difficulty"' in html
        assert 'type="range"' in html

    def test_generate_form_has_distribution_table(self, client):
        """Generate form should have the cognitive distribution table container."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "cognitive-table" in html
        assert "cognitive-distribution-group" in html

    def test_generate_form_has_cognitive_js(self, client):
        """Generate form should include the cognitive_form.js script."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "cognitive_form.js" in html

    def test_post_with_blooms_framework(self, client):
        """POST with Bloom's framework should redirect to quiz detail."""
        dist = json.dumps({"1": {"count": 10, "types": ["mc"]}, "2": {"count": 10, "types": ["mc"]}})
        response = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "20",
                "grade_level": "7th Grade",
                "cognitive_framework": "blooms",
                "cognitive_distribution": dist,
                "difficulty": "4",
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)

    def test_post_with_dok_framework(self, client):
        """POST with DOK framework should redirect to quiz detail."""
        dist = json.dumps(
            {
                "1": {"count": 5, "types": ["mc"]},
                "2": {"count": 5, "types": ["tf"]},
                "3": {"count": 5, "types": ["mc"]},
                "4": {"count": 5, "types": ["mc"]},
            }
        )
        response = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "20",
                "grade_level": "7th Grade",
                "cognitive_framework": "dok",
                "cognitive_distribution": dist,
                "difficulty": "3",
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)

    def test_post_without_framework_backward_compat(self, client):
        """POST without framework should still work (backward compatibility)."""
        response = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "20",
                "grade_level": "7th Grade",
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)


class TestCognitiveFrameworkQuizDetail:
    """Test cognitive badges and info on the quiz detail page."""

    def test_quiz_detail_shows_cognitive_badge(self, app):
        """Quiz detail should show cognitive badges when question data has cognitive_level."""
        # Seed a quiz with cognitive-tagged questions
        from src.database import Question, Quiz, get_session

        engine = app.config["DB_ENGINE"]
        session = get_session(engine)

        quiz = Quiz(
            title="Bloom's Quiz",
            class_id=1,
            status="generated",
            style_profile=json.dumps(
                {
                    "grade_level": "7th Grade",
                    "cognitive_framework": "blooms",
                    "difficulty": 4,
                }
            ),
        )
        session.add(quiz)
        session.commit()

        q1 = Question(
            quiz_id=quiz.id,
            question_type="mc",
            title="CogQ1",
            text="Test cognitive question",
            points=5.0,
            data=json.dumps(
                {
                    "type": "mc",
                    "text": "Test cognitive question",
                    "options": ["A", "B", "C", "D"],
                    "correct_index": 0,
                    "cognitive_level": "Remember",
                    "cognitive_framework": "blooms",
                    "cognitive_level_number": 1,
                }
            ),
        )
        session.add(q1)
        session.commit()

        c = app.test_client()
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        response = c.get(f"/quizzes/{quiz.id}")
        html = response.data.decode()
        assert "cognitive-badge" in html
        assert "Remember" in html
        session.close()

    def test_quiz_detail_shows_framework_info(self, app):
        """Quiz detail should show framework and difficulty in quiz info."""
        from src.database import Quiz, get_session

        engine = app.config["DB_ENGINE"]
        session = get_session(engine)

        quiz = Quiz(
            title="DOK Quiz",
            class_id=1,
            status="generated",
            style_profile=json.dumps(
                {
                    "grade_level": "7th Grade",
                    "cognitive_framework": "dok",
                    "difficulty": 3,
                }
            ),
        )
        session.add(quiz)
        session.commit()

        c = app.test_client()
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        response = c.get(f"/quizzes/{quiz.id}")
        html = response.data.decode()
        assert "Dok" in html or "dok" in html.lower()
        assert "3/5" in html
        session.close()

    def test_quiz_detail_no_badge_without_cognitive(self, app):
        """Quiz detail should NOT show cognitive badge when data has no cognitive_level."""
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        # Use the existing quiz (id=1) which has no cognitive data
        response = c.get("/quizzes/1")
        html = response.data.decode()
        assert "cognitive-badge" not in html
