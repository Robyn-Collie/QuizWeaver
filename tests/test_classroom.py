"""
Comprehensive tests for the multi-class management module (src/classroom.py).

Tests cover:
  - Creating classes with all fields
  - Creating multiple classes with unique IDs
  - Getting a class by ID
  - Getting a nonexistent class (returns None)
  - Listing classes (basic)
  - Listing classes with lesson and quiz counts
  - Context isolation between classes
  - Setting the active class via config.yaml
  - Getting the active class from config

Run with: python -m pytest tests/test_classroom.py -v
"""

import json
import os
import sys
import tempfile

import pytest
import yaml

# Ensure project root is on sys.path so imports work when running standalone.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import (
    Base,
    Class,
    LessonLog,
    Quiz,
    get_engine,
    get_session,
    init_db,
)
from src.classroom import (
    create_class,
    get_active_class,
    get_class,
    list_classes,
    set_active_class,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db():
    """
    Provide a temporary SQLite database with all tables created.

    Yields a (engine, session) tuple.  After the test the session and engine
    are closed, and the temporary file is removed.  ``engine.dispose()`` is
    called before deletion to avoid Windows file-locking errors.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()  # Close handle immediately so SQLAlchemy can use the file

    engine = get_engine(tmp_path)
    init_db(engine)
    session = get_session(engine)

    yield engine, session

    # Teardown ---------------------------------------------------------------
    session.close()
    engine.dispose()
    try:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except OSError:
        pass  # Windows may still hold a lock; ignore cleanup errors


@pytest.fixture()
def tmp_config():
    """
    Provide a temporary config.yaml file with minimal content.

    Yields the file path.  The file is removed after the test.
    """
    tmp = tempfile.NamedTemporaryFile(
        suffix=".yaml", delete=False, mode="w", encoding="utf-8"
    )
    yaml.dump({"llm": {"provider": "mock"}, "paths": {}}, tmp, default_flow_style=False)
    tmp.close()

    yield tmp.name

    try:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_create_class(db):
    """Create a class with all fields and verify they are stored correctly."""
    _engine, session = db

    cls = create_class(
        session,
        name="7th Grade Science - Block A",
        grade_level="7th Grade",
        subject="Science",
        standards=["SOL 7.1", "SOL 7.2"],
    )

    assert cls.id is not None, "Class should have an auto-generated ID"
    assert cls.name == "7th Grade Science - Block A"
    assert cls.grade_level == "7th Grade"
    assert cls.subject == "Science"

    # standards is stored as a JSON string
    stored_standards = json.loads(cls.standards)
    assert stored_standards == ["SOL 7.1", "SOL 7.2"]

    # config defaults to an empty JSON object
    stored_config = json.loads(cls.config)
    assert stored_config == {}

    # created_at should be populated
    assert cls.created_at is not None


def test_create_multiple_classes(db):
    """Create two classes and verify they receive unique IDs."""
    _engine, session = db

    cls_a = create_class(session, name="Block A", grade_level="7th Grade", subject="Science")
    cls_b = create_class(session, name="Block B", grade_level="8th Grade", subject="Math")

    assert cls_a.id != cls_b.id, "Each class should have a unique ID"
    assert cls_a.name == "Block A"
    assert cls_b.name == "Block B"

    # Both should be retrievable
    all_classes = session.query(Class).all()
    assert len(all_classes) == 2


def test_get_class(db):
    """Create a class, then retrieve it by ID and verify fields match."""
    _engine, session = db

    created = create_class(
        session,
        name="Algebra 1 - Period 3",
        grade_level="9th Grade",
        subject="Math",
        standards=["A.1", "A.2"],
    )

    fetched = get_class(session, created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == created.name
    assert fetched.grade_level == created.grade_level
    assert fetched.subject == created.subject
    assert fetched.standards == created.standards


def test_get_class_not_found(db):
    """Requesting a nonexistent class ID returns None."""
    _engine, session = db

    result = get_class(session, 9999)
    assert result is None


def test_list_classes(db):
    """list_classes returns all created classes with correct basic info."""
    _engine, session = db

    create_class(session, name="Class X", grade_level="6th Grade", subject="ELA")
    create_class(session, name="Class Y", grade_level="7th Grade", subject="Science")

    result = list_classes(session)

    assert len(result) == 2
    names = [c["name"] for c in result]
    assert "Class X" in names
    assert "Class Y" in names

    # Each entry should contain the expected keys
    for entry in result:
        assert "id" in entry
        assert "name" in entry
        assert "grade_level" in entry
        assert "subject" in entry
        assert "standards" in entry
        assert "lesson_count" in entry
        assert "quiz_count" in entry
        assert "created_at" in entry


def test_list_classes_with_counts(db):
    """Verify lesson_count and quiz_count are accurate per class."""
    _engine, session = db

    cls = create_class(session, name="Active Class", grade_level="8th Grade", subject="History")

    # Add two lesson logs to this class
    session.add(LessonLog(class_id=cls.id, content="Lesson 1 - Civil War", topics=json.dumps(["civil war"])))
    session.add(LessonLog(class_id=cls.id, content="Lesson 2 - Reconstruction", topics=json.dumps(["reconstruction"])))
    session.commit()

    # Add one quiz to this class
    session.add(Quiz(title="Civil War Quiz", class_id=cls.id, status="generated"))
    session.commit()

    # Also create an empty class with no lessons or quizzes
    create_class(session, name="Empty Class")

    result = list_classes(session)
    assert len(result) == 2

    # Find the class entries by name
    active_entry = next(c for c in result if c["name"] == "Active Class")
    empty_entry = next(c for c in result if c["name"] == "Empty Class")

    assert active_entry["lesson_count"] == 2
    assert active_entry["quiz_count"] == 1

    assert empty_entry["lesson_count"] == 0
    assert empty_entry["quiz_count"] == 0


def test_class_context_isolation(db):
    """Lessons added to Class A must not appear in Class B."""
    _engine, session = db

    cls_a = create_class(session, name="Class A")
    cls_b = create_class(session, name="Class B")

    # Add a lesson log only to Class A
    session.add(
        LessonLog(
            class_id=cls_a.id,
            content="Photosynthesis overview",
            topics=json.dumps(["photosynthesis"]),
        )
    )
    session.commit()

    # Query lesson logs for each class directly
    logs_a = session.query(LessonLog).filter_by(class_id=cls_a.id).all()
    logs_b = session.query(LessonLog).filter_by(class_id=cls_b.id).all()

    assert len(logs_a) == 1, "Class A should have exactly one lesson log"
    assert len(logs_b) == 0, "Class B should have zero lesson logs"

    # Also verify via list_classes counts
    result = list_classes(session)
    entry_a = next(c for c in result if c["name"] == "Class A")
    entry_b = next(c for c in result if c["name"] == "Class B")

    assert entry_a["lesson_count"] == 1
    assert entry_b["lesson_count"] == 0


def test_set_active_class(tmp_config):
    """set_active_class writes the active_class_id into the config file."""
    success = set_active_class(tmp_config, class_id=42)
    assert success is True

    # Read back the config and verify
    with open(tmp_config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert config["active_class_id"] == 42


def test_get_active_class(db):
    """get_active_class returns the correct Class when active_class_id is set."""
    _engine, session = db

    cls = create_class(session, name="My Active Class", grade_level="7th Grade", subject="Science")

    # Simulate a config dict with active_class_id at the top level
    config = {"active_class_id": cls.id}

    active = get_active_class(session, config)

    assert active is not None
    assert active.id == cls.id
    assert active.name == "My Active Class"


def test_get_active_class_from_llm_section(db):
    """get_active_class also checks under config['llm']['active_class_id']."""
    _engine, session = db

    cls = create_class(session, name="LLM Config Class")

    config = {"llm": {"active_class_id": cls.id}}

    active = get_active_class(session, config)
    assert active is not None
    assert active.id == cls.id


def test_get_active_class_not_configured(db):
    """get_active_class returns None when no active_class_id is in config."""
    _engine, session = db

    config = {"llm": {"provider": "mock"}}

    active = get_active_class(session, config)
    assert active is None


def test_get_active_class_invalid_id(db):
    """get_active_class returns None when active_class_id refers to a missing class."""
    _engine, session = db

    config = {"active_class_id": 9999}

    active = get_active_class(session, config)
    assert active is None
