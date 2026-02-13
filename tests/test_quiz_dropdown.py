"""
Tests for BL-009: Source Quiz Dropdown with better context.

Verifies that quiz dropdowns show richer metadata (question count, date,
standards) in the API endpoint and in server-rendered templates.
"""

import json
import os
import tempfile
from datetime import datetime

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with seeded data for dropdown testing."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Create a class
    cls = Class(
        name="Biology Period 3",
        grade_level="9th Grade",
        subject="Biology",
        standards=json.dumps(["BIO.1", "BIO.2"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    # Create quizzes with varying metadata
    quiz1 = Quiz(
        title="Cell Division Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps(
            {
                "grade_level": "9th Grade",
                "sol_standards": ["BIO.1", "BIO.2"],
                "num_questions": 10,
            }
        ),
        created_at=datetime(2026, 1, 15, 10, 0, 0),
    )
    session.add(quiz1)
    session.commit()

    # Add questions to quiz1
    for i in range(5):
        q = Question(
            quiz_id=quiz1.id,
            text=f"Question {i + 1} about cell division?",
            question_type="mc",
            points=2,
            data=json.dumps(
                {
                    "options": ["A", "B", "C", "D"],
                    "correct_index": 0,
                }
            ),
        )
        session.add(q)

    quiz2 = Quiz(
        title="Photosynthesis Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps(
            {
                "grade_level": "9th Grade",
                "sol_standards": ["BIO.3"],
            }
        ),
        created_at=datetime(2026, 2, 1, 14, 30, 0),
    )
    session.add(quiz2)
    session.commit()

    # Add questions to quiz2
    for i in range(3):
        q = Question(
            quiz_id=quiz2.id,
            text=f"Question {i + 1} about photosynthesis?",
            question_type="mc",
            points=1,
            data=json.dumps(
                {
                    "options": ["A", "B", "C", "D"],
                    "correct_index": 1,
                }
            ),
        )
        session.add(q)

    # Quiz with no title (edge case)
    quiz3 = Quiz(
        title=None,
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({}),
        created_at=datetime(2026, 2, 5, 9, 0, 0),
    )
    session.add(quiz3)
    session.commit()

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "9th Grade"},
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


class TestApiClassQuizzes:
    """Test the /api/classes/<id>/quizzes endpoint returns rich metadata."""

    def test_returns_quiz_list(self, client):
        """API returns a list of quizzes for the class."""
        response = client.get("/api/classes/1/quizzes")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 3

    def test_includes_question_count(self, client):
        """Each quiz entry includes question_count."""
        response = client.get("/api/classes/1/quizzes")
        data = response.get_json()
        # Quizzes are ordered by created_at desc, so quiz3 first, then quiz2, then quiz1
        titles = [q["title"] for q in data]
        for q in data:
            assert "question_count" in q

        # Find quiz1 (Cell Division) - has 5 questions
        cell_quiz = next(q for q in data if q["title"] == "Cell Division Quiz")
        assert cell_quiz["question_count"] == 5

        # Find quiz2 (Photosynthesis) - has 3 questions
        photo_quiz = next(q for q in data if q["title"] == "Photosynthesis Quiz")
        assert photo_quiz["question_count"] == 3

    def test_includes_date(self, client):
        """Each quiz entry includes a formatted date."""
        response = client.get("/api/classes/1/quizzes")
        data = response.get_json()
        cell_quiz = next(q for q in data if q["title"] == "Cell Division Quiz")
        assert cell_quiz["date"] == "Jan 15"

        photo_quiz = next(q for q in data if q["title"] == "Photosynthesis Quiz")
        assert photo_quiz["date"] == "Feb 01"

    def test_includes_standards(self, client):
        """Each quiz entry includes standards from style_profile."""
        response = client.get("/api/classes/1/quizzes")
        data = response.get_json()
        cell_quiz = next(q for q in data if q["title"] == "Cell Division Quiz")
        assert "BIO.1" in cell_quiz["standards"]
        assert "BIO.2" in cell_quiz["standards"]

    def test_includes_reading_level(self, client):
        """Each quiz entry includes reading_level (empty string if not a variant)."""
        response = client.get("/api/classes/1/quizzes")
        data = response.get_json()
        for q in data:
            assert "reading_level" in q

    def test_no_title_fallback(self, client):
        """Quizzes with no title get a fallback title."""
        response = client.get("/api/classes/1/quizzes")
        data = response.get_json()
        # quiz3 has no title
        untitled = [q for q in data if "Quiz #" in q["title"]]
        assert len(untitled) == 1

    def test_ordered_by_most_recent_first(self, client):
        """Quizzes are returned most recent first."""
        response = client.get("/api/classes/1/quizzes")
        data = response.get_json()
        dates = [q["date"] for q in data]
        # Feb 05 should come before Feb 01, which comes before Jan 15
        assert dates[0] == "Feb 05"
        assert dates[1] == "Feb 01"
        assert dates[2] == "Jan 15"


class TestImportPageQuizDropdown:
    """Verify the import page quiz dropdown shows rich labels."""

    def test_dropdown_shows_question_count(self, client):
        """Import page quiz dropdown shows question count."""
        response = client.get("/classes/1/analytics/import")
        html = response.data.decode()
        assert "5 Qs" in html
        assert "3 Qs" in html

    def test_dropdown_shows_date(self, client):
        """Import page quiz dropdown shows creation date."""
        response = client.get("/classes/1/analytics/import")
        html = response.data.decode()
        assert "Jan 15" in html
        assert "Feb 01" in html

    def test_dropdown_has_all_quizzes(self, client):
        """Import page quiz dropdown lists all class quizzes."""
        response = client.get("/classes/1/analytics/import")
        html = response.data.decode()
        assert "Cell Division Quiz" in html
        assert "Photosynthesis Quiz" in html


class TestQuizScoresPageDropdown:
    """Verify the quiz scores page dropdown shows rich labels."""

    def test_dropdown_shows_question_count(self, client):
        """Quiz scores page dropdown shows question count."""
        response = client.get("/classes/1/analytics/quiz-scores")
        html = response.data.decode()
        assert "5 Qs" in html
        assert "3 Qs" in html

    def test_dropdown_shows_date(self, client):
        """Quiz scores page dropdown shows creation date."""
        response = client.get("/classes/1/analytics/quiz-scores")
        html = response.data.decode()
        assert "Jan 15" in html
        assert "Feb 01" in html


class TestStudyGenerateDropdownJS:
    """Verify the study generate form includes the JS for rich dropdowns."""

    def test_study_js_loaded(self, client):
        """Study generate page loads study.js."""
        response = client.get("/study/generate")
        html = response.data.decode()
        assert "study.js" in html

    def test_study_js_builds_rich_labels(self):
        """study.js contains code to build rich dropdown labels."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "study.js")
        with open(path) as f:
            content = f.read()
        assert "question_count" in content
        assert "standards" in content
        assert "reading_level" in content
