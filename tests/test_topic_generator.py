"""Tests for the topic-based generation module."""

import json
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base, Class, LessonLog, Quiz, StudySet
from src.lesson_tracker import log_lesson
from src.topic_generator import (
    VALID_OUTPUT_TYPES,
    generate_from_topics,
    get_class_topics,
    search_topics,
)


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def class_with_lessons(db_session):
    """Create a class with logged lessons and topics."""
    cls = Class(
        name="7th Grade Science",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1E"]),
        config=json.dumps({}),
    )
    db_session.add(cls)
    db_session.commit()

    # Log lessons with topics
    log_lesson(
        db_session,
        class_id=cls.id,
        content="Today we studied photosynthesis and the water cycle.",
        topics=["photosynthesis", "water cycle"],
    )
    log_lesson(
        db_session,
        class_id=cls.id,
        content="Review of cell division and mitosis.",
        topics=["cell division", "mitosis"],
    )
    log_lesson(
        db_session,
        class_id=cls.id,
        content="Lab on photosynthesis rates.",
        topics=["photosynthesis"],
    )

    return cls


class TestGetClassTopics:
    def test_returns_all_unique_topics(self, db_session, class_with_lessons):
        topics = get_class_topics(db_session, class_with_lessons.id)
        assert "photosynthesis" in topics
        assert "water cycle" in topics
        assert "cell division" in topics
        assert "mitosis" in topics
        # Should be unique (photosynthesis appears in 2 lessons)
        assert topics.count("photosynthesis") == 1

    def test_returns_sorted(self, db_session, class_with_lessons):
        topics = get_class_topics(db_session, class_with_lessons.id)
        assert topics == sorted(topics)

    def test_empty_for_no_lessons(self, db_session):
        cls = Class(name="Empty", config=json.dumps({}))
        db_session.add(cls)
        db_session.commit()
        topics = get_class_topics(db_session, cls.id)
        assert topics == []

    def test_handles_json_string_topics(self, db_session):
        cls = Class(name="Test", config=json.dumps({}))
        db_session.add(cls)
        db_session.commit()
        lesson = LessonLog(
            class_id=cls.id,
            content="test",
            topics='["alpha", "beta"]',
        )
        db_session.add(lesson)
        db_session.commit()
        topics = get_class_topics(db_session, cls.id)
        assert "alpha" in topics
        assert "beta" in topics


class TestSearchTopics:
    def test_search_finds_matching(self, db_session, class_with_lessons):
        results = search_topics(db_session, class_with_lessons.id, "photo")
        assert "photosynthesis" in results

    def test_search_case_insensitive(self, db_session, class_with_lessons):
        results = search_topics(db_session, class_with_lessons.id, "WATER")
        assert "water cycle" in results

    def test_search_no_match(self, db_session, class_with_lessons):
        results = search_topics(db_session, class_with_lessons.id, "quantum")
        assert results == []

    def test_empty_query_returns_all(self, db_session, class_with_lessons):
        results = search_topics(db_session, class_with_lessons.id, "")
        assert len(results) == 4  # all unique topics


class TestGenerateFromTopics:
    def test_generates_quiz(self, db_session, class_with_lessons):
        config = {"llm": {"provider": "mock"}}
        result = generate_from_topics(
            session=db_session,
            class_id=class_with_lessons.id,
            topics=["photosynthesis"],
            output_type="quiz",
            config=config,
            num_questions=5,
        )
        assert result is not None
        assert isinstance(result, Quiz)
        assert result.status == "generated"
        assert "photosynthesis" in result.title.lower()

    def test_generates_flashcards(self, db_session, class_with_lessons):
        config = {"llm": {"provider": "mock"}}
        result = generate_from_topics(
            session=db_session,
            class_id=class_with_lessons.id,
            topics=["cell division"],
            output_type="flashcard",
            config=config,
        )
        assert result is not None
        assert isinstance(result, StudySet)
        assert result.material_type == "flashcard"

    def test_generates_study_guide(self, db_session, class_with_lessons):
        config = {"llm": {"provider": "mock"}}
        result = generate_from_topics(
            session=db_session,
            class_id=class_with_lessons.id,
            topics=["mitosis", "cell division"],
            output_type="study_guide",
            config=config,
        )
        assert result is not None
        assert isinstance(result, StudySet)
        assert result.material_type == "study_guide"

    def test_invalid_output_type(self, db_session, class_with_lessons):
        config = {"llm": {"provider": "mock"}}
        result = generate_from_topics(
            session=db_session,
            class_id=class_with_lessons.id,
            topics=["photosynthesis"],
            output_type="invalid_type",
            config=config,
        )
        assert result is None

    def test_no_topics(self, db_session, class_with_lessons):
        config = {"llm": {"provider": "mock"}}
        result = generate_from_topics(
            session=db_session,
            class_id=class_with_lessons.id,
            topics=[],
            output_type="quiz",
            config=config,
        )
        assert result is None

    def test_custom_title(self, db_session, class_with_lessons):
        config = {"llm": {"provider": "mock"}}
        result = generate_from_topics(
            session=db_session,
            class_id=class_with_lessons.id,
            topics=["photosynthesis"],
            output_type="quiz",
            config=config,
            title="My Custom Quiz",
        )
        assert result is not None
        assert result.title == "My Custom Quiz"


class TestValidOutputTypes:
    def test_quiz_in_valid_types(self):
        assert "quiz" in VALID_OUTPUT_TYPES

    def test_flashcard_in_valid_types(self):
        assert "flashcard" in VALID_OUTPUT_TYPES

    def test_study_guide_in_valid_types(self):
        assert "study_guide" in VALID_OUTPUT_TYPES

    def test_vocabulary_in_valid_types(self):
        assert "vocabulary" in VALID_OUTPUT_TYPES

    def test_review_sheet_in_valid_types(self):
        assert "review_sheet" in VALID_OUTPUT_TYPES


class TestWebIntegration:
    """Test the web routes for topic generation."""

    @pytest.fixture
    def app(self, db_session, class_with_lessons):
        """Create a Flask test app."""
        db_fd = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = db_fd.name
        db_fd.close()

        from src.database import Class, get_engine, get_session, init_db

        engine = get_engine(db_path)
        init_db(engine)
        session = get_session(engine)
        cls = Class(
            name="7th Grade Science",
            grade_level="7th Grade",
            subject="Science",
            standards=json.dumps(["SOL 7.1E"]),
            config=json.dumps({}),
        )
        session.add(cls)
        session.commit()
        log_lesson(session, cls.id, "Photosynthesis lesson", topics=["photosynthesis"])
        session.close()
        engine.dispose()

        config = {
            "llm": {"provider": "mock"},
            "active_class_id": 1,
            "paths": {"database_file": db_path},
        }

        from src.web.app import create_app

        app = create_app(config)
        app.config["TESTING"] = True
        app.config["DB_PATH"] = db_path

        yield app

        app.config["DB_ENGINE"].dispose()
        try:
            os.unlink(db_path)
        except OSError:
            pass

    @pytest.fixture
    def client(self, app):
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "test"
            sess["display_name"] = "Test"
        return client

    def test_generate_topics_page_loads(self, client):
        resp = client.get("/generate/topics")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Generate from Topics" in html
        assert "output_type" in html

    def test_api_topics_search(self, client):
        resp = client.get("/api/topics/search?class_id=1&q=photo")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "topics" in data
        assert "photosynthesis" in data["topics"]

    def test_api_topics_search_no_class(self, client):
        resp = client.get("/api/topics/search?q=photo")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["topics"] == []

    def test_generate_topics_requires_login(self, app):
        client = app.test_client()
        resp = client.get("/generate/topics")
        assert resp.status_code == 303

    def test_dashboard_has_topic_link(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "/generate/topics" in html
        assert "Generate from Topics" in html
