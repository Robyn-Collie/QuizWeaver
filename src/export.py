"""
Quiz export module for QuizWeaver.

Exports quizzes to CSV, DOCX (Word), GIFT (Moodle), PDF, and QTI (Canvas) formats.
Handles normalization of different question data shapes from
mock vs real LLM providers.
"""

import csv
import io
import json
import re
import uuid
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# Type normalization map: long form -> short form
TYPE_MAP = {
    "multiple_choice": "mc",
    "true_false": "tf",
    "short_answer": "short_answer",
    "fill_in": "fill_in",
    "fill_in_the_blank": "fill_in",
    "matching": "matching",
    "ordering": "ordering",
    "essay": "essay",
}


def normalize_question(question_obj, index: int) -> Dict[str, Any]:
    """Normalize a Question ORM object into a clean dict.

    Handles different data shapes from mock vs real LLM providers:
    - Type field: "multiple_choice" vs "mc", "true_false" vs "tf"
    - Answer: correct_index (int) vs correct_answer/answer (string)
    - Matching: prompt_items/response_items vs matches [{term, definition}]
    - Text: "text" vs "question" field

    Args:
        question_obj: Question ORM object with .data, .text, .question_type, etc.
        index: 0-based question index for numbering.

    Returns:
        Normalized dict with consistent field names.
    """
    # Parse data field if stored as JSON string
    data = question_obj.data
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            data = {}
    if not isinstance(data, dict):
        data = {}

    # Resolve type
    raw_type = question_obj.question_type or data.get("type", "mc")
    q_type = TYPE_MAP.get(raw_type, raw_type)

    # Resolve text: prefer ORM .text, then data.text, then data.question
    text = question_obj.text or data.get("text") or data.get("question", "")

    # Resolve options
    options = data.get("options", [])
    # Handle Gemini-style options as list of dicts {id, text}
    if options and isinstance(options[0], dict):
        options = [opt.get("text", str(opt)) for opt in options]

    # Resolve correct answer
    correct_answer = _resolve_correct_answer(data, options, q_type)

    # Resolve matching pairs
    matches = _resolve_matches(data)

    # Resolve ordering fields
    ordering_items = data.get("items", [])
    ordering_correct_order = data.get("correct_order", [])
    ordering_instructions = data.get("instructions", "")

    # Resolve short answer fields
    expected_answer = data.get("expected_answer", "")
    acceptable_answers = data.get("acceptable_answers", [])
    rubric_hint = data.get("rubric_hint", "")

    # For short_answer, use expected_answer as correct_answer if not already set
    if q_type == "short_answer" and not correct_answer and expected_answer:
        correct_answer = expected_answer

    return {
        "number": index + 1,
        "type": q_type,
        "text": text,
        "options": options,
        "correct_answer": correct_answer,
        "matches": matches,
        "ordering_items": ordering_items,
        "ordering_correct_order": ordering_correct_order,
        "ordering_instructions": ordering_instructions,
        "expected_answer": expected_answer,
        "acceptable_answers": acceptable_answers,
        "rubric_hint": rubric_hint,
        "points": question_obj.points or data.get("points", 0),
        "cognitive_level": data.get("cognitive_level"),
        "cognitive_framework": data.get("cognitive_framework"),
        "image_description": data.get("image_description") or data.get("image_ref"),
    }


def _resolve_correct_answer(
    data: dict, options: list, q_type: str
) -> str:
    """Resolve the correct answer string from various data shapes."""
    # Try direct answer fields first
    answer = data.get("correct_answer") or data.get("answer")
    if answer is not None:
        return str(answer)

    # Fall back to correct_index into options
    correct_index = data.get("correct_index")
    if correct_index is not None and options:
        try:
            idx = int(correct_index)
            if 0 <= idx < len(options):
                return str(options[idx])
        except (ValueError, TypeError):
            pass

    # For T/F questions, try is_true field
    if q_type == "tf":
        is_true = data.get("is_true")
        if is_true is not None:
            return "True" if is_true else "False"

    return ""


def _resolve_matches(data: dict) -> List[Dict[str, str]]:
    """Resolve matching pairs from various data shapes."""
    # Gemini style: matches = [{term, definition}]
    matches = data.get("matches")
    if matches and isinstance(matches, list):
        result = []
        for m in matches:
            if isinstance(m, dict):
                result.append({
                    "term": m.get("term", ""),
                    "definition": m.get("definition", ""),
                })
        if result:
            return result

    # Mock style: prompt_items + response_items + correct_matches
    prompts = data.get("prompt_items", [])
    responses = data.get("response_items", [])
    correct_matches = data.get("correct_matches", {})
    if prompts and responses:
        result = []
        for i, prompt in enumerate(prompts):
            match_idx = correct_matches.get(str(i), i)
            definition = responses[match_idx] if match_idx < len(responses) else ""
            result.append({"term": prompt, "definition": definition})
        return result

    return []


def _escape_gift(text: str) -> str:
    """Escape special GIFT format characters."""
    for char in ["~", "=", "#", "{", "}", ":"]:
        text = text.replace(char, "\\" + char)
    return text


def _sanitize_filename(title: str) -> str:
    """Sanitize a quiz title for use as a filename."""
    # Remove special chars, keep alphanumeric, spaces, hyphens, underscores
    clean = re.sub(r"[^\w\s\-]", "", title)
    clean = re.sub(r"\s+", "_", clean.strip())
    return clean[:80] or "quiz"


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------


def export_csv(quiz, questions, style_profile: Optional[dict] = None) -> str:
    """Export quiz questions to CSV format.

    Args:
        quiz: Quiz ORM object.
        questions: List of Question ORM objects.
        style_profile: Parsed style profile dict (optional).

    Returns:
        CSV string with headers and question rows.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "#", "Type", "Question", "Options", "Correct Answer",
        "Points", "Cognitive Level", "Framework",
    ])

    for i, q in enumerate(questions):
        nq = normalize_question(q, i)
        options_str = _format_options_csv(nq)
        writer.writerow([
            nq["number"],
            nq["type"],
            nq["text"],
            options_str,
            nq["correct_answer"],
            nq["points"],
            nq["cognitive_level"] or "",
            nq["cognitive_framework"] or "",
        ])

    return output.getvalue()


def _format_options_csv(nq: dict) -> str:
    """Format options for CSV column."""
    if nq["type"] == "matching" and nq["matches"]:
        return " | ".join(
            f"{m['term']} -> {m['definition']}" for m in nq["matches"]
        )
    if nq["type"] == "ordering" and nq.get("ordering_items"):
        return ", ".join(nq["ordering_items"])
    if nq["type"] == "short_answer":
        answers = nq.get("acceptable_answers", [])
        if answers:
            return " | ".join(answers)
        return nq.get("expected_answer", "")
    if nq["type"] == "tf":
        return "True | False"
    if nq["options"]:
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        parts = []
        for j, opt in enumerate(nq["options"]):
            letter = letters[j] if j < len(letters) else str(j)
            parts.append(f"{letter}) {opt}")
        return " | ".join(parts)
    return ""


# ---------------------------------------------------------------------------
# DOCX (Word) Export
# ---------------------------------------------------------------------------


def export_docx(quiz, questions, style_profile: Optional[dict] = None) -> io.BytesIO:
    """Export quiz to a Word document.

    Args:
        quiz: Quiz ORM object.
        questions: List of Question ORM objects.
        style_profile: Parsed style profile dict (optional).

    Returns:
        BytesIO buffer containing the .docx file.
    """
    if style_profile is None:
        style_profile = {}

    doc = Document()

    # Title
    title = doc.add_heading(quiz.title or "Quiz", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Info block
    _add_docx_info(doc, quiz, style_profile)

    # Questions section
    doc.add_heading("Questions", level=2)

    normalized = []
    for i, q in enumerate(questions):
        nq = normalize_question(q, i)
        normalized.append(nq)
        _add_docx_question(doc, nq)

    # Answer key (new page)
    doc.add_page_break()
    doc.add_heading("Answer Key", level=2)
    _add_docx_answer_key(doc, normalized)

    # Save to buffer
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def _add_docx_info(doc, quiz, style_profile: dict):
    """Add quiz metadata info block to the document."""
    info_lines = []

    sol = style_profile.get("sol_standards")
    if sol:
        if isinstance(sol, list):
            sol = ", ".join(sol)
        info_lines.append(f"Standards: {sol}")

    framework = style_profile.get("cognitive_framework")
    if framework:
        info_lines.append(f"Framework: {framework.capitalize()}")

    difficulty = style_profile.get("difficulty")
    if difficulty:
        info_lines.append(f"Difficulty: {difficulty}/5")

    provider = style_profile.get("provider")
    if provider:
        info_lines.append(f"Generated by: {provider}")

    created = getattr(quiz, "created_at", None)
    if created:
        if isinstance(created, datetime):
            info_lines.append(f"Date: {created.strftime('%Y-%m-%d')}")
        else:
            info_lines.append(f"Date: {created}")

    if info_lines:
        for line in info_lines:
            p = doc.add_paragraph(line)
            p.style.font.size = Pt(10)


def _add_docx_question(doc, nq: dict):
    """Add a single question to the Word document."""
    # Question header: "1. [MC] (5 pts) - Remember"
    header_parts = [f"{nq['number']}."]
    header_parts.append(f"[{nq['type'].upper()}]")
    header_parts.append(f"({nq['points']} pts)")
    if nq["cognitive_level"]:
        header_parts.append(f"- {nq['cognitive_level']}")

    p = doc.add_paragraph()
    run = p.add_run(" ".join(header_parts))
    run.bold = True
    run.font.size = Pt(11)

    # Question text
    doc.add_paragraph(nq["text"])

    # Answer area based on type
    if nq["type"] == "mc":
        _add_docx_mc_options(doc, nq)
    elif nq["type"] == "tf":
        _add_docx_tf_options(doc, nq)
    elif nq["type"] in ("fill_in",):
        doc.add_paragraph("Answer: ____________________")
    elif nq["type"] == "short_answer":
        if nq.get("rubric_hint"):
            p = doc.add_paragraph()
            run = p.add_run(f"(Hint: {nq['rubric_hint']})")
            run.italic = True
            run.font.size = Pt(9)
        doc.add_paragraph("_" * 60)
        doc.add_paragraph("_" * 60)
    elif nq["type"] == "ordering" and nq.get("ordering_items"):
        _add_docx_ordering(doc, nq)
    elif nq["type"] == "essay":
        for _ in range(4):
            doc.add_paragraph("_" * 60)
    elif nq["type"] == "matching" and nq["matches"]:
        _add_docx_matching(doc, nq)

    # Spacer
    doc.add_paragraph("")


def _add_docx_mc_options(doc, nq: dict):
    """Add multiple choice options with correct answer bolded."""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for j, opt in enumerate(nq["options"]):
        letter = letters[j] if j < len(letters) else str(j)
        p = doc.add_paragraph(style="List Bullet")
        text = f"{letter}. {opt}"
        run = p.add_run(text)
        if str(opt) == nq["correct_answer"]:
            run.bold = True


def _add_docx_tf_options(doc, nq: dict):
    """Add True/False options with correct bolded."""
    for val in ["True", "False"]:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(val)
        if val == nq["correct_answer"]:
            run.bold = True


def _add_docx_matching(doc, nq: dict):
    """Add a matching question as a simple table."""
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Term"
    hdr[1].text = "Definition"
    for m in nq["matches"]:
        row = table.add_row().cells
        row[0].text = m["term"]
        row[1].text = m["definition"]


def _add_docx_ordering(doc, nq: dict):
    """Add an ordering question with numbered blanks for student response."""
    if nq.get("ordering_instructions"):
        p = doc.add_paragraph()
        run = p.add_run(nq["ordering_instructions"])
        run.italic = True
        run.font.size = Pt(9)

    # Show items in a scrambled display order (reverse of correct)
    items = nq.get("ordering_items", [])
    import random as _rng
    display_order = list(range(len(items)))
    # Use a deterministic shuffle based on question number
    _rng.Random(nq["number"]).shuffle(display_order)

    for rank, idx in enumerate(display_order):
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(f"___  {items[idx]}")


def _add_docx_answer_key(doc, normalized: list):
    """Add answer key section listing all correct answers."""
    for nq in normalized:
        if nq["type"] == "matching" and nq["matches"]:
            answer_text = "; ".join(
                f"{m['term']} -> {m['definition']}" for m in nq["matches"]
            )
        elif nq["type"] == "ordering" and nq.get("ordering_items"):
            correct_order = nq.get("ordering_correct_order", [])
            items = nq.get("ordering_items", [])
            ordered = []
            for idx in correct_order:
                if 0 <= idx < len(items):
                    ordered.append(items[idx])
            answer_text = " -> ".join(ordered) if ordered else "(see items)"
        elif nq["type"] == "short_answer":
            parts = [nq.get("expected_answer", "")]
            alts = nq.get("acceptable_answers", [])
            if alts:
                parts.append(f"(also: {', '.join(alts)})")
            answer_text = " ".join(parts)
        else:
            answer_text = nq["correct_answer"]

        p = doc.add_paragraph()
        run = p.add_run(f"{nq['number']}. ")
        run.bold = True
        p.add_run(answer_text or "(see rubric)")


# ---------------------------------------------------------------------------
# GIFT Export (Moodle / Canvas import format)
# ---------------------------------------------------------------------------


def export_gift(quiz, questions) -> str:
    """Export quiz to GIFT format for Moodle/Canvas import.

    Args:
        quiz: Quiz ORM object.
        questions: List of Question ORM objects.

    Returns:
        GIFT format string.
    """
    lines = []
    # Add quiz title as a comment
    lines.append(f"// {quiz.title or 'Quiz'}")
    lines.append(f"// Exported from QuizWeaver")
    lines.append("")

    for i, q in enumerate(questions):
        nq = normalize_question(q, i)
        gift_str = _format_gift_question(nq)
        lines.append(gift_str)
        lines.append("")

    return "\n".join(lines)


def _format_gift_question(nq: dict) -> str:
    """Format a single normalized question as GIFT."""
    title = f"Q{nq['number']}"
    escaped_text = _escape_gift(nq["text"])

    if nq["type"] == "mc":
        return _gift_mc(title, escaped_text, nq)
    elif nq["type"] == "tf":
        return _gift_tf(title, escaped_text, nq)
    elif nq["type"] == "short_answer":
        return _gift_short_answer(title, escaped_text, nq)
    elif nq["type"] == "fill_in":
        return _gift_short(title, escaped_text, nq)
    elif nq["type"] == "matching":
        return _gift_matching(title, escaped_text, nq)
    elif nq["type"] == "ordering":
        return _gift_ordering(title, escaped_text, nq)
    elif nq["type"] == "essay":
        return _gift_essay(title, escaped_text)
    else:
        # Default: treat as short answer
        return _gift_short(title, escaped_text, nq)


def _gift_mc(title: str, text: str, nq: dict) -> str:
    """Format MC question in GIFT."""
    parts = [f"::{title}:: {text} {{"]
    for opt in nq["options"]:
        escaped_opt = _escape_gift(str(opt))
        if str(opt) == nq["correct_answer"]:
            parts.append(f"  ={escaped_opt}")
        else:
            parts.append(f"  ~{escaped_opt}")
    parts.append("}")
    return "\n".join(parts)


def _gift_tf(title: str, text: str, nq: dict) -> str:
    """Format T/F question in GIFT."""
    answer = nq["correct_answer"].upper() if nq["correct_answer"] else "TRUE"
    return f"::{title}:: {text} {{{answer}}}"


def _gift_short(title: str, text: str, nq: dict) -> str:
    """Format short answer / fill-in question in GIFT."""
    answer = _escape_gift(nq["correct_answer"]) if nq["correct_answer"] else ""
    if answer:
        return f"::{title}:: {text} {{={answer}}}"
    return f"::{title}:: {text} {{}}"


def _gift_matching(title: str, text: str, nq: dict) -> str:
    """Format matching question in GIFT."""
    parts = [f"::{title}:: {text} {{"]
    for m in nq["matches"]:
        term = _escape_gift(m["term"])
        defn = _escape_gift(m["definition"])
        parts.append(f"  ={term} -> {defn}")
    parts.append("}")
    return "\n".join(parts)


def _gift_short_answer(title: str, text: str, nq: dict) -> str:
    """Format short answer question in GIFT with multiple acceptable answers."""
    answers = []
    expected = nq.get("expected_answer", "")
    if expected:
        answers.append(expected)
    for alt in nq.get("acceptable_answers", []):
        if alt and alt not in answers:
            answers.append(alt)
    if not answers and nq.get("correct_answer"):
        answers.append(nq["correct_answer"])

    if answers:
        answer_parts = " ".join(f"={_escape_gift(a)}" for a in answers)
        return f"::{title}:: {text} {{{answer_parts}}}"
    return f"::{title}:: {text} {{}}"


def _gift_ordering(title: str, text: str, nq: dict) -> str:
    """Format ordering question in GIFT.

    Moodle ordering format: each item gets a numbered position.
    Uses matching-style format where items map to their position number.
    """
    items = nq.get("ordering_items", [])
    correct_order = nq.get("ordering_correct_order", [])

    if not items:
        return f"::{title}:: {text} {{}}"

    # Build matching-style pairs: item -> position number
    parts = [f"::{title}:: {text} {{"]
    for pos, idx in enumerate(correct_order):
        if 0 <= idx < len(items):
            item = _escape_gift(items[idx])
            parts.append(f"  ={item} -> {pos + 1}")
    parts.append("}")
    return "\n".join(parts)


def _gift_essay(title: str, text: str) -> str:
    """Format essay question in GIFT."""
    return f"::{title}:: {text} {{}}"


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------


def export_pdf(quiz, questions, style_profile: Optional[dict] = None) -> io.BytesIO:
    """Export quiz to a PDF document.

    Args:
        quiz: Quiz ORM object.
        questions: List of Question ORM objects.
        style_profile: Parsed style profile dict (optional).

    Returns:
        BytesIO buffer containing the PDF file.
    """
    if style_profile is None:
        style_profile = {}

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - 50

    # --- Title page ---
    c.setFont("Helvetica-Bold", 18)
    title = quiz.title or "Quiz"
    c.drawCentredString(width / 2, y, title)
    y -= 30

    # Info block
    c.setFont("Helvetica", 10)
    info_lines = _pdf_info_lines(quiz, style_profile)
    for line in info_lines:
        c.drawCentredString(width / 2, y, line)
        y -= 14
    y -= 20

    # --- Questions ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Questions")
    y -= 24

    normalized = []
    for i, q in enumerate(questions):
        nq = normalize_question(q, i)
        normalized.append(nq)
        y = _pdf_draw_question(c, nq, y, width, height)

    # --- Answer Key (new page) ---
    c.showPage()
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Answer Key")
    y -= 24

    c.setFont("Helvetica", 10)
    for nq in normalized:
        if y < 60:
            c.showPage()
            y = height - 50
        answer = _pdf_answer_text(nq)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, f"{nq['number']}.")
        c.setFont("Helvetica", 10)
        c.drawString(72, y, answer)
        y -= 16

    c.save()
    buf.seek(0)
    return buf


def _pdf_info_lines(quiz, style_profile: dict) -> List[str]:
    """Build info lines for the PDF title area."""
    lines = []
    sol = style_profile.get("sol_standards")
    if sol:
        if isinstance(sol, list):
            sol = ", ".join(sol)
        lines.append(f"Standards: {sol}")

    framework = style_profile.get("cognitive_framework")
    if framework:
        lines.append(f"Framework: {framework.capitalize()}")

    difficulty = style_profile.get("difficulty")
    if difficulty:
        lines.append(f"Difficulty: {difficulty}/5")

    provider = style_profile.get("provider")
    if provider:
        lines.append(f"Generated by: {provider}")

    created = getattr(quiz, "created_at", None)
    if created:
        if isinstance(created, datetime):
            lines.append(f"Date: {created.strftime('%Y-%m-%d')}")
        else:
            lines.append(f"Date: {created}")

    return lines


def _pdf_draw_question(c, nq: dict, y: float, page_width: float, page_height: float) -> float:
    """Draw a single question on the PDF canvas. Returns new y position."""
    # Check for page break
    if y < 120:
        c.showPage()
        y = page_height - 50

    # Header line: "1. [MC] (5 pts) - Remember"
    header_parts = [f"{nq['number']}."]
    header_parts.append(f"[{nq['type'].upper()}]")
    header_parts.append(f"({nq['points']} pts)")
    if nq["cognitive_level"]:
        header_parts.append(f"- {nq['cognitive_level']}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, " ".join(header_parts))
    y -= 16

    # Question text with wrapping
    c.setFont("Helvetica", 10)
    y = _pdf_draw_wrapped_text(c, nq["text"], 50, y, page_width - 100, page_height)

    # Image description if present
    if nq.get("image_description"):
        c.setFont("Helvetica-Oblique", 9)
        y = _pdf_draw_wrapped_text(
            c, f"[Image: {nq['image_description']}]", 60, y, page_width - 120, page_height
        )
        c.setFont("Helvetica", 10)

    # Options based on type
    if nq["type"] == "mc" and nq["options"]:
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for j, opt in enumerate(nq["options"]):
            if y < 60:
                c.showPage()
                y = page_height - 50
            letter_label = letters[j] if j < len(letters) else str(j)
            c.drawString(70, y, f"{letter_label}. {opt}")
            y -= 14
    elif nq["type"] == "tf":
        for val in ["True", "False"]:
            if y < 60:
                c.showPage()
                y = page_height - 50
            c.drawString(70, y, f"o  {val}")
            y -= 14
    elif nq["type"] in ("fill_in",):
        c.drawString(70, y, "Answer: ____________________")
        y -= 14
    elif nq["type"] == "short_answer":
        if nq.get("rubric_hint"):
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(70, y, f"(Hint: {nq['rubric_hint']})")
            y -= 14
            c.setFont("Helvetica", 10)
        c.drawString(70, y, "_" * 60)
        y -= 14
        c.drawString(70, y, "_" * 60)
        y -= 14
    elif nq["type"] == "ordering" and nq.get("ordering_items"):
        if nq.get("ordering_instructions"):
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(70, y, nq["ordering_instructions"])
            y -= 14
            c.setFont("Helvetica", 10)
        items = nq["ordering_items"]
        import random as _rng
        display_order = list(range(len(items)))
        _rng.Random(nq["number"]).shuffle(display_order)
        for rank, idx in enumerate(display_order):
            if y < 60:
                c.showPage()
                y = page_height - 50
            c.drawString(70, y, f"___  {items[idx]}")
            y -= 14
    elif nq["type"] == "essay":
        for _ in range(4):
            if y < 60:
                c.showPage()
                y = page_height - 50
            c.drawString(70, y, "_" * 60)
            y -= 14
    elif nq["type"] == "matching" and nq["matches"]:
        for m in nq["matches"]:
            if y < 60:
                c.showPage()
                y = page_height - 50
            c.drawString(70, y, f"{m['term']}  ->  _______________")
            y -= 14

    y -= 10  # Spacer between questions
    return y


def _pdf_draw_wrapped_text(c, text: str, x: float, y: float, max_width: float, page_height: float) -> float:
    """Draw text with simple word wrapping. Returns new y position."""
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


def _pdf_answer_text(nq: dict) -> str:
    """Get answer text for the answer key."""
    if nq["type"] == "matching" and nq["matches"]:
        return "; ".join(f"{m['term']} -> {m['definition']}" for m in nq["matches"])
    if nq["type"] == "ordering" and nq.get("ordering_items"):
        correct_order = nq.get("ordering_correct_order", [])
        items = nq.get("ordering_items", [])
        ordered = [items[idx] for idx in correct_order if 0 <= idx < len(items)]
        return " -> ".join(ordered) if ordered else "(see items)"
    if nq["type"] == "short_answer":
        parts = [nq.get("expected_answer", nq.get("correct_answer", ""))]
        alts = nq.get("acceptable_answers", [])
        if alts:
            parts.append(f"(also: {', '.join(alts)})")
        return " ".join(p for p in parts if p)
    return nq["correct_answer"] or "(see rubric)"


# ---------------------------------------------------------------------------
# QTI Export (Canvas-compatible)
# ---------------------------------------------------------------------------

# QTI 1.2 XML Templates

_QTI_MANIFEST_START = """<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="man_{manifest_id}" xmlns="http://www.imsglobal.org/xsd/imscp_v1p1">
  <metadata>
    <schema>IMS Content</schema>
    <schemaversion>1.1.3</schemaversion>
  </metadata>
  <organizations />
  <resources>
    <resource identifier="res_{assessment_id}" type="imsqti_xmlv1p2/imscc_xmlv1p1/assessment">
      <file href="{assessment_filename}"/>
    </resource>
  </resources>
</manifest>"""

_QTI_ASSESSMENT_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<questestinterop xmlns="http://www.imsglobal.org/xsd/ims_qtiasiv1p2">
  <assessment ident="{assessment_id}" title="{title}">
    <qtimetadata>
      <qtimetadatafield>
        <fieldlabel>qmd_assessmenttype</fieldlabel>
        <fieldentry>Examination</fieldentry>
      </qtimetadatafield>
    </qtimetadata>
    <section ident="root_section">
"""

_QTI_ASSESSMENT_FOOTER = """    </section>
  </assessment>
</questestinterop>"""


def _xml_escape(text: str) -> str:
    """Escape text for safe inclusion in XML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _qti_mc_item(ident: str, nq: dict) -> str:
    """Build a QTI MC item XML string from normalized question data."""
    text = _xml_escape(nq["text"])
    points = nq["points"] or 5

    # Find correct option index
    correct_idx = 0
    for i, opt in enumerate(nq["options"]):
        if str(opt) == nq["correct_answer"]:
            correct_idx = i
            break

    response_labels = ""
    for idx, opt in enumerate(nq["options"]):
        response_labels += (
            f'          <response_label ident="opt_{idx}">'
            f'<material><mattext texttype="text/plain">{_xml_escape(str(opt))}</mattext></material>'
            f'</response_label>\n'
        )

    return f"""      <item ident="{ident}" title="Q{nq['number']}">
        <itemmetadata>
          <qtimetadata>
            <qtimetadatafield>
              <fieldlabel>question_type</fieldlabel>
              <fieldentry>multiple_choice_question</fieldentry>
            </qtimetadatafield>
            <qtimetadatafield>
              <fieldlabel>points_possible</fieldlabel>
              <fieldentry>{points}</fieldentry>
            </qtimetadatafield>
          </qtimetadata>
        </itemmetadata>
        <presentation>
          <material><mattext texttype="text/html">{text}</mattext></material>
          <response_lid ident="response1" rcardinality="Single">
            <render_choice>
{response_labels}            </render_choice>
          </response_lid>
        </presentation>
        <resprocessing>
          <outcomes><decvar maxvalue="100" minvalue="0" varname="SCORE" vartype="Decimal"/></outcomes>
          <respcondition continue="No">
            <conditionvar><varequal respident="response1">opt_{correct_idx}</varequal></conditionvar>
            <setvar action="Set" varname="SCORE">{points}</setvar>
          </respcondition>
        </resprocessing>
      </item>"""


def _qti_tf_item(ident: str, nq: dict) -> str:
    """Build a QTI True/False item (implemented as MC with True/False options)."""
    is_true = nq["correct_answer"].strip().lower() == "true" if nq["correct_answer"] else True
    # Reuse MC with True/False options
    tf_nq = dict(nq)
    tf_nq["options"] = ["True", "False"]
    tf_nq["correct_answer"] = "True" if is_true else "False"
    return _qti_mc_item(ident, tf_nq)


def _qti_essay_item(ident: str, nq: dict) -> str:
    """Build a QTI essay item XML string."""
    text = _xml_escape(nq["text"])
    points = nq["points"] or 5

    return f"""      <item ident="{ident}" title="Q{nq['number']}">
        <itemmetadata>
          <qtimetadata>
            <qtimetadatafield>
              <fieldlabel>question_type</fieldlabel>
              <fieldentry>essay_question</fieldentry>
            </qtimetadatafield>
            <qtimetadatafield>
              <fieldlabel>points_possible</fieldlabel>
              <fieldentry>{points}</fieldentry>
            </qtimetadatafield>
          </qtimetadata>
        </itemmetadata>
        <presentation>
          <material><mattext texttype="text/html">{text}</mattext></material>
          <response_str ident="response1" rcardinality="Single">
            <render_fib><response_label ident="answer1"/></render_fib>
          </response_str>
        </presentation>
        <resprocessing>
          <outcomes><decvar maxvalue="100" minvalue="0" varname="SCORE" vartype="Decimal"/></outcomes>
          <respcondition continue="No">
            <conditionvar><other/></conditionvar>
          </respcondition>
        </resprocessing>
      </item>"""


def export_qti(quiz, questions) -> io.BytesIO:
    """Export quiz as a QTI 1.2 ZIP package (Canvas-compatible).

    Args:
        quiz: Quiz ORM object.
        questions: List of Question ORM objects.

    Returns:
        BytesIO buffer containing the .zip file.
    """
    assessment_id = uuid.uuid4().hex
    manifest_id = uuid.uuid4().hex
    title = _xml_escape(quiz.title or "Quiz")
    assessment_filename = f"{assessment_id}.xml"

    # Build item XML for each question
    item_parts = []
    for i, q in enumerate(questions):
        nq = normalize_question(q, i)
        ident = f"q{nq['number']}"

        if nq["type"] == "mc":
            item_parts.append(_qti_mc_item(ident, nq))
        elif nq["type"] == "tf":
            item_parts.append(_qti_tf_item(ident, nq))
        elif nq["type"] == "essay":
            item_parts.append(_qti_essay_item(ident, nq))
        elif nq["type"] in ("short_answer", "fill_in"):
            # Treat as essay for QTI
            item_parts.append(_qti_essay_item(ident, nq))
        else:
            # Default: MC if options exist, else essay
            if nq["options"]:
                item_parts.append(_qti_mc_item(ident, nq))
            else:
                item_parts.append(_qti_essay_item(ident, nq))

    # Assemble assessment XML
    assessment_xml = _QTI_ASSESSMENT_HEADER.format(
        assessment_id=assessment_id, title=title
    )
    assessment_xml += "\n".join(item_parts)
    assessment_xml += "\n" + _QTI_ASSESSMENT_FOOTER

    # Assemble manifest XML
    manifest_xml = _QTI_MANIFEST_START.format(
        manifest_id=manifest_id,
        assessment_id=assessment_id,
        assessment_filename=assessment_filename,
    )

    # Write to ZIP in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("imsmanifest.xml", manifest_xml)
        zf.writestr(assessment_filename, assessment_xml)

    buf.seek(0)
    return buf
