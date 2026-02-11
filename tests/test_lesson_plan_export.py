"""
Tests for QuizWeaver lesson plan export (PDF and DOCX).

Covers both export formats with various plan data configurations.
"""

import io
import json
import os
import tempfile

import pytest

from src.database import (
    Base, Class, LessonPlan,
    get_engine, get_session,
)
from src.lesson_plan_export import (
    export_lesson_plan_pdf,
    export_lesson_plan_docx,
    SECTION_LABELS,
    SECTION_ORDER,
    _parse_plan_data,
    _sanitize_filename,
)


@pytest.fixture
def db_session():
    """Create a temporary database with a lesson plan."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Block A",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    plan_data = {
        "learning_objectives": "Students will define photosynthesis and explain its stages.",
        "materials_needed": "Textbook, whiteboard, diagram handout, colored pencils.",
        "warm_up": "Show a photo of a plant and ask students to list 3 observations.",
        "direct_instruction": "Mini-lecture on photosynthesis with diagram walkthrough.",
        "guided_practice": "Pair work: label the photosynthesis diagram together.",
        "independent_practice": "Answer 5 short-response questions in notebooks.",
        "assessment": "Exit ticket with 2 questions on photosynthesis.",
        "closure": "Review objectives and preview tomorrow's lab.",
        "differentiation": "Below grade: word bank. Advanced: critical thinking question.",
        "standards_alignment": "Addresses SOL 7.1 and SOL 7.2.",
    }

    plan = LessonPlan(
        class_id=cls.id,
        title="Photosynthesis Deep Dive",
        topics=json.dumps(["Photosynthesis"]),
        standards=json.dumps(["SOL 7.1"]),
        grade_level="7th Grade",
        duration_minutes=50,
        plan_data=json.dumps(plan_data),
        status="draft",
    )
    session.add(plan)
    session.commit()

    yield session, plan

    session.close()
    engine.dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


# --- Helpers ---

class TestHelpers:
    def test_parse_plan_data_json_string(self, db_session):
        _, plan = db_session
        data = _parse_plan_data(plan)
        assert "learning_objectives" in data
        assert "warm_up" in data

    def test_parse_plan_data_invalid(self):
        class FakePlan:
            plan_data = "not json"
        data = _parse_plan_data(FakePlan())
        assert data == {}

    def test_sanitize_filename_normal(self):
        assert _sanitize_filename("My Lesson Plan!") == "My_Lesson_Plan"

    def test_sanitize_filename_empty(self):
        assert _sanitize_filename("") == "lesson_plan"

    def test_section_order_matches_labels(self):
        for key in SECTION_ORDER:
            assert key in SECTION_LABELS


# --- PDF Export ---

class TestPdfExport:
    def test_pdf_returns_bytesio(self, db_session):
        _, plan = db_session
        buf = export_lesson_plan_pdf(plan)
        assert isinstance(buf, io.BytesIO)

    def test_pdf_has_content(self, db_session):
        _, plan = db_session
        buf = export_lesson_plan_pdf(plan)
        content = buf.read()
        assert len(content) > 100
        assert content[:5] == b"%PDF-"

    def test_pdf_with_empty_plan(self, db_session):
        session, plan = db_session
        plan.plan_data = json.dumps({})
        session.commit()
        buf = export_lesson_plan_pdf(plan)
        assert isinstance(buf, io.BytesIO)
        assert len(buf.read()) > 50


# --- DOCX Export ---

class TestDocxExport:
    def test_docx_returns_bytesio(self, db_session):
        _, plan = db_session
        buf = export_lesson_plan_docx(plan)
        assert isinstance(buf, io.BytesIO)

    def test_docx_has_content(self, db_session):
        _, plan = db_session
        buf = export_lesson_plan_docx(plan)
        content = buf.read()
        assert len(content) > 100
        # DOCX files start with PK (zip format)
        assert content[:2] == b"PK"

    def test_docx_with_empty_plan(self, db_session):
        session, plan = db_session
        plan.plan_data = json.dumps({})
        session.commit()
        buf = export_lesson_plan_docx(plan)
        assert isinstance(buf, io.BytesIO)
        assert len(buf.read()) > 50
