"""Tests for multiple-answer (select all that apply) question support.

Covers mock generation, normalization, all export formats, web display,
critic validation, and the Quizizz skip behavior.
"""

import io
import json
import zipfile
from unittest.mock import MagicMock

from src.critic_validation import VALID_TYPES, pre_validate_questions
from src.export import (
    export_csv,
    export_docx,
    export_gift,
    export_pdf,
    export_qti,
    export_quizizz_csv,
    normalize_question,
)
from src.question_regenerator import normalize_question_data

# ── Fixtures ──────────────────────────────────────────────────────────


def _make_ma_question_obj(
    text="Which are true about photosynthesis?",
    options=None,
    correct_indices=None,
    q_type="ma",
    points=5,
):
    """Build a mock Question ORM object for an ma question."""
    if options is None:
        options = [
            "Produces oxygen",
            "Occurs only in animals",
            "Uses sunlight",
            "Requires no water",
        ]
    if correct_indices is None:
        correct_indices = [0, 2]

    data = {
        "type": q_type,
        "text": text,
        "options": options,
        "correct_indices": correct_indices,
        "points": points,
    }

    obj = MagicMock()
    obj.data = data
    obj.text = text
    obj.question_type = q_type
    obj.points = points
    return obj


def _make_quiz_obj(title="Test Quiz"):
    obj = MagicMock()
    obj.title = title
    obj.status = "generated"
    obj.created_at = None
    obj.reading_level = None
    return obj


# ── Type registry ─────────────────────────────────────────────────────


class TestMATypeRegistry:
    def test_ma_in_valid_types(self):
        assert "ma" in VALID_TYPES

    def test_multiple_answer_in_export_type_map(self):
        from src.export import TYPE_MAP

        assert TYPE_MAP["multiple_answer"] == "ma"


# ── Normalization ─────────────────────────────────────────────────────


class TestMANormalization:
    def test_normalize_question_ma_type(self):
        q = _make_ma_question_obj()
        nq = normalize_question(q, 0)
        assert nq["type"] == "ma"
        assert nq["correct_indices"] == [0, 2]

    def test_normalize_question_ma_correct_answer_text(self):
        q = _make_ma_question_obj()
        nq = normalize_question(q, 0)
        # correct_answer should be comma-separated text of correct options
        assert "Produces oxygen" in nq["correct_answer"]
        assert "Uses sunlight" in nq["correct_answer"]

    def test_normalize_question_data_multiple_answer_type(self):
        raw = {
            "question_type": "multiple_answer",
            "text": "Select all correct answers.",
            "options": ["A", "B", "C"],
            "correct_indices": [0, 2],
        }
        result = normalize_question_data(raw)
        assert result["type"] == "ma"

    def test_normalize_question_data_select_all_type(self):
        raw = {
            "question_type": "select all that apply",
            "text": "Pick all.",
            "options": ["X", "Y"],
            "correct_indices": [1],
        }
        result = normalize_question_data(raw)
        assert result["type"] == "ma"

    def test_normalize_infers_ma_from_correct_indices(self):
        raw = {
            "text": "Which?",
            "options": ["A", "B", "C"],
            "correct_indices": [0, 1],
        }
        result = normalize_question_data(raw)
        assert result["type"] == "ma"

    def test_normalize_long_form_multiple_answer_in_export(self):
        """Question with type='multiple_answer' normalizes to 'ma' in export."""
        q = _make_ma_question_obj(q_type="multiple_answer")
        nq = normalize_question(q, 0)
        assert nq["type"] == "ma"


# ── Critic validation ─────────────────────────────────────────────────


class TestMACriticValidation:
    def test_valid_ma_question_passes(self):
        q = {
            "type": "ma",
            "text": "Select all that apply.",
            "options": ["A", "B", "C", "D"],
            "correct_indices": [0, 2],
            "points": 5,
        }
        results = pre_validate_questions([q])
        assert results[0]["passed"] is True

    def test_ma_missing_correct_indices_fails(self):
        q = {
            "type": "ma",
            "text": "Select all that apply.",
            "options": ["A", "B", "C"],
            "points": 5,
        }
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("correct_indices" in issue for issue in results[0]["issues"])

    def test_ma_empty_correct_indices_fails(self):
        q = {
            "type": "ma",
            "text": "Select all.",
            "options": ["A", "B"],
            "correct_indices": [],
            "points": 3,
        }
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_ma_out_of_bounds_indices_fails(self):
        q = {
            "type": "ma",
            "text": "Select all.",
            "options": ["A", "B"],
            "correct_indices": [0, 5],
            "points": 3,
        }
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_ma_too_few_options_fails(self):
        q = {
            "type": "ma",
            "text": "Pick all.",
            "options": ["Only one"],
            "correct_indices": [0],
            "points": 2,
        }
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False


# ── CSV Export ────────────────────────────────────────────────────────


class TestMACSVExport:
    def test_csv_contains_ma_question(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        csv_text = export_csv(quiz, [q])
        assert "ma" in csv_text
        assert "Produces oxygen" in csv_text
        assert "Uses sunlight" in csv_text

    def test_csv_correct_answer_comma_separated(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        csv_text = export_csv(quiz, [q])
        # Correct answer column should contain both correct options
        assert "Produces oxygen" in csv_text
        assert "Uses sunlight" in csv_text

    def test_csv_options_mark_correct_with_asterisk(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        csv_text = export_csv(quiz, [q])
        # In teacher mode, correct options get * marker
        assert "Produces oxygen*" in csv_text
        assert "Uses sunlight*" in csv_text
        # Incorrect options don't get *
        assert "Occurs only in animals*" not in csv_text


# ── Quizizz CSV Export ────────────────────────────────────────────────


class TestMAQuizizzExport:
    def test_quizizz_skips_ma_questions(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        csv_text = export_quizizz_csv(quiz, [q])
        # Should only have the header, no data rows
        lines = csv_text.strip().split("\n")
        assert len(lines) == 1  # header only


# ── DOCX Export ───────────────────────────────────────────────────────


class TestMADOCXExport:
    def test_docx_exports_without_error(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        buf = export_docx(quiz, [q])
        assert isinstance(buf, io.BytesIO)
        assert buf.getvalue()  # non-empty

    def test_docx_student_mode_exports(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        buf = export_docx(quiz, [q], student_mode=True)
        assert isinstance(buf, io.BytesIO)
        assert buf.getvalue()


# ── PDF Export ────────────────────────────────────────────────────────


class TestMAPDFExport:
    def test_pdf_exports_without_error(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        buf = export_pdf(quiz, [q])
        assert isinstance(buf, io.BytesIO)
        # PDF starts with %PDF
        assert buf.getvalue()[:5] == b"%PDF-"

    def test_pdf_student_mode_exports(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        buf = export_pdf(quiz, [q], student_mode=True)
        assert isinstance(buf, io.BytesIO)
        assert buf.getvalue()[:5] == b"%PDF-"


# ── GIFT Export ───────────────────────────────────────────────────────


class TestMAGIFTExport:
    def test_gift_contains_percentage_weights(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        gift_text = export_gift(quiz, [q])
        # Moodle multi-answer uses ~%weight% format
        assert "~%" in gift_text

    def test_gift_correct_options_have_positive_weight(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj(
            options=["A", "B", "C", "D"],
            correct_indices=[0, 2],
        )
        gift_text = export_gift(quiz, [q])
        # 2 correct answers -> 50% each
        assert "%50" in gift_text

    def test_gift_wrong_options_have_negative_weight(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj(
            options=["A", "B", "C", "D"],
            correct_indices=[0, 2],
        )
        gift_text = export_gift(quiz, [q])
        # 2 wrong answers -> -50% each
        assert "%-50" in gift_text


# ── QTI Export ────────────────────────────────────────────────────────


class TestMAQTIExport:
    def test_qti_exports_without_error(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        buf = export_qti(quiz, [q])
        assert isinstance(buf, io.BytesIO)

    def test_qti_has_multiple_cardinality(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        buf = export_qti(quiz, [q])
        # Read the assessment XML from the zip
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            xml_file = [n for n in names if n.endswith(".xml") and n != "imsmanifest.xml"][0]
            xml_content = zf.read(xml_file).decode("utf-8")

        assert 'rcardinality="Multiple"' in xml_content
        assert "multiple_answers_question" in xml_content

    def test_qti_has_and_condition(self):
        quiz = _make_quiz_obj()
        q = _make_ma_question_obj()
        buf = export_qti(quiz, [q])
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            xml_file = [n for n in names if n.endswith(".xml") and n != "imsmanifest.xml"][0]
            xml_content = zf.read(xml_file).decode("utf-8")

        # Should have <and> with varequal and <not> conditions
        assert "<and>" in xml_content
        assert "<varequal" in xml_content
        assert "<not>" in xml_content


# ── Mock response generation ──────────────────────────────────────────


class TestMAMockResponses:
    def test_mock_generator_can_produce_ma(self):
        """Mock generator includes multiple_answer in its type pool."""
        from src.mock_responses import get_generator_response

        # Run enough iterations that we should see at least one ma
        found_ma = False
        for _ in range(50):
            response = get_generator_response(["test prompt about photosynthesis"])
            questions = json.loads(response)
            for q in questions:
                if q.get("type") == "multiple_answer":
                    found_ma = True
                    assert "correct_indices" in q
                    assert isinstance(q["correct_indices"], list)
                    assert len(q["correct_indices"]) >= 1
                    assert "options" in q
                    break
            if found_ma:
                break
        assert found_ma, "Mock generator never produced a multiple_answer question in 50 attempts"


# ── Answer key text ───────────────────────────────────────────────────


class TestMAAnswerKey:
    def test_pdf_answer_text_lists_all_correct(self):
        from src.export import _pdf_answer_text

        nq = {
            "type": "ma",
            "options": ["Opt A", "Opt B", "Opt C", "Opt D"],
            "correct_indices": [0, 2],
            "correct_answer": "Opt A, Opt C",
        }
        text = _pdf_answer_text(nq)
        assert "A. Opt A" in text
        assert "C. Opt C" in text
        assert "B." not in text

    def test_pdf_answer_text_fallback_when_no_indices(self):
        from src.export import _pdf_answer_text

        nq = {
            "type": "ma",
            "options": [],
            "correct_indices": [],
            "correct_answer": "Some answer",
        }
        text = _pdf_answer_text(nq)
        assert text == "Some answer"
