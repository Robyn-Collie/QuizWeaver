"""
Lesson plan export module for QuizWeaver.

Exports lesson plans to PDF and DOCX (Word) formats.
"""

import io
import json
import re

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


SECTION_LABELS = {
    "learning_objectives": "Learning Objectives",
    "materials_needed": "Materials Needed",
    "warm_up": "Warm-Up (5-10 min)",
    "direct_instruction": "Direct Instruction (10-15 min)",
    "guided_practice": "Guided Practice (10-15 min)",
    "independent_practice": "Independent Practice (10-15 min)",
    "assessment": "Assessment / Check for Understanding (5 min)",
    "closure": "Closure (3-5 min)",
    "differentiation": "Differentiation",
    "standards_alignment": "Standards Alignment",
}

SECTION_ORDER = [
    "learning_objectives",
    "materials_needed",
    "warm_up",
    "direct_instruction",
    "guided_practice",
    "independent_practice",
    "assessment",
    "closure",
    "differentiation",
    "standards_alignment",
]


def _parse_plan_data(lesson_plan) -> dict:
    """Parse the JSON plan_data field from a LessonPlan."""
    data = lesson_plan.plan_data
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return {}
    if isinstance(data, dict):
        return data
    return {}


def _sanitize_filename(title: str) -> str:
    """Sanitize a title for use as a filename."""
    clean = re.sub(r"[^\w\s\-]", "", title)
    clean = re.sub(r"\s+", "_", clean.strip())
    return clean[:80] or "lesson_plan"


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------

def _pdf_wrap_text(c, text, x, y, max_width, page_height):
    """Draw text with word wrapping. Returns new y position."""
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


def export_lesson_plan_pdf(lesson_plan) -> io.BytesIO:
    """Export a lesson plan to PDF.

    Args:
        lesson_plan: LessonPlan ORM object.

    Returns:
        BytesIO buffer containing the PDF file.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - 50

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, y, lesson_plan.title or "Lesson Plan")
    y -= 24

    # Metadata line
    c.setFont("Helvetica", 10)
    meta_parts = []
    if lesson_plan.grade_level:
        meta_parts.append(f"Grade: {lesson_plan.grade_level}")
    if lesson_plan.duration_minutes:
        meta_parts.append(f"Duration: {lesson_plan.duration_minutes} min")
    if meta_parts:
        c.drawCentredString(width / 2, y, " | ".join(meta_parts))
        y -= 16

    # AI draft notice
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(
        width / 2, y,
        "AI-Generated Draft - Review and edit all sections before classroom use."
    )
    y -= 24

    # Sections
    plan_data = _parse_plan_data(lesson_plan)

    for section_key in SECTION_ORDER:
        content = plan_data.get(section_key, "")
        if not content:
            continue

        label = SECTION_LABELS.get(section_key, section_key.replace("_", " ").title())

        # Check page break
        if y < 100:
            c.showPage()
            y = height - 50

        # Section heading
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, label)
        y -= 18

        # Section content
        c.setFont("Helvetica", 10)
        y = _pdf_wrap_text(c, content, 60, y, width - 120, height)
        y -= 12

    c.save()
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# DOCX (Word) Export
# ---------------------------------------------------------------------------

def export_lesson_plan_docx(lesson_plan) -> io.BytesIO:
    """Export a lesson plan to a Word document.

    Args:
        lesson_plan: LessonPlan ORM object.

    Returns:
        BytesIO buffer containing the .docx file.
    """
    doc = Document()

    # Title
    title_p = doc.add_heading(lesson_plan.title or "Lesson Plan", level=1)
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Metadata
    meta_parts = []
    if lesson_plan.grade_level:
        meta_parts.append(f"Grade Level: {lesson_plan.grade_level}")
    if lesson_plan.duration_minutes:
        meta_parts.append(f"Duration: {lesson_plan.duration_minutes} minutes")
    if meta_parts:
        p = doc.add_paragraph(" | ".join(meta_parts))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.size = Pt(10)

    # AI draft notice
    p = doc.add_paragraph(
        "AI-Generated Draft - Review and edit all sections before classroom use."
    )
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:
        run.font.size = Pt(8)
        run.italic = True

    # Sections
    plan_data = _parse_plan_data(lesson_plan)

    for section_key in SECTION_ORDER:
        content = plan_data.get(section_key, "")
        if not content:
            continue

        label = SECTION_LABELS.get(section_key, section_key.replace("_", " ").title())

        doc.add_heading(label, level=2)
        doc.add_paragraph(content)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
