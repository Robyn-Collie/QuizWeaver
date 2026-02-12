"""
Tests for BL-038: Additional Question Types (Ordering, Short Answer).

Covers:
- Mock responses generating ordering and short answer questions
- Export support (CSV, DOCX, GIFT, PDF) for new question types
- Normalization of ordering and short answer data
- Display data structures for quiz detail template
"""

import json
import os
import tempfile

import pytest

from src.database import Class, Question, Quiz, get_engine, get_session, init_db
from src.export import (
    _format_options_csv,
    _gift_ordering,
    _gift_short_answer,
    export_csv,
    export_docx,
    export_gift,
    export_pdf,
    normalize_question,
)
from src.mock_responses import get_generator_response

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """Create a temporary database with test data."""
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
def ordering_question(db_session):
    """Create a quiz with an ordering question."""
    cls = Class(name="Test Class", grade_level="7th Grade", subject="Science")
    db_session.add(cls)
    db_session.flush()

    quiz = Quiz(title="Test Quiz", class_id=cls.id, status="generated")
    db_session.add(quiz)
    db_session.flush()

    data = {
        "type": "ordering",
        "question_type": "ordering",
        "items": [
            "Identify the components",
            "Observe the process beginning",
            "Measure the output",
            "Record the results",
        ],
        "correct_order": [0, 1, 2, 3],
        "instructions": "Arrange the steps in the correct order.",
        "cognitive_level": "Apply",
        "cognitive_framework": "blooms",
    }
    question = Question(
        quiz_id=quiz.id,
        question_type="ordering",
        text="Arrange the steps of the experiment in the correct order.",
        points=5,
        sort_order=0,
        data=json.dumps(data),
    )
    db_session.add(question)
    db_session.commit()
    return quiz, question


@pytest.fixture
def short_answer_question(db_session):
    """Create a quiz with a short answer question."""
    cls = Class(name="Test Class", grade_level="7th Grade", subject="Science")
    db_session.add(cls)
    db_session.flush()

    quiz = Quiz(title="Test Quiz SA", class_id=cls.id, status="generated")
    db_session.add(quiz)
    db_session.flush()

    data = {
        "type": "short_answer",
        "question_type": "short_answer",
        "expected_answer": "photosynthesis",
        "acceptable_answers": ["photosynthesis", "the process of photosynthesis"],
        "rubric_hint": "Student should mention light energy converting to chemical energy",
    }
    question = Question(
        quiz_id=quiz.id,
        question_type="short_answer",
        text="What is the primary function of chloroplasts?",
        points=5,
        sort_order=0,
        data=json.dumps(data),
    )
    db_session.add(question)
    db_session.commit()
    return quiz, question


# ---------------------------------------------------------------------------
# Mock Response Tests
# ---------------------------------------------------------------------------


class TestMockResponses:
    """Test that mock responses include new question types."""

    def test_generator_includes_variety(self):
        """Mock generator should produce a mix of question types."""
        # Run multiple times to check variety
        all_types = set()
        for _ in range(20):
            resp = get_generator_response(["Generate quiz about photosynthesis"])
            questions = json.loads(resp)
            for q in questions:
                all_types.add(q.get("type"))

        # Should contain at least MC/TF and one of the new types
        assert "multiple_choice" in all_types
        assert "true_false" in all_types or "ordering" in all_types or "short_answer" in all_types

    def test_ordering_question_structure(self):
        """Mock ordering questions should have required fields."""
        # Keep generating until we get an ordering question
        found = False
        for _ in range(50):
            resp = get_generator_response(["Generate quiz about genetics"])
            questions = json.loads(resp)
            for q in questions:
                if q.get("type") == "ordering":
                    found = True
                    assert "items" in q
                    assert "correct_order" in q
                    assert "instructions" in q
                    assert isinstance(q["items"], list)
                    assert len(q["items"]) > 0
                    assert isinstance(q["correct_order"], list)
                    break
            if found:
                break
        assert found, "No ordering question generated in 50 attempts"

    def test_short_answer_question_structure(self):
        """Mock short answer questions should have required fields."""
        found = False
        for _ in range(50):
            resp = get_generator_response(["Generate quiz about ecosystems"])
            questions = json.loads(resp)
            for q in questions:
                if q.get("type") == "short_answer":
                    found = True
                    assert "expected_answer" in q
                    assert "acceptable_answers" in q
                    assert "rubric_hint" in q
                    assert isinstance(q["acceptable_answers"], list)
                    break
            if found:
                break
        assert found, "No short answer question generated in 50 attempts"


# ---------------------------------------------------------------------------
# Normalization Tests
# ---------------------------------------------------------------------------


class TestNormalization:
    """Test normalize_question handles new types correctly."""

    def test_normalize_ordering(self, ordering_question):
        quiz, question = ordering_question
        nq = normalize_question(question, 0)
        assert nq["type"] == "ordering"
        assert nq["number"] == 1
        assert len(nq["ordering_items"]) == 4
        assert nq["ordering_correct_order"] == [0, 1, 2, 3]
        assert nq["ordering_instructions"] == "Arrange the steps in the correct order."

    def test_normalize_short_answer(self, short_answer_question):
        quiz, question = short_answer_question
        nq = normalize_question(question, 0)
        assert nq["type"] == "short_answer"
        assert nq["expected_answer"] == "photosynthesis"
        assert "the process of photosynthesis" in nq["acceptable_answers"]
        assert "light energy" in nq["rubric_hint"]
        # correct_answer should be set from expected_answer
        assert nq["correct_answer"] == "photosynthesis"

    def test_normalize_ordering_preserves_cognitive(self, ordering_question):
        quiz, question = ordering_question
        nq = normalize_question(question, 0)
        assert nq["cognitive_level"] == "Apply"
        assert nq["cognitive_framework"] == "blooms"


# ---------------------------------------------------------------------------
# CSV Export Tests
# ---------------------------------------------------------------------------


class TestCSVExport:
    """Test CSV export for new question types."""

    def test_csv_ordering(self, ordering_question):
        quiz, question = ordering_question
        csv_str = export_csv(quiz, [question])
        assert "ordering" in csv_str.lower()
        # Items should be comma-separated in options column
        assert "Identify the components" in csv_str

    def test_csv_short_answer(self, short_answer_question):
        quiz, question = short_answer_question
        csv_str = export_csv(quiz, [question])
        assert "short_answer" in csv_str.lower()
        assert "photosynthesis" in csv_str

    def test_csv_format_options_ordering(self):
        nq = {
            "type": "ordering",
            "ordering_items": ["Step A", "Step B", "Step C"],
        }
        result = _format_options_csv(nq)
        assert "Step A" in result
        assert "Step B" in result
        assert "Step C" in result

    def test_csv_format_options_short_answer(self):
        nq = {
            "type": "short_answer",
            "expected_answer": "gravity",
            "acceptable_answers": ["gravity", "gravitational force"],
        }
        result = _format_options_csv(nq)
        assert "gravity" in result
        assert "gravitational force" in result


# ---------------------------------------------------------------------------
# DOCX Export Tests
# ---------------------------------------------------------------------------


class TestDOCXExport:
    """Test DOCX export for new question types."""

    def test_docx_ordering(self, ordering_question):
        quiz, question = ordering_question
        buf = export_docx(quiz, [question])
        assert buf is not None
        assert buf.tell() == 0
        content = buf.read()
        assert len(content) > 0

    def test_docx_short_answer(self, short_answer_question):
        quiz, question = short_answer_question
        buf = export_docx(quiz, [question])
        assert buf is not None
        content = buf.read()
        assert len(content) > 0


# ---------------------------------------------------------------------------
# GIFT Export Tests
# ---------------------------------------------------------------------------


class TestGIFTExport:
    """Test GIFT export for new question types."""

    def test_gift_ordering(self, ordering_question):
        quiz, question = ordering_question
        gift_str = export_gift(quiz, [question])
        assert "::Q1::" in gift_str
        # Ordering uses matching-style format in GIFT
        assert "-> 1" in gift_str or "-> 2" in gift_str

    def test_gift_short_answer(self, short_answer_question):
        quiz, question = short_answer_question
        gift_str = export_gift(quiz, [question])
        assert "::Q1::" in gift_str
        # Should have =answer1 =answer2 format
        assert "=photosynthesis" in gift_str
        assert "=the process of photosynthesis" in gift_str

    def test_gift_ordering_function(self):
        nq = {
            "number": 1,
            "ordering_items": ["A", "B", "C"],
            "ordering_correct_order": [0, 1, 2],
        }
        result = _gift_ordering("Q1", "Order these items", nq)
        assert "=A -> 1" in result
        assert "=B -> 2" in result
        assert "=C -> 3" in result

    def test_gift_short_answer_function(self):
        nq = {
            "number": 1,
            "expected_answer": "mitosis",
            "acceptable_answers": ["mitosis", "cell division"],
            "correct_answer": "mitosis",
        }
        result = _gift_short_answer("Q1", "What is cell division called?", nq)
        assert "=mitosis" in result
        assert "=cell division" in result

    def test_gift_short_answer_no_duplicates(self):
        nq = {
            "number": 1,
            "expected_answer": "mitosis",
            "acceptable_answers": ["mitosis", "cell division"],
            "correct_answer": "",
        }
        result = _gift_short_answer("Q1", "Question text", nq)
        # "mitosis" should appear twice (once as expected, once in acceptable)
        # but the function deduplicates
        count = result.count("=mitosis")
        assert count == 1


# ---------------------------------------------------------------------------
# PDF Export Tests
# ---------------------------------------------------------------------------


class TestPDFExport:
    """Test PDF export for new question types."""

    def test_pdf_ordering(self, ordering_question):
        quiz, question = ordering_question
        buf = export_pdf(quiz, [question])
        assert buf is not None
        content = buf.read()
        assert len(content) > 0
        # PDF should contain content (we check it doesn't crash)

    def test_pdf_short_answer(self, short_answer_question):
        quiz, question = short_answer_question
        buf = export_pdf(quiz, [question])
        assert buf is not None
        content = buf.read()
        assert len(content) > 0
