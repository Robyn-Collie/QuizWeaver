"""
Tests for QuizWeaver lesson plan generator.

Covers generation with mock provider, all sections present, error handling,
and various input combinations.
"""

import json
import os
import tempfile

import pytest

from src.database import (
    Base, Class, LessonPlan,
    get_engine, get_session,
)
from src.lesson_plan_generator import (
    generate_lesson_plan,
    LESSON_PLAN_SECTIONS,
    SECTION_LABELS,
    _build_prompt,
    _parse_plan,
)


@pytest.fixture
def db_session():
    """Create a temporary database with test data."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed a class
    cls = Class(
        name="Test Science",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    yield session, cls.id

    session.close()
    engine.dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def config():
    """Test config using mock provider."""
    return {
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "7th Grade Science"},
    }


# --- Constants ---

class TestConstants:
    def test_section_keys_defined(self):
        assert len(LESSON_PLAN_SECTIONS) == 10

    def test_section_labels_match_keys(self):
        for key in LESSON_PLAN_SECTIONS:
            assert key in SECTION_LABELS


# --- Prompt building ---

class TestBuildPrompt:
    def test_prompt_includes_class_name(self, db_session):
        session, class_id = db_session
        from src.classroom import get_class
        class_obj = get_class(session, class_id)
        prompt = _build_prompt(class_obj, ["Photosynthesis"], ["SOL 7.1"], 50, None)
        assert "Test Science" in prompt

    def test_prompt_includes_topics(self, db_session):
        session, class_id = db_session
        from src.classroom import get_class
        class_obj = get_class(session, class_id)
        prompt = _build_prompt(class_obj, ["Photosynthesis", "Respiration"], [], 50, None)
        assert "Photosynthesis" in prompt
        assert "Respiration" in prompt

    def test_prompt_includes_duration(self, db_session):
        session, class_id = db_session
        from src.classroom import get_class
        class_obj = get_class(session, class_id)
        prompt = _build_prompt(class_obj, [], [], 90, None)
        assert "90 minutes" in prompt

    def test_prompt_includes_grade_level_override(self, db_session):
        session, class_id = db_session
        from src.classroom import get_class
        class_obj = get_class(session, class_id)
        prompt = _build_prompt(class_obj, [], [], 50, "8th Grade")
        assert "8th Grade" in prompt


# --- Parse plan ---

class TestParsePlan:
    def test_parse_valid_json(self):
        data = json.dumps({"title": "Test", "warm_up": "Activity"})
        result = _parse_plan(data)
        assert result["title"] == "Test"
        assert result["warm_up"] == "Activity"

    def test_parse_json_embedded_in_text(self):
        text = 'Here is the plan:\n{"title": "Test"}\nDone.'
        result = _parse_plan(text)
        assert result is not None
        assert result["title"] == "Test"

    def test_parse_invalid_returns_none(self):
        result = _parse_plan("This is not JSON at all")
        assert result is None


# --- Generation ---

class TestGenerateLessonPlan:
    def test_generate_basic(self, db_session, config):
        session, class_id = db_session
        plan = generate_lesson_plan(
            session, class_id, config,
            topics=["Photosynthesis"],
        )
        assert plan is not None
        assert plan.status == "draft"
        assert plan.class_id == class_id

    def test_generate_has_title(self, db_session, config):
        session, class_id = db_session
        plan = generate_lesson_plan(session, class_id, config, topics=["Ecosystems"])
        assert plan is not None
        assert plan.title
        assert plan.title != "Generating..."

    def test_generate_has_all_sections(self, db_session, config):
        session, class_id = db_session
        plan = generate_lesson_plan(session, class_id, config, topics=["Cell Division"])
        assert plan is not None
        plan_data = json.loads(plan.plan_data)
        for section_key in LESSON_PLAN_SECTIONS:
            assert section_key in plan_data, f"Missing section: {section_key}"
            assert plan_data[section_key], f"Empty section: {section_key}"

    def test_generate_with_standards(self, db_session, config):
        session, class_id = db_session
        plan = generate_lesson_plan(
            session, class_id, config,
            topics=["Genetics"],
            standards=["SOL 7.1", "SOL 7.2"],
        )
        assert plan is not None
        standards = json.loads(plan.standards)
        assert "SOL 7.1" in standards

    def test_generate_with_duration(self, db_session, config):
        session, class_id = db_session
        plan = generate_lesson_plan(
            session, class_id, config,
            topics=["Energy"],
            duration_minutes=90,
        )
        assert plan is not None
        assert plan.duration_minutes == 90

    def test_generate_with_grade_level(self, db_session, config):
        session, class_id = db_session
        plan = generate_lesson_plan(
            session, class_id, config,
            topics=["Forces"],
            grade_level="8th Grade",
        )
        assert plan is not None
        assert plan.grade_level == "8th Grade"

    def test_generate_invalid_class(self, db_session, config):
        session, _ = db_session
        plan = generate_lesson_plan(session, 9999, config, topics=["Nothing"])
        assert plan is None

    def test_generate_no_topics(self, db_session, config):
        session, class_id = db_session
        plan = generate_lesson_plan(session, class_id, config)
        assert plan is not None
        assert plan.status == "draft"

    def test_generate_stores_topics_json(self, db_session, config):
        session, class_id = db_session
        plan = generate_lesson_plan(
            session, class_id, config,
            topics=["Mitosis", "Meiosis"],
        )
        assert plan is not None
        topics = json.loads(plan.topics)
        assert "Mitosis" in topics
        assert "Meiosis" in topics

    def test_generate_with_provider_override(self, db_session, config):
        session, class_id = db_session
        plan = generate_lesson_plan(
            session, class_id, config,
            topics=["Respiration"],
            provider_name="mock",
        )
        assert plan is not None
        assert plan.status == "draft"
