"""
Tests for search, filtering, and pagination (Session 6, Phase C).
"""

import os
import json
import tempfile
import pytest

from src.database import Base, Class, Quiz, Question, StudySet, StudyCard, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with quizzes for search/filter testing."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Create classes
    cls1 = Class(name="Math Block A", grade_level="8th Grade", subject="Math")
    cls2 = Class(name="Science Block B", grade_level="7th Grade", subject="Science")
    session.add(cls1)
    session.add(cls2)
    session.commit()

    # Create quizzes (enough for pagination)
    for i in range(25):
        status = "generated" if i % 3 != 2 else "pending"
        class_id = cls1.id if i < 15 else cls2.id
        title = f"Algebra Quiz {i+1}" if i < 15 else f"Biology Quiz {i+1}"
        quiz = Quiz(title=title, class_id=class_id, status=status,
                    style_profile=json.dumps({}))
        session.add(quiz)
    session.commit()

    # Add a question to the first quiz for verification
    q = Question(quiz_id=1, question_type="mc", text="What is 2+2?", points=1.0,
                 data=json.dumps({"options": ["3", "4", "5"], "correct_index": 1}))
    session.add(q)
    session.commit()

    # Create study sets
    ss1 = StudySet(class_id=cls1.id, title="Algebra Flashcards", material_type="flashcard", status="generated")
    ss2 = StudySet(class_id=cls2.id, title="Biology Vocabulary", material_type="vocabulary", status="generated")
    ss3 = StudySet(class_id=cls1.id, title="Math Review", material_type="review_sheet", status="generated")
    session.add_all([ss1, ss2, ss3])
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

    yield flask_app

    flask_app.config["DB_ENGINE"].dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def client(app):
    """Logged-in test client."""
    c = app.test_client()
    # No DB users, so config-based auth works
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


# ============================================================
# TestQuizSearch
# ============================================================

class TestQuizSearch:
    """Test quiz search, filtering, and pagination."""

    def test_search_by_title(self, client):
        """Search finds quizzes by title."""
        resp = client.get("/quizzes?q=Algebra")
        assert resp.status_code == 200
        assert b"Algebra Quiz" in resp.data
        assert b"Biology Quiz" not in resp.data

    def test_search_no_results(self, client):
        """Search with no matches shows empty state."""
        resp = client.get("/quizzes?q=Nonexistent")
        assert resp.status_code == 200
        assert b"No quizzes found" in resp.data

    def test_filter_by_status(self, client):
        """Filter by status shows only matching quizzes."""
        resp = client.get("/quizzes?status=pending")
        assert resp.status_code == 200
        assert b"pending" in resp.data

    def test_filter_by_class(self, client):
        """Filter by class shows only that class's quizzes."""
        resp = client.get("/quizzes?class_id=2")
        assert resp.status_code == 200
        assert b"Biology Quiz" in resp.data

    def test_combined_filters(self, client):
        """Multiple filters can be combined."""
        resp = client.get("/quizzes?q=Algebra&status=generated")
        assert resp.status_code == 200

    def test_pagination_first_page(self, client):
        """First page shows up to 20 quizzes."""
        resp = client.get("/quizzes?page=1")
        assert resp.status_code == 200
        assert b"Page 1 of" in resp.data

    def test_pagination_second_page(self, client):
        """Second page shows remaining quizzes."""
        resp = client.get("/quizzes?page=2")
        assert resp.status_code == 200
        assert b"Page 2 of" in resp.data

    def test_pagination_out_of_range(self, client):
        """Out-of-range page is clamped to last page."""
        resp = client.get("/quizzes?page=999")
        assert resp.status_code == 200
        # Should not crash; shows last valid page

    def test_all_classes_in_filter(self, client):
        """All classes appear in the filter dropdown."""
        resp = client.get("/quizzes")
        assert b"Math Block A" in resp.data
        assert b"Science Block B" in resp.data


# ============================================================
# TestStudySearch
# ============================================================

class TestStudySearch:
    """Test study materials search."""

    def test_search_by_title(self, client):
        """Search finds study sets by title."""
        resp = client.get("/study?q=Algebra")
        assert resp.status_code == 200
        assert b"Algebra Flashcards" in resp.data
        assert b"Biology Vocabulary" not in resp.data

    def test_combined_search_and_type(self, client):
        """Search and type filter can be combined."""
        resp = client.get("/study?q=Math&type=review_sheet")
        assert resp.status_code == 200
        assert b"Math Review" in resp.data

    def test_search_no_results(self, client):
        """Search with no matches shows empty state."""
        resp = client.get("/study?q=Nonexistent")
        assert resp.status_code == 200
        assert b"No study materials" in resp.data
