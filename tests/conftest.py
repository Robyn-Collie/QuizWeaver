"""
Shared pytest fixtures for QuizWeaver tests.

Provides commonly-used database, config, and Flask test client fixtures
so that individual test files do not need to duplicate boilerplate setup
and teardown logic.

Fixtures defined here are automatically available to all test files in
the tests/ directory (and subdirectories) without explicit import.

Fixture summary
---------------
Database:
    db_path              -- temp .db file path with cleanup
    db_session           -- (session, db_path) tuple with migrations
    db_engine_session    -- (engine, session, db_path) tuple

Config:
    mock_config          -- standard config dict using MockLLMProvider

LLM:
    mock_provider        -- a MockLLMProvider() instance

Data builders:
    sample_class         -- factory that inserts a Class into a session
    sample_quiz_with_questions -- factory that inserts Class + Quiz + Questions
    mc_question_data     -- dict for a typical multiple-choice question

Flask:
    flask_app            -- Flask app seeded with class + quiz + question
    flask_client         -- logged-in test client (session-injected)
    anon_flask_client    -- unauthenticated test client
    make_flask_app       -- factory fixture for custom-seeded Flask apps
"""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session, init_db
from src.migrations import run_migrations

# ---------------------------------------------------------------------------
# Core database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path():
    """Provide a temporary database file path with cleanup.

    Yields the file path as a string.  The file is removed after the
    test completes.  ``engine.dispose()`` should be called by the
    consumer before this fixture tears down, but cleanup is wrapped in
    try/except for Windows file-locking safety.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    yield tmp.name
    try:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
    except OSError:
        pass  # Windows may still hold the lock


@pytest.fixture
def db_session(db_path):
    """Provide a fully-initialized SQLAlchemy session bound to a temp DB.

    Runs migrations, creates all ORM tables, and yields a
    ``(session, db_path)`` tuple.  Many tests expect this tuple so
    they can build config dicts that reference the database file.

    Cleanup: session.close(), engine.dispose(), file removal handled
    by the ``db_path`` fixture.
    """
    run_migrations(db_path, verbose=False)
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)
    yield session, db_path
    session.close()
    engine.dispose()


@pytest.fixture
def db_engine_session(db_path):
    """Provide engine AND session for tests that need engine access.

    Yields an ``(engine, session, db_path)`` tuple.

    Cleanup: session and engine are closed; file removal handled by
    the ``db_path`` fixture.
    """
    run_migrations(db_path, verbose=False)
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)
    yield engine, session, db_path
    session.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config(db_session):
    """Provide a standard mock config dict for quiz generation.

    Depends on ``db_session`` so the database path is available.
    Returns a config dict suitable for ``generate_quiz()`` and other
    functions that accept a config parameter.
    """
    session, db_path_value = db_session
    return {
        "llm": {"provider": "mock"},
        "paths": {"database_file": db_path_value},
        "generation": {
            "quiz_title": "Test Quiz",
            "default_grade_level": "7th Grade Science",
            "sol_standards": [],
            "target_image_ratio": 0.0,
            "generate_ai_images": False,
            "interactive_review": False,
        },
    }


# ---------------------------------------------------------------------------
# LLM provider fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_provider():
    """Provide a MockLLMProvider instance (zero-cost, no API calls)."""
    from src.llm_provider import MockLLMProvider

    return MockLLMProvider()


# ---------------------------------------------------------------------------
# Data builder fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mc_question_data():
    """Return a standard multiple-choice question data dict.

    Suitable for passing to ``Question(data=json.dumps(mc_question_data))``.
    """
    return {
        "type": "mc",
        "text": "What is photosynthesis?",
        "options": [
            "The process by which plants convert sunlight to energy",
            "A type of cellular respiration",
            "The movement of water through soil",
            "A chemical reaction in animals",
        ],
        "correct_index": 0,
    }


@pytest.fixture
def sample_class():
    """Factory fixture: insert a Class record into a given session.

    Returns a callable ``create(session, **overrides)`` so the caller
    can customise fields.  Defaults produce a 7th-grade Science class.

    Usage::

        def test_example(db_session, sample_class):
            session, db_path = db_session
            cls = sample_class(session)
            assert cls.id is not None
    """

    def _create(session, **overrides):
        defaults = {
            "name": "Test Class",
            "grade_level": "7th Grade",
            "subject": "Science",
            "standards": json.dumps(["SOL 7.1"]),
            "config": json.dumps({}),
        }
        defaults.update(overrides)
        cls = Class(**defaults)
        session.add(cls)
        session.commit()
        return cls

    return _create


@pytest.fixture
def sample_quiz_with_questions(mc_question_data):
    """Factory fixture: insert a Class + Quiz + Questions into a session.

    Returns a callable ``create(session, num_questions=1, **quiz_overrides)``
    that returns ``(quiz, class_obj, questions)``.

    Usage::

        def test_example(db_session, sample_quiz_with_questions):
            session, db_path = db_session
            quiz, cls, questions = sample_quiz_with_questions(session)
            assert len(questions) == 1
    """

    def _create(session, num_questions=1, **quiz_overrides):
        cls = Class(
            name="Test Class",
            grade_level="7th Grade",
            subject="Science",
            standards=json.dumps(["SOL 7.1"]),
            config=json.dumps({}),
        )
        session.add(cls)
        session.commit()

        quiz_defaults = {
            "title": "Test Quiz",
            "class_id": cls.id,
            "status": "generated",
            "style_profile": json.dumps({"grade_level": "7th Grade", "provider": "mock"}),
        }
        quiz_defaults.update(quiz_overrides)
        quiz = Quiz(**quiz_defaults)
        session.add(quiz)
        session.commit()

        questions = []
        for i in range(num_questions):
            q = Question(
                quiz_id=quiz.id,
                question_type="mc",
                title=f"Q{i + 1}",
                text=mc_question_data["text"],
                points=5.0,
                data=json.dumps(mc_question_data),
            )
            session.add(q)
            questions.append(q)
        session.commit()

        return quiz, cls, questions

    return _create


# ---------------------------------------------------------------------------
# Flask test client fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def flask_app(db_path):
    """Provide a Flask test app with a temporary database.

    Creates a temp DB, seeds it with minimal test data (two classes,
    two lessons, one quiz with one question), and yields the app.

    The DB engine is disposed on teardown before file cleanup.
    """
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed a primary class with lessons and a quiz
    cls1 = Class(
        name="Test Class",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    cls2 = Class(
        name="Empty Class",
        grade_level="8th Grade",
        subject="Math",
        standards=json.dumps([]),
        config=json.dumps({}),
    )
    session.add(cls1)
    session.add(cls2)
    session.commit()

    quiz = Quiz(
        title="Test Quiz",
        class_id=cls1.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "7th Grade", "provider": "mock"}),
    )
    session.add(quiz)
    session.commit()

    q1 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q1",
        text="What is photosynthesis?",
        points=5.0,
        data=json.dumps(
            {
                "type": "mc",
                "options": ["A process", "A disease", "A planet", "A tool"],
                "correct_index": 0,
            }
        ),
    )
    session.add(q1)
    session.commit()

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {
            "default_grade_level": "7th Grade Science",
            "quiz_title": "Test Quiz",
            "sol_standards": [],
            "target_image_ratio": 0.0,
            "generate_ai_images": False,
            "interactive_review": False,
        },
    }
    app = create_app(test_config)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False  # Disable CSRF for non-security tests

    yield app

    app.config["DB_ENGINE"].dispose()


@pytest.fixture
def flask_client(flask_app):
    """Provide a logged-in Flask test client.

    Uses session injection to bypass the login flow.
    """
    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        yield client


@pytest.fixture
def anon_flask_client(flask_app):
    """Provide an unauthenticated Flask test client.

    Useful for testing login redirects and auth guards.
    """
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def make_flask_app(db_path):
    """Factory fixture: create a Flask app with custom seed data.

    Returns a callable ``create(seed_fn=None, extra_config=None)``
    where ``seed_fn(session)`` is an optional function that receives a
    fresh SQLAlchemy session for inserting custom test data.

    Usage::

        def test_custom(make_flask_app):
            def seed(session):
                session.add(Class(name="Custom", grade_level="8th Grade",
                                  subject="Math"))
                session.commit()
            app = make_flask_app(seed_fn=seed)
            with app.test_client() as c:
                ...

    The engine is disposed when the fixture tears down.
    """
    apps = []  # track for cleanup

    def _create(seed_fn=None, extra_config=None):
        from src.web.app import create_app

        engine = get_engine(db_path)
        Base.metadata.create_all(engine)

        if seed_fn is not None:
            session = get_session(engine)
            seed_fn(session)
            session.close()

        engine.dispose()

        test_config = {
            "paths": {"database_file": db_path},
            "llm": {"provider": "mock"},
            "generation": {
                "default_grade_level": "7th Grade Science",
                "quiz_title": "Test Quiz",
                "sol_standards": [],
                "target_image_ratio": 0.0,
                "generate_ai_images": False,
                "interactive_review": False,
            },
        }
        if extra_config:
            for key, value in extra_config.items():
                if isinstance(value, dict) and key in test_config:
                    test_config[key].update(value)
                else:
                    test_config[key] = value

        app = create_app(test_config)
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        apps.append(app)
        return app

    yield _create

    for app in apps:
        try:
            app.config["DB_ENGINE"].dispose()
        except Exception:
            pass
