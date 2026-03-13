"""
Source document extraction engine for QuizWeaver.

Provides deterministic text extraction from PDF documents with page-level
provenance tracking. NO AI/LLM involvement -- purely rule-based.

This module supports the document-sourced standards pipeline:
1. Extract text from PDF curriculum frameworks (PyMuPDF)
2. Parse SOL codes and essential knowledge/skills/understandings
3. Register source documents with file hash verification
4. Link parsed content to existing Standard records via StandardExcerpt rows
"""

import hashlib
import json
import logging
import os
import re
import shutil
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

import fitz  # PyMuPDF -- already used by src/ingestion.py

from src.database import SourceDocument, Standard, StandardExcerpt

logger = logging.getLogger(__name__)

# Directory for stored copies of source documents (relative to project root)
SOURCE_DOCUMENTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "source_documents"
)


# ---------------------------------------------------------------------------
# 1. PDF text extraction
# ---------------------------------------------------------------------------


def extract_text_by_page(filepath: str) -> List[Dict]:
    """Extract text from each page of a PDF with page-level provenance.

    Uses PyMuPDF (fitz) for text extraction -- deterministic, no AI.

    Args:
        filepath: Path to the PDF file.

    Returns:
        List of dicts: [{"page": 1, "text": "..."}, ...]

    Raises:
        FileNotFoundError: If the file does not exist.
        RuntimeError: If the PDF cannot be opened.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"PDF file not found: {filepath}")

    pages = []
    try:
        doc = fitz.open(filepath)
    except Exception as exc:
        raise RuntimeError(f"Failed to open PDF: {filepath}") from exc

    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            text = page.get_text()
            if not text or not text.strip():
                logger.warning(
                    "Page %d of %s produced no text (may be scanned/image-only)",
                    page_index + 1,
                    filepath,
                )
            pages.append({"page": page_index + 1, "text": text or ""})
    finally:
        doc.close()

    return pages


def extract_columns_by_page(filepath: str) -> List[Dict]:
    """Extract text from a two-column PDF with column separation.

    Uses PyMuPDF bounding box data to separate left and right columns.
    This is essential for VA SOL Curriculum Framework PDFs which use
    a two-column table: Enduring Understandings (left) and
    Essential Knowledge and Practices (right).

    Args:
        filepath: Path to the PDF file.

    Returns:
        List of dicts::

            [{"page": 1, "left": "...", "right": "...", "text": "..."}, ...]

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"PDF file not found: {filepath}")

    pages = []
    try:
        doc = fitz.open(filepath)
    except Exception as exc:
        raise RuntimeError(f"Failed to open PDF: {filepath}") from exc

    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            page_width = page.rect.width
            mid_x = page_width / 2

            left_spans = []
            right_spans = []
            full_text = page.get_text() or ""

            try:
                text_dict = page.get_text("dict")
                for block in text_dict.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            bbox = span.get("bbox", [0, 0, 0, 0])
                            text = span.get("text", "").strip()
                            if not text:
                                continue
                            y_pos = bbox[1]
                            x_pos = bbox[0]
                            if x_pos < mid_x:
                                left_spans.append((y_pos, text))
                            else:
                                right_spans.append((y_pos, text))
            except Exception:
                logger.warning(
                    "Column extraction failed for page %d, falling back to plain text",
                    page_index + 1,
                )

            # Sort by y position and join into text
            left_spans.sort(key=lambda s: s[0])
            right_spans.sort(key=lambda s: s[0])
            left_text = "\n".join(t for _, t in left_spans)
            right_text = "\n".join(t for _, t in right_spans)

            pages.append({
                "page": page_index + 1,
                "left": left_text,
                "right": right_text,
                "text": full_text,
            })
    finally:
        doc.close()

    return pages


# ---------------------------------------------------------------------------
# 2. File hash
# ---------------------------------------------------------------------------


def compute_file_hash(filepath: str) -> str:
    """Compute SHA-256 hash of a file for integrity verification.

    Args:
        filepath: Path to the file.

    Returns:
        Hex-encoded SHA-256 hash string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ---------------------------------------------------------------------------
# 3. Register source document
# ---------------------------------------------------------------------------


def register_source_document(
    session,
    filepath: str,
    title: str,
    url: str = None,
    standard_set: str = None,
    version: str = None,
) -> SourceDocument:
    """Register a PDF as a source document in the database.

    Computes file hash and page count, copies the file into
    ``data/source_documents/`` if not already there, and creates
    a SourceDocument record.

    Args:
        session: SQLAlchemy session.
        filepath: Path to the PDF file.
        title: Human-readable title for the document.
        url: Optional URL where the document can be downloaded.
        standard_set: Standard set key (e.g., "sol").
        version: Version/year string.

    Returns:
        The created (or existing) SourceDocument ORM object.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    file_hash = compute_file_hash(filepath)
    filename = os.path.basename(filepath)

    # Check for an existing document with the same filename
    existing = session.query(SourceDocument).filter_by(filename=filename).first()
    if existing:
        logger.info(
            "Source document already registered: %s (id=%d)", filename, existing.id
        )
        return existing

    # Count pages using fitz
    page_count = 0
    try:
        doc = fitz.open(filepath)
        page_count = len(doc)
        doc.close()
    except Exception:
        logger.warning("Could not count pages for %s", filepath)

    # Copy file to data/source_documents/ if not already there
    os.makedirs(SOURCE_DOCUMENTS_DIR, exist_ok=True)
    dest_path = os.path.join(SOURCE_DOCUMENTS_DIR, filename)
    if not os.path.exists(dest_path):
        shutil.copy2(filepath, dest_path)
        logger.info("Copied source document to %s", dest_path)

    source_doc = SourceDocument(
        filename=filename,
        title=title,
        url=url,
        standard_set=standard_set,
        version=version,
        download_date=datetime.utcnow().strftime("%Y-%m-%d"),
        file_hash=file_hash,
        page_count=page_count,
        created_at=datetime.utcnow(),
    )
    session.add(source_doc)
    session.commit()
    logger.info("Registered source document: %s (id=%d)", title, source_doc.id)
    return source_doc


# ---------------------------------------------------------------------------
# 4. SOL Curriculum Framework parser (deterministic, regex-based)
# ---------------------------------------------------------------------------

# Regex for SOL codes: optional "SOL " prefix, then subject.number pattern
# Examples: SOL LS.1, BIO.1, ES.2, LS.14a, GOVT.1, USI.1, 6.1, 6.2
_SOL_CODE_RE = re.compile(
    r"(?:SOL\s+)?([A-Z]{2,5}\.\d+[a-z]?|\d+\.\d+[a-z]?)\b"
)

# Section header patterns (case-insensitive)
# Virginia SOL Curriculum Framework uses two-column format:
#   "Enduring Understandings" (left) → essential_understandings
#   "Essential Knowledge and Practices" (right) → essential_knowledge
_SECTION_HEADERS = {
    "essential_knowledge": re.compile(
        r"Essential\s+Knowledge(?:\s+and\s+(?:Skills|Practices))?", re.IGNORECASE
    ),
    "essential_understandings": re.compile(
        r"(?:Essential|Enduring)\s+Understandings?", re.IGNORECASE
    ),
    "essential_skills": re.compile(
        r"Essential\s+Skills?\b(?!\s+and)", re.IGNORECASE
    ),
}

# Bullet point pattern: lines starting with bullet chars or numbered items
_BULLET_RE = re.compile(r"^\s*(?:[•\-\u2013\u2014\u25E6\u25AA\uf0b7]|\d+[.)]\s)")


def _clean_text(text: str) -> str:
    """Normalize whitespace and remove stray artifacts from extracted text."""
    # Collapse multiple spaces/tabs into single space
    text = re.sub(r"[ \t]+", " ", text)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines)


def _extract_bullet_items(lines: List[str]) -> List[str]:
    """Extract bullet-point items from a list of lines.

    Handles multi-line items by joining continuation lines (lines that
    don't start with a bullet) to the preceding item.

    Args:
        lines: List of text lines.

    Returns:
        List of extracted items (each item is a single string).
    """
    items = []
    current_item = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if _BULLET_RE.match(stripped):
            # Start of a new bullet item -- strip the bullet marker
            text = re.sub(
                r"^\s*(?:[•\-\u2013\u2014\u25E6\u25AA\uf0b7]|\d+[.)]\s*)", "", stripped
            ).strip()
            if current_item is not None:
                items.append(current_item)
            current_item = text
        elif current_item is not None:
            # Continuation of the previous item
            current_item += " " + stripped
        else:
            # Non-bullet text before any bullet -- treat as content if
            # it looks substantive (not a header or short label)
            if len(stripped) > 20:
                if current_item is not None:
                    items.append(current_item)
                current_item = stripped

    if current_item is not None:
        items.append(current_item)

    return items


def parse_sol_curriculum_framework(pages_text: List[Dict]) -> List[Dict]:
    """Parse a Virginia SOL Curriculum Framework PDF into structured data.

    Deterministic regex-based parser. Finds SOL codes and extracts
    Enduring Understandings (left column) and Essential Knowledge and
    Practices (right column) with page-level provenance.

    Supports both column-aware input (from extract_columns_by_page, with
    "left"/"right" keys) and plain text input (from extract_text_by_page,
    with "text" key only). Column-aware input produces much better results
    for the two-column VA SOL Curriculum Framework format.

    Args:
        pages_text: Output of extract_columns_by_page() or
            extract_text_by_page() -- list of dicts with page info.

    Returns:
        List of dicts, one per standard found::

            [
                {
                    "code": "SOL LS.1",
                    "page": 5,
                    "essential_knowledge": ["item 1", ...],
                    "essential_understandings": ["item 1", ...],
                    "essential_skills": []
                },
                ...
            ]

        Returns an empty list if no SOL codes are found.
    """
    has_columns = any("left" in p and "right" in p for p in pages_text)

    if has_columns:
        return _parse_with_columns(pages_text)
    return _parse_plain_text(pages_text)


def _parse_with_columns(pages_text: List[Dict]) -> List[Dict]:
    """Parse using column-separated text (preferred for two-column PDFs).

    Handles shared pages where one standard ends and another begins.
    Each extracted item is stored as a (text, page) tuple internally,
    then flattened to the output format with per-item page tracking.

    The VA SOL Curriculum Framework uses a two-column table:
    - Left column: Enduring Understandings
    - Right column: Essential Knowledge and Practices

    Standard declarations (e.g., "LS.8 The student will...") appear
    as full-width rows between the two-column content sections.
    """
    # Accumulator: code -> {code, page, essential_knowledge: [(text, page)], ...}
    _accum: Dict[str, Dict] = {}
    active_code = None

    # Standard declaration regex
    _std_decl_re = re.compile(
        r"(?:SOL\s+)?([A-Z]{2,5}\.\d+|\d+\.\d+)\s+The\s+student\s+will"
    )

    for page_info in pages_text:
        page_num = page_info["page"]
        full_text = page_info.get("text", "")
        left_text = page_info.get("left", "")
        right_text = page_info.get("right", "")

        if not full_text.strip():
            continue

        # Check if a new standard is declared on this page
        # Standard declarations appear in the full (interleaved) text
        decl_match = _std_decl_re.search(full_text)
        new_code_on_page = None

        if decl_match:
            new_code_on_page = f"SOL {decl_match.group(1)}"
            decl_pos = decl_match.start()

            # If there's content BEFORE the declaration and we have
            # an active standard, that content belongs to the previous
            # standard (shared page scenario)
            if active_code and decl_pos > 0:
                pre_text = full_text[:decl_pos]
                # Only assign pre-declaration content if it has
                # substantive content (not just headers/footers)
                has_substance = any(
                    len(line.strip()) > 20
                    and not re.match(
                        r"^(Enduring|Essential|Vertical|Central|2018|Scientific|Curriculum)",
                        line.strip(),
                        re.IGNORECASE,
                    )
                    for line in pre_text.split("\n")
                )
                if has_substance:
                    # Content before declaration belongs to previous standard
                    # Split columns at the declaration boundary using line count
                    pre_lines = pre_text.count("\n")
                    total_lines = full_text.count("\n")
                    if total_lines > 0:
                        ratio = pre_lines / total_lines
                    else:
                        ratio = 0.5

                    # Split left and right columns proportionally
                    left_lines = left_text.split("\n")
                    right_lines = right_text.split("\n")
                    split_left = int(len(left_lines) * ratio)
                    split_right = int(len(right_lines) * ratio)

                    pre_left = "\n".join(left_lines[:split_left])
                    pre_right = "\n".join(right_lines[:split_right])

                    if pre_left.strip():
                        items = _extract_column_content(
                            pre_left, "understandings"
                        )
                        for item in items:
                            _accum[active_code][
                                "essential_understandings"
                            ].append((item, page_num))

                    if pre_right.strip():
                        items = _extract_column_content(
                            pre_right, "knowledge"
                        )
                        for item in items:
                            _accum[active_code][
                                "essential_knowledge"
                            ].append((item, page_num))

                    # Remaining column text goes to the new standard
                    left_text = "\n".join(left_lines[split_left:])
                    right_text = "\n".join(right_lines[split_right:])

            # Register the new standard
            if new_code_on_page not in _accum:
                _accum[new_code_on_page] = {
                    "code": new_code_on_page,
                    "page": page_num,
                    "essential_knowledge": [],
                    "essential_understandings": [],
                    "essential_skills": [],
                }
            active_code = new_code_on_page

        if not active_code:
            # Try simpler SOL code patterns at line starts
            for match in _SOL_CODE_RE.finditer(full_text):
                code = f"SOL {match.group(1)}"
                if code not in _accum:
                    _accum[code] = {
                        "code": code,
                        "page": page_num,
                        "essential_knowledge": [],
                        "essential_understandings": [],
                        "essential_skills": [],
                    }
                    active_code = code
                    break

        if not active_code:
            continue

        # Extract content from left column → essential_understandings
        if left_text.strip():
            left_items = _extract_column_content(left_text, "understandings")
            for item in left_items:
                _accum[active_code]["essential_understandings"].append(
                    (item, page_num)
                )

        # Extract content from right column → essential_knowledge
        if right_text.strip():
            right_items = _extract_column_content(right_text, "knowledge")
            for item in right_items:
                _accum[active_code]["essential_knowledge"].append(
                    (item, page_num)
                )

    if not _accum:
        logger.warning("No SOL codes found in the document")
        return []

    # Flatten (text, page) tuples, deduplicate, filter, and build output
    result = []

    # Preamble patterns to filter out (standard declarations, vertical
    # alignment notes, etc. that aren't actual content)
    _preamble_re = re.compile(
        r"^(?:(?:a|b|c|d|e)\)\s|Students learn|Students begin|"
        r"These concepts are extended|This standard is|"
        r"Students are not responsible)",
        re.IGNORECASE,
    )

    for entry in _accum.values():
        # Extract the base SOL code (e.g., "LS.8" from "SOL LS.8")
        base_code = entry["code"].replace("SOL ", "")
        # Build set of related codes (same standard + sub-standards)
        related_codes = {base_code}
        # e.g., LS.8 -> LS.8 a, LS.8 b, LS.8 c
        for sub in "abcdefgh":
            related_codes.add(f"{base_code} {sub}")
            related_codes.add(f"{base_code}{sub}")

        out = {
            "code": entry["code"],
            "page": entry["page"],
            "essential_knowledge": [],
            "essential_understandings": [],
            "essential_skills": [],
            "_page_map": {
                "essential_knowledge": [],
                "essential_understandings": [],
                "essential_skills": [],
            },
        }
        for key in ("essential_knowledge", "essential_understandings", "essential_skills"):
            seen = set()
            for item_tuple in entry[key]:
                text, pg = item_tuple
                normalized = text.strip().lower()
                if normalized in seen or len(normalized) <= 10:
                    continue

                # Filter: skip items that ONLY reference a different
                # standard (e.g., "(LS.7 a)" in LS.8's content)
                sol_refs = re.findall(
                    r"\(([A-Z]{2,5}\.\d+)\s*[a-h]?\)", text
                )
                if sol_refs:
                    # Check if ANY reference matches this standard
                    has_own_ref = any(
                        ref in related_codes for ref in sol_refs
                    )
                    if not has_own_ref:
                        # All references are to other standards — skip
                        continue

                # Filter: skip preamble/boilerplate items
                if _preamble_re.match(text.strip()):
                    continue

                # Truncate if another standard's declaration is
                # embedded in the text (e.g., "...LS.8 c). LS.9 The
                # student will investigate...")
                next_std = re.search(
                    r"\s+[A-Z]{2,5}\.\d+\s+The\s+student\s+will",
                    text,
                )
                if next_std:
                    text = text[: next_std.start()].rstrip()
                    if len(text.strip()) <= 10:
                        continue

                seen.add(normalized)
                out[key].append(text)
                out["_page_map"][key].append(pg)
        result.append(out)

    return result


def _extract_column_content(column_text: str, column_type: str) -> List[str]:
    """Extract content items from a single column of text.

    Filters out headers, boilerplate, and short fragments.
    Joins multi-line items into complete sentences.

    Args:
        column_text: Text from one column of a page.
        column_type: "understandings" or "knowledge" for filtering.

    Returns:
        List of content strings.
    """
    lines = column_text.split("\n")
    items = []
    current_item = None

    # Skip patterns: headers, boilerplate, page footers
    _skip_re = re.compile(
        r"^(Enduring Understandings|Essential Knowledge and Practices|"
        r"Vertical Alignment|Central Idea|In order to meet this standard|"
        r"2018 Virginia Science|Scientific & Engineering|"
        r"Curriculum Framework|\d+$)",
        re.IGNORECASE,
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _skip_re.match(stripped):
            continue

        # Check if this is a bullet/new item
        is_bullet = bool(_BULLET_RE.match(stripped))

        if is_bullet:
            if current_item:
                items.append(current_item)
            # Strip bullet marker
            text = re.sub(
                r"^\s*(?:[•\-\u2013\u2014\u25E6\u25AA\uf0b7]|\d+[.)]\s*)",
                "",
                stripped,
            ).strip()
            current_item = text
        elif current_item is not None:
            # Continuation of previous item
            current_item += " " + stripped
        else:
            # Non-bullet content — could be a paragraph-style item
            if len(stripped) > 20:
                if current_item:
                    items.append(current_item)
                current_item = stripped

    if current_item:
        items.append(current_item)

    return items


def _parse_plain_text(pages_text: List[Dict]) -> List[Dict]:
    """Parse using plain text only (fallback for non-column input)."""
    # Internal accumulator keyed by SOL code
    _accum: Dict[str, Dict] = {}

    for page_info in pages_text:
        page_num = page_info["page"]
        raw_text = page_info.get("text", "")
        if not raw_text.strip():
            continue

        text = _clean_text(raw_text)
        lines = text.split("\n")

        # Find SOL codes on this page
        page_sol_codes = []
        for match in _SOL_CODE_RE.finditer(text):
            code = match.group(1)  # e.g., "LS.1"
            full_code = f"SOL {code}"
            if full_code not in page_sol_codes:
                page_sol_codes.append(full_code)

        if not page_sol_codes:
            continue

        active_code = page_sol_codes[0]

        for code in page_sol_codes:
            if code not in _accum:
                _accum[code] = {
                    "code": code,
                    "page": page_num,
                    "essential_knowledge": [],
                    "essential_understandings": [],
                    "essential_skills": [],
                }

        current_section = None
        section_lines: List[str] = []

        for line in lines:
            stripped = line.strip()

            sol_line_match = re.match(
                r"^(?:SOL\s+)?([A-Z]{2,5}\.\d+[a-z]?)\b", stripped
            )
            if sol_line_match:
                candidate = f"SOL {sol_line_match.group(1)}"
                if candidate in page_sol_codes or candidate not in _accum:
                    if current_section and section_lines and active_code:
                        _flush_section(
                            _accum, active_code, current_section,
                            section_lines, page_num,
                        )
                        section_lines = []
                    active_code = candidate
                    if active_code not in _accum:
                        _accum[active_code] = {
                            "code": active_code,
                            "page": page_num,
                            "essential_knowledge": [],
                            "essential_understandings": [],
                            "essential_skills": [],
                        }

            new_section = None
            for section_key, pattern in _SECTION_HEADERS.items():
                if pattern.search(stripped):
                    new_section = section_key
                    break

            if new_section:
                if current_section and section_lines and active_code:
                    _flush_section(
                        _accum, active_code, current_section,
                        section_lines, page_num,
                    )
                current_section = new_section
                section_lines = []
            elif current_section:
                section_lines.append(stripped)

        if current_section and section_lines and active_code:
            _flush_section(
                _accum, active_code, current_section,
                section_lines, page_num,
            )

    if not _accum:
        logger.warning("No SOL codes found in the document")
        return []

    return list(_accum.values())


def _flush_section(
    accum: Dict,
    sol_code: str,
    section_key: str,
    lines: List[str],
    page_num: int,
) -> None:
    """Flush accumulated section lines into the accumulator.

    Extracts bullet items from the lines and appends them as flat
    strings to the appropriate section list for the given SOL code.
    """
    items = _extract_bullet_items(lines)
    if not items:
        # If no bullet items found, treat non-empty lines as content
        joined = " ".join(l for l in lines if l.strip())
        if joined.strip():
            items = [joined.strip()]

    entry = accum.get(sol_code)
    if entry is None:
        return

    for item_text in items:
        text = item_text.strip()
        if text:
            entry[section_key].append(text)


# ---------------------------------------------------------------------------
# 5. Import parsed data into database
# ---------------------------------------------------------------------------


def import_from_source_document(
    session,
    document_id: int,
    parsed_data,
) -> int:
    """Link parsed content to existing standards via StandardExcerpt rows.

    For each standard code in parsed_data, finds the matching Standard
    in the database and creates StandardExcerpt rows with content_type,
    source_page, and source_excerpt. Also updates the JSON cache columns
    on the Standard model (essential_knowledge, essential_understandings,
    essential_skills).

    Args:
        session: SQLAlchemy session.
        document_id: ID of the registered SourceDocument.
        parsed_data: Output of parse_sol_curriculum_framework() -- a list
            of dicts each with "code", "page", and section lists.

    Returns:
        Count of standards that were updated.
    """
    updated_count = 0

    for entry in parsed_data:
        sol_code = entry.get("code", "")
        source_page = entry.get("page", 0)

        # Normalize code for DB lookup: try with and without "SOL " prefix
        standard = _find_standard(session, sol_code)
        if standard is None:
            logger.warning(
                "No matching Standard found for code '%s' -- skipping",
                sol_code,
            )
            continue

        standard_updated = False
        sort_order = 0
        # Per-item page map from _parse_with_columns (optional)
        page_map = entry.get("_page_map", {})

        for content_type in (
            "essential_knowledge",
            "essential_understandings",
            "essential_skills",
        ):
            items = entry.get(content_type, [])
            if not items:
                continue

            # Get per-item page numbers if available
            item_pages = page_map.get(content_type, [])

            for idx, item_text in enumerate(items):
                # Use per-item page if available, else fall back to
                # the standard's declaration page
                item_page = (
                    item_pages[idx]
                    if idx < len(item_pages)
                    else source_page
                )
                # Create StandardExcerpt row
                excerpt = StandardExcerpt(
                    standard_id=standard.id,
                    source_document_id=document_id,
                    content_type=content_type,
                    source_page=item_page,
                    source_excerpt=item_text,
                    sort_order=sort_order,
                    created_at=datetime.utcnow(),
                )
                session.add(excerpt)
                sort_order += 1
                standard_updated = True

            # Update JSON cache column on Standard
            _update_standard_json_cache(standard, content_type, items)

        if standard_updated:
            updated_count += 1

    if updated_count > 0:
        session.commit()
        logger.info(
            "Imported excerpts for %d standards from document %d",
            updated_count,
            document_id,
        )

    return updated_count


def _find_standard(session, sol_code: str) -> Optional[Standard]:
    """Find a Standard by SOL code, trying multiple formats.

    Tries: exact match, with "SOL " prefix, without "SOL " prefix.

    Args:
        session: SQLAlchemy session.
        sol_code: SOL code string (e.g., "SOL LS.1" or "LS.1").

    Returns:
        Standard object or None.
    """
    # Try exact match first
    std = session.query(Standard).filter_by(code=sol_code).first()
    if std:
        return std

    # Try with "SOL " prefix
    if not sol_code.startswith("SOL "):
        std = session.query(Standard).filter_by(code=f"SOL {sol_code}").first()
        if std:
            return std

    # Try without "SOL " prefix
    if sol_code.startswith("SOL "):
        bare_code = sol_code[4:].strip()
        std = session.query(Standard).filter_by(code=bare_code).first()
        if std:
            return std

    # Fallback for grade 3-8 science code format mismatch.
    # Curriculum framework PDFs extract codes like "SOL 6.1" but the DB may
    # store them as "SOL 6.1E" (old format) or "SOL 6.1S" (science suffix).
    # Try appending E and S suffixes for numeric-prefix codes (e.g., 6.1, 7.2).
    import re
    normalized = sol_code if sol_code.startswith("SOL ") else f"SOL {sol_code}"
    bare = normalized[4:].strip()
    if re.match(r"^\d+\.\d+$", bare):
        for suffix in ("S", "E"):
            std = session.query(Standard).filter_by(
                code=f"SOL {bare}{suffix}"
            ).first()
            if std:
                return std

    return None


def _update_standard_json_cache(
    standard: Standard,
    content_type: str,
    items: List[str],
) -> None:
    """Update the JSON cache column on a Standard with new content.

    Merges new items with any existing cached content, avoiding duplicates.

    Args:
        standard: Standard ORM object.
        content_type: One of "essential_knowledge", "essential_understandings",
            "essential_skills".
        items: List of plain text strings.
    """
    # Get existing cached content
    existing_json = getattr(standard, content_type, None)
    existing_items: List[str] = []
    if existing_json:
        try:
            existing_items = json.loads(existing_json)
        except (json.JSONDecodeError, TypeError):
            existing_items = []

    # Collect existing text values for deduplication
    existing_texts = set()
    for item in existing_items:
        if isinstance(item, str):
            existing_texts.add(item)
        elif isinstance(item, dict):
            existing_texts.add(item.get("text", ""))

    # Add new items (text only for the cache column)
    new_texts = []
    for text in items:
        if text not in existing_texts:
            new_texts.append(text)
            existing_texts.add(text)

    if new_texts:
        # The cache column stores a JSON list of strings
        all_items = list(existing_items) + new_texts
        setattr(standard, content_type, json.dumps(all_items))


# ---------------------------------------------------------------------------
# 6. Query helpers
# ---------------------------------------------------------------------------


def get_excerpts_for_standard(session, standard_id: int) -> Dict:
    """Return excerpts for a standard, grouped by content_type with provenance.

    Args:
        session: SQLAlchemy session.
        standard_id: ID of the Standard.

    Returns:
        Dict keyed by content_type::

            {
                "essential_knowledge": [
                    {"text": "...", "page": N, "doc_title": "...", "doc_id": N},
                    ...
                ],
                "essential_understandings": [...],
                "essential_skills": [...]
            }
    """
    excerpts = (
        session.query(StandardExcerpt)
        .filter_by(standard_id=standard_id)
        .order_by(StandardExcerpt.content_type, StandardExcerpt.sort_order)
        .all()
    )

    grouped = defaultdict(list)

    for exc in excerpts:
        doc_title = ""
        doc_id = exc.source_document_id
        if exc.source_document:
            doc_title = exc.source_document.title

        grouped[exc.content_type].append({
            "text": exc.source_excerpt,
            "page": exc.source_page,
            "doc_title": doc_title,
            "doc_id": doc_id,
        })

    return dict(grouped)


def get_source_document(session, document_id: int) -> Optional[SourceDocument]:
    """Fetch a source document by ID.

    Args:
        session: SQLAlchemy session.
        document_id: ID of the SourceDocument.

    Returns:
        SourceDocument object or None.
    """
    return session.query(SourceDocument).filter_by(id=document_id).first()


def list_source_documents(
    session, standard_set: str = None,
) -> List[SourceDocument]:
    """List all registered source documents, optionally filtered.

    Args:
        session: SQLAlchemy session.
        standard_set: Optional filter by standard set key.

    Returns:
        List of SourceDocument objects ordered by title.
    """
    query = session.query(SourceDocument)
    if standard_set:
        query = query.filter_by(standard_set=standard_set)
    return query.order_by(SourceDocument.title).all()
