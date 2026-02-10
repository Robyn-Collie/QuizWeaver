"""
Tests for AI literacy notices across the application.

Verifies that AI-generated content banners appear on output pages
and that the privacy notice appears on the lesson logging form.
"""

import os
import json
import tempfile
import pytest
from datetime import date

from src.database import (
    Base, Class, LessonLog, Quiz, Question,
    StudySet, StudyCard, Rubric, RubricCriterion,
    PerformanceData,
    get_engine, get_session,
)


@pytest.fixture
def app():
    """Create a Flask test app with seeded data for all output pages."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed class
    cls = Class(
        name="Test Class",
        grade_level="8th Grade",
        subject="Math",
        standards=json.dumps(["SOL 8.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    # Seed lesson
    lesson = LessonLog(
        class_id=cls.id,
        date=date(2026, 2, 1),
        content="Test lesson content.",
        topics=json.dumps(["algebra"]),
        notes=None,
    )
    session.add(lesson)
    session.commit()

    # Seed quiz with questions
    quiz = Quiz(
        title="Test Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "8th Grade"}),
    )
    session.add(quiz)
    session.commit()

    question = Question(
        quiz_id=quiz.id,
        text="What is 2+2?",
        question_type="mc",
        points=1,
        data=json.dumps({
            "options": ["3", "4", "5", "6"],
            "correct_index": 1,
        }),
    )
    session.add(question)
    session.commit()

    # Seed study set with cards
    study_set = StudySet(
        title="Test Flashcards",
        class_id=cls.id,
        material_type="flashcard",
        status="generated",
        config=json.dumps({}),
    )
    session.add(study_set)
    session.commit()

    card = StudyCard(
        study_set_id=study_set.id,
        card_type="flashcard",
        front="Term",
        back="Definition",
        data=json.dumps({"tags": ["algebra"]}),
        sort_order=0,
    )
    session.add(card)
    session.commit()

    # Seed rubric
    rubric = Rubric(
        title="Test Rubric",
        quiz_id=quiz.id,
        status="generated",
    )
    session.add(rubric)
    session.commit()

    criterion = RubricCriterion(
        rubric_id=rubric.id,
        criterion="Understanding",
        description="Shows understanding",
        max_points=4,
        levels=json.dumps([
            {"label": "Beginning", "description": "Limited"},
            {"label": "Developing", "description": "Partial"},
            {"label": "Proficient", "description": "Good"},
            {"label": "Advanced", "description": "Excellent"},
        ]),
        sort_order=0,
    )
    session.add(criterion)
    session.commit()

    # Seed performance data for reteach
    perf = PerformanceData(
        class_id=cls.id,
        topic="algebra",
        avg_score=0.45,
        date=date(2026, 2, 1),
        source="manual_entry",
        sample_size=25,
    )
    session.add(perf)
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
    """Create a logged-in test client."""
    c = app.test_client()
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


class TestLessonPrivacyNotice:
    """Test privacy notice on lesson logging form."""

    def test_privacy_notice_present(self, client):
        """Privacy notice appears on the new lesson form."""
        response = client.get("/classes/1/lessons/new")
        html = response.data.decode()
        assert "ai-notice-privacy" in html

    def test_privacy_mentions_no_pii(self, client):
        """Privacy notice warns against including student names."""
        response = client.get("/classes/1/lessons/new")
        html = response.data.decode()
        assert "student names" in html.lower() or "personally identifying" in html.lower()

    def test_privacy_mentions_ai_provider(self, client):
        """Privacy notice mentions data is sent to AI provider."""
        response = client.get("/classes/1/lessons/new")
        html = response.data.decode()
        assert "AI provider" in html

    def test_privacy_links_to_help(self, client):
        """Privacy notice links to help page."""
        response = client.get("/classes/1/lessons/new")
        html = response.data.decode()
        assert "/help" in html


class TestQuizAIBanner:
    """Test AI-generated banner on quiz detail page."""

    def test_banner_present(self, client):
        """AI notice banner appears on quiz detail."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert "ai-notice" in html

    def test_banner_mentions_review(self, client):
        """Banner tells teacher to review content."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert "review" in html.lower()

    def test_banner_mentions_ai_generated(self, client):
        """Banner identifies content as AI-generated."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert "AI-Generated" in html

    def test_banner_links_to_help(self, client):
        """Banner links to help page."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert "/help" in html


class TestStudyAIBanner:
    """Test AI-generated banner on study material detail page."""

    def test_banner_present(self, client):
        """AI notice banner appears on study detail."""
        response = client.get("/study/1")
        html = response.data.decode()
        assert "ai-notice" in html

    def test_banner_mentions_ai_generated(self, client):
        """Banner identifies content as AI-generated."""
        response = client.get("/study/1")
        html = response.data.decode()
        assert "AI-Generated" in html

    def test_banner_links_to_help(self, client):
        """Banner links to help page."""
        response = client.get("/study/1")
        html = response.data.decode()
        assert "/help" in html


class TestRubricAIBanner:
    """Test AI-generated banner on rubric detail page."""

    def test_banner_present(self, client):
        """AI notice banner appears on rubric detail."""
        response = client.get("/rubrics/1")
        html = response.data.decode()
        assert "ai-notice" in html

    def test_banner_mentions_ai_generated(self, client):
        """Banner identifies content as AI-generated."""
        response = client.get("/rubrics/1")
        html = response.data.decode()
        assert "AI-Generated" in html

    def test_banner_mentions_review(self, client):
        """Banner tells teacher to review criteria."""
        response = client.get("/rubrics/1")
        html = response.data.decode()
        assert "review" in html.lower()


class TestReteachAIBanner:
    """Test AI-generated banner on re-teach suggestions page."""

    def test_banner_after_generation(self, client):
        """AI notice appears after generating suggestions."""
        response = client.post(
            "/classes/1/analytics/reteach",
            data={"focus_topics": "algebra", "max_suggestions": "3"},
            follow_redirects=True,
        )
        html = response.data.decode()
        assert "ai-notice" in html

    def test_banner_mentions_professional_judgment(self, client):
        """Banner mentions using professional judgment."""
        response = client.post(
            "/classes/1/analytics/reteach",
            data={"focus_topics": "algebra", "max_suggestions": "3"},
            follow_redirects=True,
        )
        html = response.data.decode()
        assert "professional judgment" in html.lower()

    def test_no_banner_before_generation(self, client):
        """AI notice does not appear before suggestions are generated."""
        response = client.get("/classes/1/analytics/reteach")
        html = response.data.decode()
        # The ai-notice should not be there when no suggestions exist yet
        assert "AI-Generated Content" not in html or "suggestions" not in html.lower()
