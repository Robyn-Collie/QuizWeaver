"""
Deterministic pre-validation layer for quiz questions.

Runs BEFORE the LLM critic call, saving tokens on obvious structural
failures.  Pure functions only — no LLM calls, no database access.

Does NOT enforce question-type diversity.  If the teacher wants 100%
multiple-choice, that is a valid configuration choice.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Recognised question type identifiers (internal canonical forms)
VALID_TYPES = {"mc", "tf", "short_answer", "fill_in_blank", "matching", "essay", "ordering", "ma", "stimulus", "cloze"}


def pre_validate_questions(
    questions: List[Dict[str, Any]],
    teacher_config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Validate each question structurally and return per-question results.

    Args:
        questions: List of question dicts from the generator.
        teacher_config: Optional dict with keys like ``allowed_types``
            (list of permitted type strings).

    Returns:
        List of result dicts, one per question, in the same order::

            {
                "index": int,
                "passed": bool,
                "issues": [str, ...],
                "fact_warnings": [str, ...],
            }
    """
    allowed_types = None
    if teacher_config:
        allowed_types = teacher_config.get("allowed_types")
        if allowed_types:
            allowed_types = set(allowed_types)

    results = []
    for idx, q in enumerate(questions):
        issues: List[str] = []
        fact_warnings: List[str] = []

        _check_common_fields(q, issues)
        _check_type_specific(q, issues, fact_warnings)

        if allowed_types:
            qtype = q.get("type", "")
            if qtype and qtype not in allowed_types:
                issues.append(f"Type '{qtype}' not in allowed types: {sorted(allowed_types)}")

        results.append(
            {
                "index": idx,
                "passed": len(issues) == 0,
                "issues": issues,
                "fact_warnings": fact_warnings,
            }
        )

    return results


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _check_common_fields(q: Dict[str, Any], issues: List[str]) -> None:
    """Check fields required on every question type."""
    # text must exist and be non-empty
    text = q.get("text")
    if not text or not str(text).strip():
        issues.append("Missing or empty 'text' field")

    # points must be positive
    points = q.get("points")
    if points is None:
        issues.append("Missing 'points' field")
    elif not isinstance(points, (int, float)) or points <= 0:
        issues.append(f"'points' must be positive, got {points}")

    # type must be recognised
    qtype = q.get("type")
    if not qtype:
        issues.append("Missing 'type' field")
    elif qtype not in VALID_TYPES:
        issues.append(f"Unrecognised type '{qtype}'; expected one of {sorted(VALID_TYPES)}")


def _check_type_specific(q: Dict[str, Any], issues: List[str], fact_warnings: List[str]) -> None:
    """Run type-specific structural and basic fact-consistency checks."""
    qtype = q.get("type")
    if not qtype:
        return  # already flagged in common checks

    if qtype == "mc":
        _check_mc(q, issues, fact_warnings)
    elif qtype == "ma":
        _check_ma(q, issues)
    elif qtype == "tf":
        _check_tf(q, issues, fact_warnings)
    elif qtype == "short_answer":
        _check_short_answer(q, issues)
    elif qtype == "fill_in_blank":
        _check_fill_in(q, issues)
    elif qtype == "ordering":
        _check_ordering(q, issues)
    elif qtype == "matching":
        _check_matching(q, issues)
    elif qtype == "stimulus":
        _check_stimulus(q, issues)
    elif qtype == "cloze":
        _check_cloze(q, issues)
    # essay: no additional structural requirements beyond common


def _check_mc(q: Dict[str, Any], issues: List[str], fact_warnings: List[str]) -> None:
    """Multiple-choice: 4 options, correct_index in bounds, answer matches."""
    options = q.get("options")
    if not isinstance(options, list):
        issues.append("MC question missing 'options' list")
        return
    if len(options) < 2:
        issues.append(f"MC question needs at least 2 options, got {len(options)}")

    ci = q.get("correct_index")
    if ci is None:
        issues.append("MC question missing 'correct_index'")
    elif not isinstance(ci, int) or ci < 0 or ci >= len(options):
        issues.append(f"'correct_index' {ci} out of bounds for {len(options)} options")
    else:
        # Fact-consistency: correct_answer text should match options[ci]
        ca = q.get("correct_answer")
        if ca is not None and isinstance(ca, str):
            actual = str(options[ci]).strip()
            if ca.strip() and actual and ca.strip().lower() != actual.lower():
                fact_warnings.append(f"correct_answer '{ca}' does not match options[{ci}] '{actual}'")


def _check_ma(q: Dict[str, Any], issues: List[str]) -> None:
    """Multiple-answer: options + correct_indices."""
    options = q.get("options")
    if not isinstance(options, list) or len(options) < 2:
        issues.append("MA question needs 'options' list with >=2 items")
        return
    ci = q.get("correct_indices")
    if not isinstance(ci, list) or len(ci) == 0:
        issues.append("MA question missing 'correct_indices' list")
    elif any(not isinstance(i, int) or i < 0 or i >= len(options) for i in ci):
        issues.append("Some 'correct_indices' are out of bounds")


def _check_tf(q: Dict[str, Any], issues: List[str], fact_warnings: List[str]) -> None:
    """True/false: is_true field present; consistency with correct_answer."""
    is_true = q.get("is_true")
    if is_true is None:
        issues.append("TF question missing 'is_true' field")
    elif not isinstance(is_true, bool):
        issues.append(f"'is_true' should be bool, got {type(is_true).__name__}")
    else:
        # Fact-consistency: is_true should agree with correct_answer text
        ca = q.get("correct_answer")
        if ca is not None and isinstance(ca, str):
            ca_lower = ca.strip().lower()
            if ca_lower in ("true", "false"):
                expected_bool = ca_lower == "true"
                if expected_bool != is_true:
                    fact_warnings.append(f"is_true={is_true} contradicts correct_answer='{ca}'")


def _check_short_answer(q: Dict[str, Any], issues: List[str]) -> None:
    """Short-answer: expected_answer present."""
    ea = q.get("expected_answer")
    if not ea or not str(ea).strip():
        issues.append("Short-answer question missing 'expected_answer'")


def _check_fill_in(q: Dict[str, Any], issues: List[str]) -> None:
    """Fill-in-the-blank: text has ___, correct_answer present."""
    text = q.get("text", "")
    if "___" not in str(text):
        issues.append("Fill-in-the-blank question text must contain '___'")
    ca = q.get("correct_answer")
    if not ca or not str(ca).strip():
        issues.append("Fill-in-the-blank missing 'correct_answer'")


def _check_ordering(q: Dict[str, Any], issues: List[str]) -> None:
    """Ordering: items list and correct_order present."""
    items = q.get("items")
    if not isinstance(items, list) or len(items) < 2:
        issues.append("Ordering question needs 'items' list with >=2 items")
    co = q.get("correct_order")
    if not isinstance(co, list):
        issues.append("Ordering question missing 'correct_order' list")


def _check_matching(q: Dict[str, Any], issues: List[str]) -> None:
    """Matching: must have matches list with term/definition pairs."""
    matches = q.get("matches")
    # Also check alternate data shapes (prompt_items/response_items)
    prompt_items = q.get("prompt_items")
    response_items = q.get("response_items")

    if matches and isinstance(matches, list):
        if len(matches) < 2:
            issues.append("Matching question needs at least 2 pairs")
        for i, m in enumerate(matches):
            if not isinstance(m, dict):
                issues.append(f"Match pair {i} is not a dict")
            elif not m.get("term") or not m.get("definition"):
                issues.append(f"Match pair {i} missing 'term' or 'definition'")
    elif prompt_items and response_items:
        if not isinstance(prompt_items, list) or len(prompt_items) < 2:
            issues.append("Matching question needs at least 2 prompt_items")
        if not isinstance(response_items, list) or len(response_items) < 2:
            issues.append("Matching question needs at least 2 response_items")
    else:
        issues.append(
            "Matching question missing 'matches' list (expected [{term, definition}, ...]) "
            "or 'prompt_items'/'response_items' lists"
        )


def _check_cloze(q: Dict[str, Any], issues: List[str]) -> None:
    """Cloze: must have 'blanks' list with id/answer, and text with matching {{id}} placeholders."""
    blanks = q.get("blanks")
    if not isinstance(blanks, list) or len(blanks) == 0:
        issues.append("Cloze question missing 'blanks' list (expected [{id, answer}, ...])")
        return

    text = str(q.get("text", ""))
    blank_ids = set()
    for bi, blank in enumerate(blanks):
        if not isinstance(blank, dict):
            issues.append(f"Blank {bi} is not a dict")
            continue
        b_id = blank.get("id")
        if b_id is None:
            issues.append(f"Blank {bi} missing 'id'")
        else:
            blank_ids.add(str(b_id))
        b_answer = blank.get("answer")
        if not b_answer or not str(b_answer).strip():
            issues.append(f"Blank {bi} missing 'answer'")

    # Check that text contains {{id}} placeholders matching blank ids
    import re

    placeholder_ids = set(re.findall(r"\{\{(\d+)\}\}", text))
    if blank_ids and not placeholder_ids:
        issues.append("Cloze text has no {{id}} placeholders matching blanks")
    elif blank_ids != placeholder_ids:
        missing = blank_ids - placeholder_ids
        extra = placeholder_ids - blank_ids
        if missing:
            issues.append(f"Cloze text missing placeholders for blank ids: {sorted(missing)}")
        if extra:
            issues.append(f"Cloze text has placeholders not in blanks: {sorted(extra)}")


def _check_stimulus(q: Dict[str, Any], issues: List[str]) -> None:
    """Stimulus/passage: must have stimulus_text and at least one sub-question."""
    stimulus_text = q.get("stimulus_text")
    if not stimulus_text or not str(stimulus_text).strip():
        issues.append("Stimulus question missing 'stimulus_text' (the shared passage)")

    sub_qs = q.get("sub_questions")
    if not isinstance(sub_qs, list) or len(sub_qs) == 0:
        issues.append("Stimulus question needs at least 1 sub-question in 'sub_questions'")
    else:
        for si, sq in enumerate(sub_qs):
            if not isinstance(sq, dict):
                issues.append(f"Sub-question {si} is not a dict")
                continue
            sq_text = sq.get("text")
            if not sq_text or not str(sq_text).strip():
                issues.append(f"Sub-question {si} missing 'text'")
            sq_type = sq.get("type")
            if not sq_type:
                issues.append(f"Sub-question {si} missing 'type'")
            sq_points = sq.get("points")
            if sq_points is None or (isinstance(sq_points, (int, float)) and sq_points <= 0):
                issues.append(f"Sub-question {si} has invalid 'points'")
