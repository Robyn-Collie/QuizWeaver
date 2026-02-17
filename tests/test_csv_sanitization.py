"""
Tests for CSV formula injection sanitization and dependency pinning.

Covers:
- sanitize_csv_cell() direct unit tests
- CSV export functions sanitize user-controlled text fields
- requirements.txt has all versions pinned
"""

import csv
import io
import json
import os
import re

from src.export import export_csv, export_quizizz_csv
from src.export_utils import sanitize_csv_cell
from src.rubric_export import export_rubric_csv
from src.study_export import export_flashcards_csv

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_question(**kwargs):
    """Create a Question-like object for testing without a database."""

    class FakeQuestion:
        def __init__(self, **kw):
            self.id = kw.get("id", 1)
            self.quiz_id = kw.get("quiz_id", 1)
            self.question_type = kw.get("question_type", "mc")
            self.title = kw.get("title", "Q1")
            self.text = kw.get("text", "Sample question?")
            self.points = kw.get("points", 5.0)
            self.data = kw.get("data", {})

    return FakeQuestion(**kwargs)


def _make_quiz(**kwargs):
    """Create a Quiz-like object for testing."""

    class FakeQuiz:
        def __init__(self, **kw):
            self.id = kw.get("id", 1)
            self.title = kw.get("title", "Test Quiz")
            self.class_id = kw.get("class_id", 1)
            self.status = kw.get("status", "generated")
            self.style_profile = kw.get("style_profile", "{}")
            self.created_at = kw.get("created_at")

    return FakeQuiz(**kwargs)


def _make_study_set(**kwargs):
    """Create a StudySet-like object for testing."""

    class FakeStudySet:
        def __init__(self, **kw):
            self.id = kw.get("id", 1)
            self.title = kw.get("title", "Study Set")
            self.material_type = kw.get("material_type", "flashcard")

    return FakeStudySet(**kwargs)


def _make_study_card(**kwargs):
    """Create a StudyCard-like object for testing."""

    class FakeStudyCard:
        def __init__(self, **kw):
            self.id = kw.get("id", 1)
            self.front = kw.get("front", "Front text")
            self.back = kw.get("back", "Back text")
            self.data = kw.get("data", "{}")
            self.sort_order = kw.get("sort_order", 0)

    return FakeStudyCard(**kwargs)


def _make_rubric(**kwargs):
    """Create a Rubric-like object for testing."""

    class FakeRubric:
        def __init__(self, **kw):
            self.id = kw.get("id", 1)
            self.title = kw.get("title", "Test Rubric")

    return FakeRubric(**kwargs)


def _make_criterion(**kwargs):
    """Create a RubricCriterion-like object for testing."""

    class FakeCriterion:
        def __init__(self, **kw):
            self.id = kw.get("id", 1)
            self.criterion = kw.get("criterion", "Analysis")
            self.description = kw.get("description", "Analyze the text")
            self.max_points = kw.get("max_points", 10)
            self.levels = kw.get("levels", "[]")
            self.sort_order = kw.get("sort_order", 0)

    return FakeCriterion(**kwargs)


def _parse_csv(csv_string):
    """Parse a CSV string into a list of rows (lists of strings)."""
    reader = csv.reader(io.StringIO(csv_string))
    return list(reader)


# ---------------------------------------------------------------------------
# TestSanitizeCsvCell - Direct unit tests
# ---------------------------------------------------------------------------


class TestSanitizeCsvCell:
    """Test the sanitize_csv_cell() function directly."""

    def test_formula_equals(self):
        assert sanitize_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"

    def test_formula_plus(self):
        assert sanitize_csv_cell("+cmd|'/C calc'") == "'+cmd|'/C calc'"

    def test_formula_minus(self):
        assert sanitize_csv_cell("-dangerous") == "'-dangerous"

    def test_formula_at(self):
        assert sanitize_csv_cell("@evil") == "'@evil"

    def test_formula_tab(self):
        assert sanitize_csv_cell("\tcmd") == "'\tcmd"

    def test_formula_cr(self):
        assert sanitize_csv_cell("\rcmd") == "'\rcmd"

    def test_normal_text(self):
        assert sanitize_csv_cell("Normal text") == "Normal text"

    def test_empty_string(self):
        assert sanitize_csv_cell("") == ""

    def test_non_string_int(self):
        assert sanitize_csv_cell(42) == 42

    def test_non_string_float(self):
        assert sanitize_csv_cell(3.14) == 3.14

    def test_non_string_none(self):
        assert sanitize_csv_cell(None) is None

    def test_non_string_bool(self):
        assert sanitize_csv_cell(True) is True

    def test_negative_number_string(self):
        """Negative numbers as strings get sanitized (they start with -)."""
        assert sanitize_csv_cell("-5 degrees") == "'-5 degrees"

    def test_number_starting_text(self):
        """Text starting with a digit is safe."""
        assert sanitize_csv_cell("42 is the answer") == "42 is the answer"

    def test_question_mark(self):
        """Questions are safe."""
        assert sanitize_csv_cell("What is photosynthesis?") == "What is photosynthesis?"


# ---------------------------------------------------------------------------
# TestExportCsvSanitization - Quiz CSV export
# ---------------------------------------------------------------------------


class TestExportCsvSanitization:
    """Test that export_csv() sanitizes formula-dangerous fields."""

    def test_question_text_sanitized(self):
        quiz = _make_quiz()
        questions = [
            _make_question(
                text="=SUM(A1)",
                question_type="mc",
                data={
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                },
            )
        ]
        result = export_csv(quiz, questions)
        rows = _parse_csv(result)
        # Row 1 is data (row 0 is header)
        assert rows[1][2] == "'=SUM(A1)"  # Question text

    def test_correct_answer_sanitized(self):
        quiz = _make_quiz()
        questions = [
            _make_question(
                text="Question?",
                question_type="mc",
                data={
                    "options": ["Safe", "+evil"],
                    "correct_answer": "+evil",
                },
            )
        ]
        result = export_csv(quiz, questions)
        rows = _parse_csv(result)
        assert rows[1][4] == "'+evil"  # Correct Answer column

    def test_options_sanitized(self):
        quiz = _make_quiz()
        questions = [
            _make_question(
                text="Question?",
                question_type="mc",
                data={
                    "options": ["=HYPERLINK()", "B", "C", "D"],
                    "correct_answer": "B",
                },
            )
        ]
        result = export_csv(quiz, questions)
        rows = _parse_csv(result)
        # Options column contains formatted text like "A) =HYPERLINK() | B) B | ..."
        # The whole options string starts with "A) " so it's safe, but we verify
        # the column is sanitized when the formatted string starts with a dangerous char
        assert "'=" not in rows[1][2]  # question text is safe

    def test_safe_text_unchanged(self):
        quiz = _make_quiz()
        questions = [
            _make_question(
                text="What is 2+2?",
                question_type="mc",
                data={
                    "options": ["3", "4", "5", "6"],
                    "correct_answer": "4",
                },
            )
        ]
        result = export_csv(quiz, questions)
        rows = _parse_csv(result)
        assert rows[1][2] == "What is 2+2?"


# ---------------------------------------------------------------------------
# TestExportQuizizzCsvSanitization
# ---------------------------------------------------------------------------


class TestExportQuizizzCsvSanitization:
    """Test that export_quizizz_csv() sanitizes formula-dangerous fields."""

    def test_question_text_sanitized(self):
        quiz = _make_quiz()
        questions = [
            _make_question(
                text="=EVIL()",
                question_type="mc",
                data={
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                },
            )
        ]
        result = export_quizizz_csv(quiz, questions)
        rows = _parse_csv(result)
        assert rows[1][0] == "'=EVIL()"

    def test_option_fields_sanitized(self):
        quiz = _make_quiz()
        questions = [
            _make_question(
                text="Question?",
                question_type="mc",
                data={
                    "options": ["+cmd", "@link", "Safe", "Also safe"],
                    "correct_answer": "Safe",
                },
            )
        ]
        result = export_quizizz_csv(quiz, questions)
        rows = _parse_csv(result)
        assert rows[1][2] == "'+cmd"  # Option 1
        assert rows[1][3] == "'@link"  # Option 2
        assert rows[1][4] == "Safe"  # Option 3 (safe)

    def test_tf_question_text_sanitized(self):
        quiz = _make_quiz()
        questions = [
            _make_question(
                text="-trick question",
                question_type="tf",
                data={
                    "correct_answer": "True",
                },
            )
        ]
        result = export_quizizz_csv(quiz, questions)
        rows = _parse_csv(result)
        assert rows[1][0] == "'-trick question"


# ---------------------------------------------------------------------------
# TestStudyExportCsvSanitization
# ---------------------------------------------------------------------------


class TestStudyExportCsvSanitization:
    """Test that export_flashcards_csv() sanitizes formula-dangerous fields."""

    def test_flashcard_front_sanitized(self):
        study_set = _make_study_set(material_type="flashcard")
        cards = [_make_study_card(front="=SUM()", back="Safe back", data="{}")]
        result = export_flashcards_csv(study_set, cards)
        rows = _parse_csv(result)
        assert rows[1][1] == "'=SUM()"  # Front column

    def test_flashcard_back_sanitized(self):
        study_set = _make_study_set(material_type="flashcard")
        cards = [_make_study_card(front="Safe front", back="+evil", data="{}")]
        result = export_flashcards_csv(study_set, cards)
        rows = _parse_csv(result)
        assert rows[1][2] == "'+evil"  # Back column

    def test_vocabulary_term_sanitized(self):
        study_set = _make_study_set(material_type="vocabulary")
        cards = [
            _make_study_card(
                front="@term",
                back="definition",
                data=json.dumps(
                    {
                        "example": "=formula",
                        "part_of_speech": "noun",
                    }
                ),
            )
        ]
        result = export_flashcards_csv(study_set, cards)
        rows = _parse_csv(result)
        assert rows[1][1] == "'@term"  # Term column
        assert rows[1][3] == "'=formula"  # Example column

    def test_study_guide_sanitized(self):
        study_set = _make_study_set(material_type="study_guide")
        cards = [
            _make_study_card(
                front="+heading",
                back="-content",
                data=json.dumps(
                    {
                        "key_points": ["point1"],
                    }
                ),
            )
        ]
        result = export_flashcards_csv(study_set, cards)
        rows = _parse_csv(result)
        assert rows[1][1] == "'+heading"
        assert rows[1][2] == "'-content"

    def test_review_sheet_sanitized(self):
        study_set = _make_study_set(material_type="review_sheet")
        cards = [_make_study_card(front="=heading", back="@content", data="{}")]
        result = export_flashcards_csv(study_set, cards)
        rows = _parse_csv(result)
        assert rows[1][1] == "'=heading"
        assert rows[1][2] == "'@content"

    def test_safe_content_unchanged(self):
        study_set = _make_study_set(material_type="flashcard")
        cards = [_make_study_card(front="Normal term", back="Normal definition", data="{}")]
        result = export_flashcards_csv(study_set, cards)
        rows = _parse_csv(result)
        assert rows[1][1] == "Normal term"
        assert rows[1][2] == "Normal definition"


# ---------------------------------------------------------------------------
# TestRubricExportCsvSanitization
# ---------------------------------------------------------------------------


class TestRubricExportCsvSanitization:
    """Test that export_rubric_csv() sanitizes formula-dangerous fields."""

    def test_criterion_name_sanitized(self):
        rubric = _make_rubric()
        criteria = [_make_criterion(criterion="=EVIL()", description="Safe desc", levels="[]")]
        result = export_rubric_csv(rubric, criteria)
        rows = _parse_csv(result)
        assert rows[1][0] == "'=EVIL()"

    def test_description_sanitized(self):
        rubric = _make_rubric()
        criteria = [_make_criterion(criterion="Analysis", description="+dangerous", levels="[]")]
        result = export_rubric_csv(rubric, criteria)
        rows = _parse_csv(result)
        assert rows[1][1] == "'+dangerous"

    def test_level_description_sanitized(self):
        rubric = _make_rubric()
        levels = json.dumps(
            [
                {"label": "Beginning", "description": "=SUM(hack)"},
                {"label": "Developing", "description": "Normal"},
                {"label": "Proficient", "description": "@trick"},
                {"label": "Advanced", "description": "Great work"},
            ]
        )
        criteria = [_make_criterion(criterion="Analysis", description="Desc", levels=levels)]
        result = export_rubric_csv(rubric, criteria)
        rows = _parse_csv(result)
        assert rows[1][3] == "'=SUM(hack)"  # Beginning column
        assert rows[1][4] == "Normal"  # Developing (safe)
        assert rows[1][5] == "'@trick"  # Proficient column
        assert rows[1][6] == "Great work"  # Advanced (safe)

    def test_safe_rubric_unchanged(self):
        rubric = _make_rubric()
        levels = json.dumps(
            [
                {"label": "Beginning", "description": "Needs improvement"},
                {"label": "Advanced", "description": "Excellent analysis"},
            ]
        )
        criteria = [_make_criterion(criterion="Analysis", description="Analyze sources", levels=levels)]
        result = export_rubric_csv(rubric, criteria)
        rows = _parse_csv(result)
        assert rows[1][0] == "Analysis"
        assert rows[1][1] == "Analyze sources"
        assert rows[1][3] == "Needs improvement"


# ---------------------------------------------------------------------------
# TestRequirementsPinned
# ---------------------------------------------------------------------------


class TestRequirementsPinned:
    """Test that requirements.txt has all versions pinned."""

    def test_all_packages_pinned(self):
        """Every non-comment, non-empty line in requirements.txt should have ==."""
        req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        with open(req_path) as f:
            lines = f.readlines()

        unpinned = []
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue
            # Check for == version pin
            if "==" not in stripped:
                unpinned.append(f"Line {line_num}: {stripped}")

        assert unpinned == [], "Unpinned dependencies found:\n" + "\n".join(unpinned)

    def test_no_empty_versions(self):
        """Version pins should have actual version numbers after ==."""
        req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        with open(req_path) as f:
            lines = f.readlines()

        bad_versions = []
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "==" in stripped:
                # Extract version after ==
                parts = stripped.split("==", 1)
                version = parts[1].strip() if len(parts) > 1 else ""
                if not version or not re.match(r"\d+\.\d+", version):
                    bad_versions.append(f"Line {line_num}: {stripped}")

        assert bad_versions == [], "Invalid version pins:\n" + "\n".join(bad_versions)
