"""
Rubric export module for QuizWeaver.

Exports rubrics to PDF, DOCX (Word), and CSV formats.
"""

import csv
import io
import json

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

PROFICIENCY_LABELS = ["Beginning", "Developing", "Proficient", "Advanced"]


def _parse_levels(criterion) -> list:
    """Parse the levels JSON field from a RubricCriterion."""
    levels = criterion.levels
    if isinstance(levels, str):
        try:
            return json.loads(levels)
        except (json.JSONDecodeError, ValueError):
            return []
    if isinstance(levels, list):
        return levels
    return []


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------


def export_rubric_csv(rubric, criteria) -> str:
    """Export rubric to CSV format.

    Args:
        rubric: Rubric ORM object.
        criteria: List of RubricCriterion ORM objects, sorted by sort_order.

    Returns:
        CSV string with header row and criteria rows.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    header = ["Criterion", "Description", "Max Points"]
    for label in PROFICIENCY_LABELS:
        header.append(label)
    writer.writerow(header)

    for c in criteria:
        levels = _parse_levels(c)
        level_descs = {}
        for lv in levels:
            label = lv.get("label", "")
            level_descs[label] = lv.get("description", "")

        row = [
            c.criterion or "",
            c.description or "",
            c.max_points or 0,
        ]
        for label in PROFICIENCY_LABELS:
            row.append(level_descs.get(label, ""))
        writer.writerow(row)

    return output.getvalue()


# ---------------------------------------------------------------------------
# DOCX (Word) Export
# ---------------------------------------------------------------------------


def export_rubric_docx(rubric, criteria) -> io.BytesIO:
    """Export rubric to a Word document with a formatted table.

    Args:
        rubric: Rubric ORM object.
        criteria: List of RubricCriterion ORM objects.

    Returns:
        BytesIO buffer containing the .docx file.
    """
    doc = Document()

    # Title
    title_p = doc.add_heading(rubric.title or "Rubric", level=1)
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Table: Criterion | Max Pts | Beginning | Developing | Proficient | Advanced
    col_count = 2 + len(PROFICIENCY_LABELS)  # criterion + max_points + 4 levels
    table = doc.add_table(rows=1, cols=col_count)
    table.style = "Table Grid"

    # Header row
    hdr = table.rows[0].cells
    hdr[0].text = "Criterion"
    hdr[1].text = "Max Pts"
    for i, label in enumerate(PROFICIENCY_LABELS):
        hdr[2 + i].text = label

    # Make header bold
    for cell in hdr:
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(9)

    # Data rows
    for c in criteria:
        levels = _parse_levels(c)
        level_descs = {}
        for lv in levels:
            label = lv.get("label", "")
            level_descs[label] = lv.get("description", "")

        row_cells = table.add_row().cells
        # Criterion name + description
        p = row_cells[0].paragraphs[0]
        run = p.add_run(c.criterion or "")
        run.bold = True
        run.font.size = Pt(9)
        if c.description:
            p.add_run(f"\n{c.description}").font.size = Pt(8)

        row_cells[1].text = str(c.max_points or 0)
        for para in row_cells[1].paragraphs:
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        for i, label in enumerate(PROFICIENCY_LABELS):
            row_cells[2 + i].text = level_descs.get(label, "")
            for para in row_cells[2 + i].paragraphs:
                for run in para.runs:
                    run.font.size = Pt(8)

    # Total points row
    total_pts = sum(c.max_points or 0 for c in criteria)
    p = doc.add_paragraph()
    run = p.add_run(f"Total Points: {total_pts}")
    run.bold = True
    run.font.size = Pt(11)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------


def export_rubric_pdf(rubric, criteria) -> io.BytesIO:
    """Export rubric to a PDF with a table layout.

    Args:
        rubric: Rubric ORM object.
        criteria: List of RubricCriterion ORM objects.

    Returns:
        BytesIO buffer containing the PDF file.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - 50

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, rubric.title or "Rubric")
    y -= 30

    # Column layout info
    col_x = 50
    col_widths = {
        "criterion": 130,
        "pts": 40,
        "levels": (width - 50 - 130 - 40 - 50) / 4,  # Split remaining among 4 levels
    }

    # Draw header
    c.setFont("Helvetica-Bold", 8)
    x = col_x
    c.drawString(x, y, "Criterion")
    x += col_widths["criterion"]
    c.drawString(x, y, "Pts")
    x += col_widths["pts"]
    for label in PROFICIENCY_LABELS:
        c.drawString(x, y, label)
        x += col_widths["levels"]
    y -= 4

    # Header line
    c.line(col_x, y, width - 50, y)
    y -= 14

    # Draw each criterion
    for cr in criteria:
        levels = _parse_levels(cr)
        level_descs = {}
        for lv in levels:
            label = lv.get("label", "")
            level_descs[label] = lv.get("description", "")

        # Calculate needed height (rough estimate)
        needed_height = 60
        if y < needed_height + 50:
            c.showPage()
            y = height - 50

        # Criterion name
        c.setFont("Helvetica-Bold", 8)
        x = col_x
        c.drawString(x, y, (cr.criterion or "")[:30])

        # Points
        c.setFont("Helvetica", 8)
        x = col_x + col_widths["criterion"]
        c.drawString(x, y, str(cr.max_points or 0))

        # Level descriptions
        x = col_x + col_widths["criterion"] + col_widths["pts"]
        c.setFont("Helvetica", 7)
        for label in PROFICIENCY_LABELS:
            desc = level_descs.get(label, "")
            # Truncate long descriptions for PDF
            if len(desc) > 50:
                desc = desc[:47] + "..."
            c.drawString(x, y, desc)
            x += col_widths["levels"]

        # Description below criterion name
        if cr.description:
            y -= 12
            c.setFont("Helvetica", 7)
            desc_text = cr.description
            if len(desc_text) > 80:
                desc_text = desc_text[:77] + "..."
            c.drawString(col_x + 5, y, desc_text)

        y -= 18
        # Separator line
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.line(col_x, y + 6, width - 50, y + 6)
        c.setStrokeColorRGB(0, 0, 0)

    # Total
    y -= 10
    if y < 60:
        c.showPage()
        y = height - 50
    total_pts = sum(cr.max_points or 0 for cr in criteria)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(col_x, y, f"Total Points: {total_pts}")

    c.save()
    buf.seek(0)
    return buf
