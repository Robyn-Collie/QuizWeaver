"""
Tests for QuizWeaver web frontend.

TDD: These tests are written BEFORE the implementation.
They define the expected behavior of the Flask web UI.
"""

import os
import json
import tempfile
import pytest
from datetime import date, datetime

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

    # Add lesson logs for the legacy class
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
    """Create a test client for the Flask app."""
    return app.test_client()


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
