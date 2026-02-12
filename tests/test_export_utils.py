"""Tests for shared export utility functions (src/export_utils.py)."""

import io
import unittest

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from src.export_utils import pdf_wrap_text, sanitize_filename


class TestSanitizeFilename(unittest.TestCase):
    """Tests for sanitize_filename()."""

    def test_basic_cleanup(self):
        assert sanitize_filename("My Quiz!") == "My_Quiz"

    def test_special_characters(self):
        assert sanitize_filename("Test: Quiz #1 (v2)") == "Test_Quiz_1_v2"

    def test_empty_string_uses_default(self):
        assert sanitize_filename("") == "export"

    def test_custom_default(self):
        assert sanitize_filename("", default="quiz") == "quiz"
        assert sanitize_filename("", default="lesson_plan") == "lesson_plan"
        assert sanitize_filename("", default="study") == "study"

    def test_max_length_80(self):
        title = "A" * 200
        result = sanitize_filename(title)
        assert len(result) <= 80

    def test_whitespace_only(self):
        assert sanitize_filename("   ") == "export"

    def test_preserves_hyphens_underscores(self):
        assert sanitize_filename("my-quiz_v2") == "my-quiz_v2"

    def test_collapses_multiple_spaces(self):
        assert sanitize_filename("Hello   World") == "Hello_World"

    def test_strips_leading_trailing_whitespace(self):
        assert sanitize_filename("  Hello World  ") == "Hello_World"

    def test_only_special_chars_uses_default(self):
        assert sanitize_filename("!@#$%^&*()") == "export"
        assert sanitize_filename("!@#$%^&*()", default="quiz") == "quiz"


class TestPdfWrapText(unittest.TestCase):
    """Tests for pdf_wrap_text()."""

    def _make_canvas(self):
        """Create a ReportLab canvas for testing."""
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        c.setFont("Helvetica", 10)
        return c, buf

    def test_empty_text_returns_y_unchanged(self):
        c, _ = self._make_canvas()
        y = pdf_wrap_text(c, "", 50, 700, 400, 792)
        assert y == 700

    def test_none_text_returns_y_unchanged(self):
        c, _ = self._make_canvas()
        y = pdf_wrap_text(c, None, 50, 700, 400, 792)
        assert y == 700

    def test_short_text_decreases_y(self):
        c, _ = self._make_canvas()
        y = pdf_wrap_text(c, "Hello world", 50, 700, 400, 792)
        assert y < 700

    def test_long_text_wraps(self):
        c, _ = self._make_canvas()
        long_text = "This is a very long line that should definitely wrap around because it exceeds the maximum width allowed for a single line on the PDF canvas"
        y = pdf_wrap_text(c, long_text, 50, 700, 200, 792)
        # Should have wrapped to multiple lines
        assert y < 700 - 14  # At least 2 lines of descent

    def test_page_break_near_bottom(self):
        c, _ = self._make_canvas()
        # Start very near the bottom (y=55 < 60 threshold)
        y = pdf_wrap_text(c, "Word1 Word2 Word3", 50, 55, 20, 792)
        # Should have triggered a page break — y should be well above starting point
        # (page resets to page_height - 50 = 742, then each word line decreases by 14)
        assert y > 600

    def test_returns_numeric_y(self):
        c, _ = self._make_canvas()
        y = pdf_wrap_text(c, "Test text", 50, 500, 400, 792)
        assert isinstance(y, (int, float))


if __name__ == "__main__":
    unittest.main()
