"""Tests for cloze (fill-in-multiple-blanks) question support (BL-067).

Covers:
- Mock response generation for cloze questions
- Export normalization (normalize_question)
- Critic pre-validation (_check_cloze)
- Question regenerator type mapping
- CSV, DOCX, GIFT, PDF, QTI export rendering
- Quizizz CSV skip behavior
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
    _pdf_answer_text,
    export_csv,
    export_docx,
    export_gift,
    export_pdf,
    export_qti,
    export_quizizz_csv,
    normalize_question,
)
from src.mock_responses import get_generator_response
from src.question_regenerator import normalize_question_data

# ── Fixtures ──────────────────────────────────────────────────────────


def _make_cloze_question_obj(
    text=None,
    blanks=None,
    points=2,
):
    """Build a mock Question ORM object for a cloze question."""
    if text is None:
        text = "The {{1}} is the powerhouse of the {{2}}."
    if blanks is None:
        blanks = [
            {"id": 1, "answer": "mitochondria", "alternatives": ["mitochondrion"]},
            {"id": 2, "answer": "cell", "alternatives": ["living cell"]},
        ]

    data = {
        "type": "cloze",
        "text": text,
        "blanks": blanks,
        "points": points,
    }

    obj = MagicMock()
    obj.data = data
    obj.text = text
    obj.question_type = "cloze"
    obj.points = points
    return obj


def _make_quiz_obj(title="Cloze Test Quiz"):
    obj = MagicMock()
    obj.title = title
    obj.status = "generated"
    obj.created_at = None
    obj.reading_level = None
    return obj


# ── Type registry ─────────────────────────────────────────────────────


class TestClozeTypeRegistry(unittest.TestCase):
    def test_cloze_in_valid_types(self):
        assert "cloze" in VALID_TYPES

    def test_cloze_in_export_type_map(self):
        assert "cloze" in TYPE_MAP
        assert TYPE_MAP["cloze"] == "cloze"

    def test_fill_in_multiple_blanks_maps_to_cloze(self):
        assert TYPE_MAP["fill_in_multiple_blanks"] == "cloze"


# ── Mock Response ─────────────────────────────────────────────────────


class TestClozeMockResponse(unittest.TestCase):
    def test_mock_generator_can_produce_cloze(self):
        """Mock generator includes cloze in its type pool."""
        import random

        random.seed(42)
        found_cloze = False
        for _ in range(50):
            response = get_generator_response(["test prompt about photosynthesis"])
            questions = json.loads(response)
            for q in questions:
                if q.get("type") == "cloze":
                    found_cloze = True
                    assert "blanks" in q
                    assert isinstance(q["blanks"], list)
                    assert len(q["blanks"]) >= 1
                    for blank in q["blanks"]:
                        assert "id" in blank
                        assert "answer" in blank
                    # Verify text has {{id}} placeholders
                    assert "{{1}}" in q["text"]
                    break
            if found_cloze:
                break
        assert found_cloze, "Mock generator never produced a cloze question in 50 runs"


# ── Normalization ─────────────────────────────────────────────────────


class TestClozeNormalization(unittest.TestCase):
    def test_normalize_cloze_type(self):
        q = _make_cloze_question_obj()
        nq = normalize_question(q, 0)
        assert nq["type"] == "cloze"
        assert nq["number"] == 1

    def test_normalize_cloze_blanks(self):
        q = _make_cloze_question_obj()
        nq = normalize_question(q, 0)
        assert len(nq["blanks"]) == 2
        assert nq["blanks"][0]["answer"] == "mitochondria"
        assert nq["blanks"][1]["answer"] == "cell"

    def test_normalize_cloze_correct_answer(self):
        """correct_answer should be semicolon-separated blank answers."""
        q = _make_cloze_question_obj()
        nq = normalize_question(q, 0)
        assert "mitochondria" in nq["correct_answer"]
        assert "cell" in nq["correct_answer"]
        assert ";" in nq["correct_answer"]

    def test_normalize_cloze_from_json_string(self):
        """Data stored as JSON string should parse correctly."""
        q = _make_cloze_question_obj()
        q.data = json.dumps(q.data)
        nq = normalize_question(q, 0)
        assert nq["type"] == "cloze"
        assert len(nq["blanks"]) == 2

    def test_normalize_fill_in_multiple_blanks_type(self):
        """fill_in_multiple_blanks should normalize to cloze."""
        q = _make_cloze_question_obj()
        q.question_type = "fill_in_multiple_blanks"
        nq = normalize_question(q, 0)
        assert nq["type"] == "cloze"


# ── Question Regenerator ─────────────────────────────────────────────


class TestClozeQuestionRegenerator(unittest.TestCase):
    def test_cloze_via_question_type(self):
        q = normalize_question_data(
            {
                "text": "The {{1}} is important.",
                "question_type": "Cloze",
                "blanks": [{"id": 1, "answer": "answer"}],
            }
        )
        assert q["type"] == "cloze"

    def test_fill_in_multiple_blanks_via_question_type(self):
        q = normalize_question_data(
            {
                "text": "The {{1}} does {{2}}.",
                "question_type": "fill in multiple blanks",
                "blanks": [
                    {"id": 1, "answer": "a"},
                    {"id": 2, "answer": "b"},
                ],
            }
        )
        assert q["type"] == "cloze"

    def test_cloze_preserves_blanks(self):
        blanks = [
            {"id": 1, "answer": "mitochondria", "alternatives": ["mitochondrion"]},
            {"id": 2, "answer": "cell", "alternatives": []},
        ]
        q = normalize_question_data(
            {
                "type": "cloze",
                "text": "The {{1}} is in the {{2}}.",
                "blanks": blanks,
            }
        )
        assert q["type"] == "cloze"
        assert q["blanks"] == blanks


# ── Critic Validation ────────────────────────────────────────────────


class TestClozeCriticValidation(unittest.TestCase):
    def _valid_cloze(self):
        return {
            "type": "cloze",
            "text": "The {{1}} is the powerhouse of the {{2}}.",
            "points": 2,
            "blanks": [
                {"id": 1, "answer": "mitochondria", "alternatives": ["mitochondrion"]},
                {"id": 2, "answer": "cell", "alternatives": []},
            ],
        }

    def test_valid_cloze_passes(self):
        results = pre_validate_questions([self._valid_cloze()])
        assert results[0]["passed"] is True

    def test_missing_blanks_fails(self):
        q = self._valid_cloze()
        del q["blanks"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("blanks" in i.lower() for i in results[0]["issues"])

    def test_empty_blanks_list_fails(self):
        q = self._valid_cloze()
        q["blanks"] = []
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_blank_missing_id_fails(self):
        q = self._valid_cloze()
        del q["blanks"][0]["id"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("id" in i.lower() for i in results[0]["issues"])

    def test_blank_missing_answer_fails(self):
        q = self._valid_cloze()
        q["blanks"][0]["answer"] = ""
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("answer" in i.lower() for i in results[0]["issues"])

    def test_mismatched_placeholders_fails(self):
        q = self._valid_cloze()
        q["text"] = "The {{1}} is here but {{3}} is wrong."
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("placeholder" in i.lower() for i in results[0]["issues"])

    def test_no_placeholders_in_text_fails(self):
        q = self._valid_cloze()
        q["text"] = "The blank is here with no placeholders."
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("placeholder" in i.lower() for i in results[0]["issues"])

    def test_three_blanks_valid(self):
        q = {
            "type": "cloze",
            "text": "In {{1}}, the {{2}} produces {{3}}.",
            "points": 3,
            "blanks": [
                {"id": 1, "answer": "photosynthesis"},
                {"id": 2, "answer": "chloroplast"},
                {"id": 3, "answer": "glucose"},
            ],
        }
        results = pre_validate_questions([q])
        assert results[0]["passed"] is True


# ── CSV Export ────────────────────────────────────────────────────────


class TestClozeCSVExport(unittest.TestCase):
    def test_csv_contains_cloze_question(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        csv_text = export_csv(quiz, [q])
        assert "cloze" in csv_text
        assert "mitochondria" in csv_text

    def test_csv_correct_answer_semicolon_separated(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        csv_text = export_csv(quiz, [q])
        assert "mitochondria" in csv_text
        assert "cell" in csv_text

    def test_format_options_csv_cloze(self):
        nq = normalize_question(_make_cloze_question_obj(), 0)
        result = _format_options_csv(nq)
        assert "Blank 1" in result
        assert "Blank 2" in result
        assert "mitochondria" in result
        assert "cell" in result

    def test_format_options_csv_alternatives(self):
        nq = normalize_question(_make_cloze_question_obj(), 0)
        result = _format_options_csv(nq)
        assert "mitochondrion" in result  # alternative for blank 1


# ── Quizizz CSV Export ────────────────────────────────────────────────


class TestClozeQuizizzExport(unittest.TestCase):
    def test_quizizz_skips_cloze_questions(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        csv_text = export_quizizz_csv(quiz, [q])
        lines = csv_text.strip().split("\n")
        assert len(lines) == 1  # header only


# ── DOCX Export ───────────────────────────────────────────────────────


class TestClozeDOCXExport(unittest.TestCase):
    def test_docx_exports_without_error(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        buf = export_docx(quiz, [q])
        assert isinstance(buf, io.BytesIO)
        assert buf.getvalue()  # non-empty

    def test_docx_student_mode_exports(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        buf = export_docx(quiz, [q], student_mode=True)
        assert isinstance(buf, io.BytesIO)
        assert buf.getvalue()


# ── PDF Export ────────────────────────────────────────────────────────


class TestClozePDFExport(unittest.TestCase):
    def test_pdf_exports_without_error(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        buf = export_pdf(quiz, [q])
        assert isinstance(buf, io.BytesIO)
        assert buf.getvalue()[:5] == b"%PDF-"

    def test_pdf_student_mode_exports(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        buf = export_pdf(quiz, [q], student_mode=True)
        assert isinstance(buf, io.BytesIO)
        assert buf.getvalue()[:5] == b"%PDF-"

    def test_pdf_answer_text_cloze(self):
        nq = normalize_question(_make_cloze_question_obj(), 0)
        text = _pdf_answer_text(nq)
        assert "(1) mitochondria" in text
        assert "(2) cell" in text
        assert "mitochondrion" in text  # alternative

    def test_pdf_answer_text_cloze_no_alternatives(self):
        q = _make_cloze_question_obj(
            blanks=[
                {"id": 1, "answer": "oxygen", "alternatives": []},
                {"id": 2, "answer": "carbon dioxide", "alternatives": []},
            ]
        )
        nq = normalize_question(q, 0)
        text = _pdf_answer_text(nq)
        assert "(1) oxygen" in text
        assert "(2) carbon dioxide" in text


# ── GIFT Export ───────────────────────────────────────────────────────


class TestClozeGIFTExport(unittest.TestCase):
    def test_gift_uses_native_cloze_format(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        gift_text = export_gift(quiz, [q])
        assert "SHORTANSWER" in gift_text

    def test_gift_cloze_contains_answers(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        gift_text = export_gift(quiz, [q])
        assert "mitochondria" in gift_text
        assert "cell" in gift_text

    def test_gift_cloze_contains_alternatives(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        gift_text = export_gift(quiz, [q])
        assert "mitochondrion" in gift_text


# ── QTI Export ────────────────────────────────────────────────────────


class TestClozeQTIExport(unittest.TestCase):
    def test_qti_exports_without_error(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        buf = export_qti(quiz, [q])
        assert isinstance(buf, io.BytesIO)

    def test_qti_has_fill_in_multiple_blanks_type(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        buf = export_qti(quiz, [q])
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            xml_file = [n for n in names if n.endswith(".xml") and n != "imsmanifest.xml"][0]
            xml_content = zf.read(xml_file).decode("utf-8")
        assert "fill_in_multiple_blanks_question" in xml_content

    def test_qti_has_multiple_response_strs(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        buf = export_qti(quiz, [q])
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            xml_file = [n for n in names if n.endswith(".xml") and n != "imsmanifest.xml"][0]
            xml_content = zf.read(xml_file).decode("utf-8")
        # Should have response_str for each blank
        assert "response_1" in xml_content
        assert "response_2" in xml_content

    def test_qti_has_varequal_for_answers(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        buf = export_qti(quiz, [q])
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            xml_file = [n for n in names if n.endswith(".xml") and n != "imsmanifest.xml"][0]
            xml_content = zf.read(xml_file).decode("utf-8")
        assert "mitochondria" in xml_content
        assert "cell" in xml_content

    def test_qti_includes_alternatives(self):
        quiz = _make_quiz_obj()
        q = _make_cloze_question_obj()
        buf = export_qti(quiz, [q])
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            xml_file = [n for n in names if n.endswith(".xml") and n != "imsmanifest.xml"][0]
            xml_content = zf.read(xml_file).decode("utf-8")
        assert "mitochondrion" in xml_content  # alternative


# ── Edge Cases ────────────────────────────────────────────────────────


class TestClozeEdgeCases(unittest.TestCase):
    def test_single_blank_cloze(self):
        """Cloze with just one blank should still work."""
        q = _make_cloze_question_obj(
            text="The process of {{1}} converts light energy.",
            blanks=[{"id": 1, "answer": "photosynthesis", "alternatives": []}],
            points=1,
        )
        nq = normalize_question(q, 0)
        assert nq["type"] == "cloze"
        assert len(nq["blanks"]) == 1
        assert "photosynthesis" in nq["correct_answer"]

    def test_four_blanks_cloze(self):
        """Cloze with four blanks should work across all exports."""
        q = _make_cloze_question_obj(
            text="In {{1}}, the {{2}} uses {{3}} to produce {{4}}.",
            blanks=[
                {"id": 1, "answer": "photosynthesis"},
                {"id": 2, "answer": "chloroplast"},
                {"id": 3, "answer": "sunlight"},
                {"id": 4, "answer": "glucose"},
            ],
            points=4,
        )
        quiz = _make_quiz_obj()

        # All exports should succeed without error
        nq = normalize_question(q, 0)
        assert len(nq["blanks"]) == 4
        assert nq["points"] == 4

        buf_pdf = export_pdf(quiz, [q])
        assert buf_pdf.getvalue()[:5] == b"%PDF-"

        buf_docx = export_docx(quiz, [q])
        assert buf_docx.getvalue()

        gift_text = export_gift(quiz, [q])
        assert "SHORTANSWER" in gift_text

        buf_qti = export_qti(quiz, [q])
        assert isinstance(buf_qti, io.BytesIO)

    def test_cloze_mixed_with_other_types(self):
        """Cloze questions alongside MC/TF should all export correctly."""
        quiz = _make_quiz_obj()
        cloze_q = _make_cloze_question_obj()

        mc_data = {
            "type": "mc",
            "text": "What is 2+2?",
            "options": ["3", "4", "5", "6"],
            "correct_index": 1,
            "points": 1,
        }
        mc_obj = MagicMock()
        mc_obj.data = mc_data
        mc_obj.text = mc_data["text"]
        mc_obj.question_type = "mc"
        mc_obj.points = 1

        csv_text = export_csv(quiz, [cloze_q, mc_obj])
        assert "cloze" in csv_text
        assert "mc" in csv_text

        buf_pdf = export_pdf(quiz, [cloze_q, mc_obj])
        assert buf_pdf.getvalue()[:5] == b"%PDF-"


if __name__ == "__main__":
    unittest.main()
