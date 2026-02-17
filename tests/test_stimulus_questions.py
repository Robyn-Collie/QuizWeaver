"""Tests for stimulus/passage-based question groups (BL-065).

Covers:
- Mock response generation for stimulus questions
- Export normalization (normalize_question)
- Critic pre-validation (_check_stimulus)
- Question regenerator type mapping
- CSV, DOCX, GIFT, PDF, QTI export rendering
- Web display template rendering
"""

import io
import json
import unittest
import zipfile
from unittest.mock import MagicMock

from src.critic_validation import VALID_TYPES, pre_validate_questions
from src.export import (
    TYPE_MAP,
    _format_options_csv,
    export_csv,
    export_docx,
    export_gift,
    export_pdf,
    export_qti,
    normalize_question,
)
from src.mock_responses import get_generator_response
from src.question_regenerator import normalize_question_data


def _make_stimulus_question_obj(sub_questions=None, **overrides):
    """Build a mock Question ORM object for a stimulus question."""
    if sub_questions is None:
        sub_questions = [
            {
                "type": "mc",
                "text": "Based on the passage, what is the primary role of photosynthesis?",
                "options": [
                    "To produce energy",
                    "To eliminate waste",
                    "To slow reactions",
                    "To reduce growth",
                ],
                "correct_index": 0,
                "points": 1,
            },
            {
                "type": "tf",
                "text": "According to the passage, photosynthesis involves multiple stages.",
                "correct_answer": "True",
                "points": 1,
            },
        ]
    data = {
        "type": "stimulus",
        "text": "Read the following passage and answer the questions below.",
        "stimulus_text": (
            "Photosynthesis is a fundamental biological process. Plants convert "
            "sunlight into chemical energy through a series of reactions."
        ),
        "image_url": None,
        "sub_questions": sub_questions,
    }
    data.update(overrides)
    obj = MagicMock()
    obj.data = data
    obj.text = data["text"]
    obj.question_type = "stimulus"
    obj.points = sum(sq.get("points", 1) for sq in sub_questions)
    return obj


def _make_quiz():
    """Build a minimal mock Quiz ORM object."""
    quiz = MagicMock()
    quiz.title = "Stimulus Test Quiz"
    quiz.status = "generated"
    quiz.created_at = None
    return quiz


# ---------------------------------------------------------------------------
# TYPE_MAP and VALID_TYPES
# ---------------------------------------------------------------------------


class TestStimulusTypeRegistration(unittest.TestCase):
    """Verify stimulus is registered in type maps."""

    def test_stimulus_in_type_map(self):
        assert "stimulus" in TYPE_MAP
        assert TYPE_MAP["stimulus"] == "stimulus"

    def test_stimulus_in_valid_types(self):
        assert "stimulus" in VALID_TYPES


# ---------------------------------------------------------------------------
# Mock Response
# ---------------------------------------------------------------------------


class TestStimulusMockResponse(unittest.TestCase):
    """Verify mock generator can produce stimulus questions."""

    def test_generator_can_produce_stimulus(self):
        """Run generator many times; at least one should be stimulus."""
        import random

        random.seed(42)
        found_stimulus = False
        for _ in range(20):
            response = get_generator_response(["Test prompt about photosynthesis"])
            questions = json.loads(response)
            for q in questions:
                if q.get("type") == "stimulus":
                    found_stimulus = True
                    # Verify stimulus structure
                    assert "stimulus_text" in q
                    assert "sub_questions" in q
                    assert isinstance(q["sub_questions"], list)
                    assert len(q["sub_questions"]) >= 1
                    for sq in q["sub_questions"]:
                        assert "type" in sq
                        assert "text" in sq
                        assert "points" in sq
                    break
            if found_stimulus:
                break
        assert found_stimulus, "Mock generator never produced a stimulus question in 20 runs"


# ---------------------------------------------------------------------------
# Normalize Question
# ---------------------------------------------------------------------------


class TestStimulusNormalize(unittest.TestCase):
    """Test normalize_question for stimulus type."""

    def test_normalize_stimulus(self):
        obj = _make_stimulus_question_obj()
        nq = normalize_question(obj, 0)
        assert nq["type"] == "stimulus"
        assert nq["number"] == 1
        assert "stimulus_text" in nq
        assert len(nq["stimulus_text"]) > 0
        assert len(nq["sub_questions"]) == 2

    def test_normalize_stimulus_points(self):
        """Points should be the sum of sub-question points."""
        obj = _make_stimulus_question_obj()
        nq = normalize_question(obj, 0)
        assert nq["points"] == 2  # 1 + 1

    def test_normalize_stimulus_from_json_string(self):
        """Data stored as JSON string should parse correctly."""
        obj = _make_stimulus_question_obj()
        obj.data = json.dumps(obj.data)
        nq = normalize_question(obj, 0)
        assert nq["type"] == "stimulus"
        assert len(nq["sub_questions"]) == 2


# ---------------------------------------------------------------------------
# Normalizer (question_regenerator)
# ---------------------------------------------------------------------------


class TestStimulusQuestionRegenerator(unittest.TestCase):
    """Test normalize_question_data for stimulus type mapping."""

    def test_stimulus_via_question_type(self):
        q = normalize_question_data(
            {
                "text": "Read the passage.",
                "question_type": "Stimulus",
                "stimulus_text": "Some passage...",
                "sub_questions": [{"type": "mc", "text": "Q?", "points": 1}],
            }
        )
        assert q["type"] == "stimulus"

    def test_passage_via_question_type(self):
        q = normalize_question_data(
            {
                "text": "Read the passage.",
                "question_type": "Passage",
                "stimulus_text": "Some passage...",
                "sub_questions": [{"type": "mc", "text": "Q?", "points": 1}],
            }
        )
        assert q["type"] == "stimulus"

    def test_stimulus_preserves_sub_questions(self):
        sqs = [
            {"type": "mc", "text": "Q1?", "options": ["A", "B"], "correct_index": 0, "points": 1},
            {"type": "tf", "text": "Q2?", "correct_answer": "True", "points": 1},
        ]
        q = normalize_question_data(
            {
                "type": "stimulus",
                "text": "Read and answer.",
                "stimulus_text": "A passage.",
                "sub_questions": sqs,
            }
        )
        assert q["type"] == "stimulus"
        assert len(q["sub_questions"]) == 2


# ---------------------------------------------------------------------------
# Critic Validation
# ---------------------------------------------------------------------------


class TestStimulusCriticValidation(unittest.TestCase):
    """Test pre_validate_questions for stimulus type."""

    def _valid_stimulus(self):
        return {
            "type": "stimulus",
            "text": "Read the passage.",
            "points": 2,
            "stimulus_text": "A passage about cells.",
            "sub_questions": [
                {"type": "mc", "text": "Q1?", "points": 1},
                {"type": "tf", "text": "Q2?", "points": 1},
            ],
        }

    def test_valid_stimulus_passes(self):
        results = pre_validate_questions([self._valid_stimulus()])
        assert results[0]["passed"] is True

    def test_missing_stimulus_text_fails(self):
        q = self._valid_stimulus()
        q["stimulus_text"] = ""
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("stimulus_text" in i for i in results[0]["issues"])

    def test_missing_sub_questions_fails(self):
        q = self._valid_stimulus()
        q["sub_questions"] = []
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("sub-question" in i.lower() or "sub_question" in i.lower() for i in results[0]["issues"])

    def test_sub_question_missing_text_fails(self):
        q = self._valid_stimulus()
        q["sub_questions"][0]["text"] = ""
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_sub_question_missing_type_fails(self):
        q = self._valid_stimulus()
        del q["sub_questions"][0]["type"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------


class TestStimulusCsvExport(unittest.TestCase):
    """Test stimulus question CSV export."""

    def test_csv_includes_stimulus(self):
        quiz = _make_quiz()
        obj = _make_stimulus_question_obj()
        csv_str = export_csv(quiz, [obj])
        assert "STIMULUS" in csv_str.upper() or "Sub-Q" in csv_str

    def test_format_options_csv_stimulus(self):
        nq = normalize_question(_make_stimulus_question_obj(), 0)
        result = _format_options_csv(nq)
        assert "Sub-Q1" in result
        assert "Sub-Q2" in result


# ---------------------------------------------------------------------------
# DOCX Export
# ---------------------------------------------------------------------------


class TestStimulusDocxExport(unittest.TestCase):
    """Test stimulus question DOCX export."""

    def test_docx_includes_stimulus(self):
        quiz = _make_quiz()
        obj = _make_stimulus_question_obj()
        buf = export_docx(quiz, [obj])
        assert isinstance(buf, io.BytesIO)
        assert buf.getvalue()  # non-empty

    def test_docx_student_mode(self):
        quiz = _make_quiz()
        obj = _make_stimulus_question_obj()
        buf = export_docx(quiz, [obj], student_mode=True)
        assert isinstance(buf, io.BytesIO)
        assert buf.getvalue()


# ---------------------------------------------------------------------------
# GIFT Export
# ---------------------------------------------------------------------------


class TestStimulusGiftExport(unittest.TestCase):
    """Test stimulus question GIFT export."""

    def test_gift_includes_stimulus_text(self):
        quiz = _make_quiz()
        obj = _make_stimulus_question_obj()
        gift_str = export_gift(quiz, [obj])
        assert "Passage" in gift_str or "passage" in gift_str or "Photosynthesis" in gift_str


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------


class TestStimulusPdfExport(unittest.TestCase):
    """Test stimulus question PDF export."""

    def test_pdf_includes_stimulus(self):
        quiz = _make_quiz()
        obj = _make_stimulus_question_obj()
        buf = export_pdf(quiz, [obj])
        assert isinstance(buf, io.BytesIO)
        assert len(buf.getvalue()) > 100  # non-trivial PDF

    def test_pdf_student_mode(self):
        quiz = _make_quiz()
        obj = _make_stimulus_question_obj()
        buf = export_pdf(quiz, [obj], student_mode=True)
        assert isinstance(buf, io.BytesIO)


# ---------------------------------------------------------------------------
# QTI Export
# ---------------------------------------------------------------------------


class TestStimulusQtiExport(unittest.TestCase):
    """Test stimulus question QTI export."""

    def test_qti_produces_valid_zip(self):
        quiz = _make_quiz()
        obj = _make_stimulus_question_obj()
        buf = export_qti(quiz, [obj])
        assert isinstance(buf, io.BytesIO)
        with zipfile.ZipFile(buf) as zf:
            assert "imsmanifest.xml" in zf.namelist()
            # Find the assessment XML
            xml_files = [n for n in zf.namelist() if n.endswith(".xml") and n != "imsmanifest.xml"]
            assert len(xml_files) == 1
            content = zf.read(xml_files[0]).decode("utf-8")
            # Should contain sub-question items
            assert "item" in content.lower()


# ---------------------------------------------------------------------------
# Multiple sub-question types
# ---------------------------------------------------------------------------


class TestStimulusSubQuestionVariety(unittest.TestCase):
    """Test stimulus with different sub-question types."""

    def test_stimulus_with_short_answer_sub(self):
        sqs = [
            {
                "type": "short_answer",
                "text": "Name one product of photosynthesis.",
                "expected_answer": "oxygen",
                "acceptable_answers": ["oxygen", "glucose"],
                "points": 2,
            },
        ]
        obj = _make_stimulus_question_obj(sub_questions=sqs)
        nq = normalize_question(obj, 0)
        assert nq["type"] == "stimulus"
        assert len(nq["sub_questions"]) == 1
        assert nq["sub_questions"][0]["type"] == "short_answer"

    def test_stimulus_total_points(self):
        """Total points should equal sum of sub-question points."""
        sqs = [
            {"type": "mc", "text": "Q1", "options": ["A", "B"], "correct_index": 0, "points": 2},
            {"type": "mc", "text": "Q2", "options": ["A", "B"], "correct_index": 1, "points": 3},
            {"type": "tf", "text": "Q3", "correct_answer": "True", "points": 1},
        ]
        obj = _make_stimulus_question_obj(sub_questions=sqs)
        assert obj.points == 6  # 2 + 3 + 1


if __name__ == "__main__":
    unittest.main()
