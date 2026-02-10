"""
Tests for QuizWeaver rubric export module.

Covers PDF, DOCX, and CSV export formats.
"""

import json
import os
import tempfile

import pytest

from src.database import (
    Base, Class, Quiz, Rubric, RubricCriterion,
    get_engine, get_session,
)
from src.rubric_export import export_rubric_csv, export_rubric_docx, export_rubric_pdf


@pytest.fixture
def db_session():
    """Create a temporary database with rubric test data."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed
    cls = Class(
        name="Test Science",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    quiz = Quiz(
        title="Photosynthesis Quiz",
        class_id=cls.id,
        status="generated",
    )
    session.add(quiz)
    session.commit()

    rubric = Rubric(
        quiz_id=quiz.id,
        title="Test Rubric",
        status="generated",
        config=json.dumps({"provider": "mock"}),
    )
    session.add(rubric)
    session.commit()

    levels_json = json.dumps([
        {"level": 1, "label": "Beginning", "description": "Minimal understanding"},
        {"level": 2, "label": "Developing", "description": "Partial understanding"},
        {"level": 3, "label": "Proficient", "description": "Solid understanding"},
        {"level": 4, "label": "Advanced", "description": "Deep understanding"},
    ])

    c1 = RubricCriterion(
        rubric_id=rubric.id,
        sort_order=0,
        criterion="Content Knowledge",
        description="Demonstrates understanding of key concepts",
        max_points=10,
        levels=levels_json,
    )
    c2 = RubricCriterion(
        rubric_id=rubric.id,
        sort_order=1,
        criterion="Scientific Vocabulary",
        description="Uses appropriate scientific terms",
        max_points=5,
        levels=levels_json,
    )
    c3 = RubricCriterion(
        rubric_id=rubric.id,
        sort_order=2,
        criterion="Critical Thinking",
        description="Applies analysis and reasoning",
        max_points=10,
        levels=levels_json,
    )
    session.add_all([c1, c2, c3])
    session.commit()

    criteria = (
        session.query(RubricCriterion)
        .filter_by(rubric_id=rubric.id)
        .order_by(RubricCriterion.sort_order)
        .all()
    )

    yield rubric, criteria

    session.close()
    engine.dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


class TestRubricCSVExport:
    def test_csv_has_header(self, db_session):
        rubric, criteria = db_session
        csv_str = export_rubric_csv(rubric, criteria)
        assert "Criterion" in csv_str
        assert "Description" in csv_str
        assert "Max Points" in csv_str

    def test_csv_has_proficiency_columns(self, db_session):
        rubric, criteria = db_session
        csv_str = export_rubric_csv(rubric, criteria)
        assert "Beginning" in csv_str
        assert "Developing" in csv_str
        assert "Proficient" in csv_str
        assert "Advanced" in csv_str

    def test_csv_has_criteria_rows(self, db_session):
        rubric, criteria = db_session
        csv_str = export_rubric_csv(rubric, criteria)
        assert "Content Knowledge" in csv_str
        assert "Scientific Vocabulary" in csv_str
        assert "Critical Thinking" in csv_str


class TestRubricDOCXExport:
    def test_docx_produces_bytes(self, db_session):
        rubric, criteria = db_session
        buf = export_rubric_docx(rubric, criteria)
        data = buf.read()
        assert len(data) > 0

    def test_docx_is_valid_zip(self, db_session):
        rubric, criteria = db_session
        buf = export_rubric_docx(rubric, criteria)
        data = buf.read()
        assert data[:2] == b"PK"  # ZIP magic bytes


class TestRubricPDFExport:
    def test_pdf_produces_bytes(self, db_session):
        rubric, criteria = db_session
        buf = export_rubric_pdf(rubric, criteria)
        data = buf.read()
        assert len(data) > 0

    def test_pdf_starts_with_header(self, db_session):
        rubric, criteria = db_session
        buf = export_rubric_pdf(rubric, criteria)
        data = buf.read()
        assert data[:5] == b"%PDF-"

    def test_empty_criteria_produces_pdf(self, db_session):
        rubric, _ = db_session
        buf = export_rubric_pdf(rubric, [])
        data = buf.read()
        assert len(data) > 0
        assert data[:5] == b"%PDF-"
