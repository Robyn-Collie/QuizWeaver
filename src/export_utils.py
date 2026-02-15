"""
Shared utility functions for QuizWeaver export modules.

Provides common helpers used across export.py, lesson_plan_export.py,
and study_export.py to avoid code duplication.
"""

import re


def sanitize_csv_cell(value):
    """Prevent CSV formula injection by escaping dangerous prefixes.

    Spreadsheet applications (Excel, Google Sheets, LibreOffice Calc) can
    interpret cells starting with =, +, -, @, tab, or carriage return as
    formulas, which may execute arbitrary commands. This function prefixes
    such cells with a single quote to neutralize them.

    Args:
        value: The cell value to sanitize. Non-string values are returned as-is.

    Returns:
        The sanitized cell value.
    """
    if not isinstance(value, str):
        return value
    if value and value[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + value
    return value


def sanitize_filename(title: str, default: str = "export") -> str:
    """Sanitize a title for use as a filename.

    Args:
        title: The raw title string.
        default: Fallback name if the sanitized result is empty.

    Returns:
        A safe filename string (max 80 characters).
    """
    clean = re.sub(r"[^\w\s\-]", "", title)
    clean = re.sub(r"\s+", "_", clean.strip())
    return clean[:80] or default


def pdf_wrap_text(c, text, x, y, max_width, page_height):
    """Draw text with word wrapping on a ReportLab canvas.

    Args:
        c: ReportLab canvas object.
        text: The text to draw.
        x: Left x coordinate.
        y: Starting y coordinate.
        max_width: Maximum line width in points.
        page_height: Page height for page-break detection.

    Returns:
        New y position after drawing text.
    """
    if not text:
        return y
    words = text.split()
    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        if c.stringWidth(test_line, c._fontname, c._fontsize) < max_width:
            line = test_line
        else:
            if y < 60:
                c.showPage()
                y = page_height - 50
            c.drawString(x, y, line)
            y -= 14
            line = word
    if line:
        if y < 60:
            c.showPage()
            y = page_height - 50
        c.drawString(x, y, line)
        y -= 14
    return y
