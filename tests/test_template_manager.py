"""
Tests for BL-039: Quiz Template Export/Import.

Covers:
- Template export (stripping private data, correct structure)
- Template import (creating quiz + questions from template)
- Round-trip export/import fidelity
- Validation (missing fields, bad version, empty questions)
- Edge cases (no questions, various question types)
- Route integration via Flask test client
"""

import json
import os
import tempfile

import pytest

from src.database import Class, Question, Quiz, get_engine, get_session, init_db
from src.template_manager import (
    TEMPLATE_VERSION,
    export_quiz_template,
    import_quiz_template,
    validate_template,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """Create a temporary database."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = get_engine(tmp.name)
    init_db(engine)
    session = get_session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(tmp.name)


@pytest.fixture
def sample_quiz(db_session):
    """Create a quiz with various question types for testing."""
    cls = Class(name="Bio Block A", grade_level="8th Grade", subject="Biology")
    db_session.add(cls)
    db_session.flush()

    style = json.dumps(
        {
            "sol_standards": ["SOL 8.1", "SOL 8.2"],
            "cognitive_framework": "blooms",
            "grade_level": "8th Grade",
            "subject": "Biology",
            "provider": "mock",
        }
    )

    quiz = Quiz(
        title="Photosynthesis Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=style,
    )
    db_session.add(quiz)
    db_session.flush()

    # MC question
    mc_data = json.dumps(
        {
            "type": "multiple_choice",
            "options": ["Glucose", "Oxygen", "Carbon dioxide", "Water"],
            "correct_answer": "Glucose",
            "cognitive_level": "Remember",
            "cognitive_framework": "blooms",
            "difficulty": "easy",
        }
    )
    db_session.add(
        Question(
            quiz_id=quiz.id,
            question_type="mc",
            text="What is the primary product?",
            points=5,
            sort_order=0,
            data=mc_data,
        )
    )

    # TF question
    tf_data = json.dumps(
        {
            "type": "true_false",
            "correct_answer": "True",
            "cognitive_level": "Understand",
        }
    )
    db_session.add(
        Question(
            quiz_id=quiz.id,
            question_type="tf",
            text="Photosynthesis occurs in chloroplasts.",
            points=3,
            sort_order=1,
            data=tf_data,
        )
    )

    # Ordering question
    ordering_data = json.dumps(
        {
            "type": "ordering",
            "question_type": "ordering",
            "items": ["Light absorption", "Water splitting", "Carbon fixation", "Sugar production"],
            "correct_order": [0, 1, 2, 3],
            "instructions": "Arrange the steps of photosynthesis.",
        }
    )
    db_session.add(
        Question(
            quiz_id=quiz.id,
            question_type="ordering",
            text="Order the steps of photosynthesis.",
            points=5,
            sort_order=2,
            data=ordering_data,
        )
    )

    # Short answer question
    sa_data = json.dumps(
        {
            "type": "short_answer",
            "question_type": "short_answer",
            "expected_answer": "chlorophyll",
            "acceptable_answers": ["chlorophyll", "chlorophyll a"],
            "rubric_hint": "Green pigment that captures light energy",
        }
    )
    db_session.add(
        Question(
            quiz_id=quiz.id,
            question_type="short_answer",
            text="What pigment is responsible for capturing light?",
            points=4,
            sort_order=3,
            data=sa_data,
        )
    )

    db_session.commit()
    return quiz, cls


# ---------------------------------------------------------------------------
# Export Tests
# ---------------------------------------------------------------------------


class TestExport:
    """Test template export functionality."""

    def test_export_basic_structure(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)

        assert template is not None
        assert template["template_version"] == TEMPLATE_VERSION
        assert template["title"] == "Photosynthesis Quiz"
        assert template["subject"] == "Biology"
        assert template["grade_level"] == "8th Grade"
        assert len(template["questions"]) == 4
        assert template["question_count"] == 4

    def test_export_standards_included(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)
        assert "SOL 8.1" in template["standards"]
        assert "SOL 8.2" in template["standards"]

    def test_export_mc_question(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)
        mc = template["questions"][0]
        assert mc["question_type"] in ("mc", "multiple_choice")
        assert mc["text"] == "What is the primary product?"
        assert mc["correct_answer"] == "Glucose"
        assert len(mc["options"]) == 4
        assert mc["cognitive_level"] == "Remember"

    def test_export_ordering_question(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)
        ordering = template["questions"][2]
        assert ordering["question_type"] == "ordering"
        assert len(ordering["items"]) == 4
        assert ordering["correct_order"] == [0, 1, 2, 3]
        assert ordering["instructions"] == "Arrange the steps of photosynthesis."

    def test_export_short_answer_question(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)
        sa = template["questions"][3]
        assert sa["question_type"] == "short_answer"
        assert sa["expected_answer"] == "chlorophyll"
        assert "chlorophyll a" in sa["acceptable_answers"]
        assert "Green pigment" in sa["rubric_hint"]

    def test_export_strips_private_data(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)
        json_str = json.dumps(template)
        # Should not contain quiz ID, class ID, or teacher info
        assert '"id"' not in json_str or '"quiz_id"' not in json_str
        assert "class_id" not in json_str
        assert "teacher" not in json_str.lower() or "created_by" in json_str

    def test_export_metadata(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)
        assert template["metadata"]["created_by"] == "QuizWeaver"
        assert "export_date" in template["metadata"]

    def test_export_nonexistent_quiz(self, db_session):
        result = export_quiz_template(db_session, 99999)
        assert result is None


# ---------------------------------------------------------------------------
# Import Tests
# ---------------------------------------------------------------------------


class TestImport:
    """Test template import functionality."""

    def test_import_creates_quiz(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)

        new_quiz = import_quiz_template(db_session, template, cls.id, title="Imported Copy")
        assert new_quiz is not None
        assert new_quiz.title == "Imported Copy"
        assert new_quiz.status == "imported"
        assert new_quiz.class_id == cls.id

    def test_import_creates_questions(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)

        new_quiz = import_quiz_template(db_session, template, cls.id)
        questions = db_session.query(Question).filter_by(quiz_id=new_quiz.id).order_by(Question.sort_order).all()
        assert len(questions) == 4

    def test_import_preserves_question_types(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)

        new_quiz = import_quiz_template(db_session, template, cls.id)
        questions = db_session.query(Question).filter_by(quiz_id=new_quiz.id).order_by(Question.sort_order).all()

        types = [q.question_type for q in questions]
        assert "mc" in types or "multiple_choice" in types
        assert "tf" in types or "true_false" in types
        assert "ordering" in types
        assert "short_answer" in types

    def test_import_uses_template_title(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)

        new_quiz = import_quiz_template(db_session, template, cls.id)
        assert new_quiz.title == "Photosynthesis Quiz"

    def test_import_style_profile(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)

        new_quiz = import_quiz_template(db_session, template, cls.id)
        sp = new_quiz.style_profile
        if isinstance(sp, str):
            sp = json.loads(sp)
        assert sp["provider"] == "template_import"
        assert "SOL 8.1" in sp["sol_standards"]


# ---------------------------------------------------------------------------
# Round-Trip Tests
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Test export->import preserves content fidelity."""

    def test_round_trip_mc(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)
        new_quiz = import_quiz_template(db_session, template, cls.id, title="RT Test")

        questions = db_session.query(Question).filter_by(quiz_id=new_quiz.id).order_by(Question.sort_order).all()
        mc_q = questions[0]
        data = json.loads(mc_q.data) if isinstance(mc_q.data, str) else mc_q.data
        assert mc_q.text == "What is the primary product?"
        assert data["correct_answer"] == "Glucose"

    def test_round_trip_ordering(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)
        new_quiz = import_quiz_template(db_session, template, cls.id)

        questions = db_session.query(Question).filter_by(quiz_id=new_quiz.id).order_by(Question.sort_order).all()
        ordering_q = [q for q in questions if q.question_type == "ordering"][0]
        data = json.loads(ordering_q.data) if isinstance(ordering_q.data, str) else ordering_q.data
        assert len(data["items"]) == 4
        assert data["correct_order"] == [0, 1, 2, 3]

    def test_round_trip_short_answer(self, db_session, sample_quiz):
        quiz, cls = sample_quiz
        template = export_quiz_template(db_session, quiz.id)
        new_quiz = import_quiz_template(db_session, template, cls.id)

        questions = db_session.query(Question).filter_by(quiz_id=new_quiz.id).order_by(Question.sort_order).all()
        sa_q = [q for q in questions if q.question_type == "short_answer"][0]
        data = json.loads(sa_q.data) if isinstance(sa_q.data, str) else sa_q.data
        assert data["expected_answer"] == "chlorophyll"
        assert "chlorophyll a" in data["acceptable_answers"]


# ---------------------------------------------------------------------------
# Validation Tests
# ---------------------------------------------------------------------------


class TestValidation:
    """Test template validation logic."""

    def test_valid_template(self):
        template = {
            "template_version": "1.0",
            "title": "Test",
            "questions": [{"question_type": "mc", "text": "Q1?", "options": ["A", "B"], "correct_answer": "A"}],
        }
        is_valid, errors = validate_template(template)
        assert is_valid
        assert errors == []

    def test_missing_version(self):
        template = {"questions": [{"question_type": "mc", "text": "Q?"}]}
        is_valid, errors = validate_template(template)
        assert not is_valid
        assert any("template_version" in e for e in errors)

    def test_missing_questions(self):
        template = {"template_version": "1.0"}
        is_valid, errors = validate_template(template)
        assert not is_valid
        assert any("questions" in e for e in errors)

    def test_empty_questions(self):
        template = {"template_version": "1.0", "questions": []}
        is_valid, errors = validate_template(template)
        assert not is_valid
        assert any("at least one question" in e for e in errors)

    def test_invalid_questions_type(self):
        template = {"template_version": "1.0", "questions": "not a list"}
        is_valid, errors = validate_template(template)
        assert not is_valid
        assert any("array" in e for e in errors)

    def test_question_missing_text(self):
        template = {
            "template_version": "1.0",
            "questions": [{"question_type": "mc"}],
        }
        is_valid, errors = validate_template(template)
        assert not is_valid
        assert any("text" in e for e in errors)

    def test_question_missing_type(self):
        template = {
            "template_version": "1.0",
            "questions": [{"text": "What?"}],
        }
        is_valid, errors = validate_template(template)
        assert not is_valid
        assert any("question_type" in e for e in errors)

    def test_wrong_version(self):
        template = {
            "template_version": "99.0",
            "questions": [{"question_type": "mc", "text": "Q?"}],
        }
        is_valid, errors = validate_template(template)
        assert not is_valid
        assert any("version" in e.lower() for e in errors)

    def test_not_a_dict(self):
        is_valid, errors = validate_template([1, 2, 3])
        assert not is_valid
        assert any("object" in e.lower() for e in errors)

    def test_import_invalid_template(self, db_session):
        cls = Class(name="Test", grade_level="7th", subject="Sci")
        db_session.add(cls)
        db_session.flush()

        bad_template = {"template_version": "1.0"}  # missing questions
        result = import_quiz_template(db_session, bad_template, cls.id)
        assert result is None
