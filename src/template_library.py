"""Community Template Library for QuizWeaver.

Provides a curated collection of built-in quiz templates that ship with the app,
plus the ability to browse, search, preview, and use templates from a user
directory. Built-in templates live in data/templates/ as validated JSON files.

Templates follow the same format as src/template_manager.py and are validated
using validate_template() before use.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from src.template_manager import validate_template

logger = logging.getLogger(__name__)

BUILT_IN_TEMPLATES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "templates"
)
USER_TEMPLATES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "user_templates"
)


def _template_id_from_path(filepath: str) -> str:
    """Derive a template ID from a file path (filename without .json)."""
    return os.path.splitext(os.path.basename(filepath))[0]


def _load_template_file(filepath: str) -> Optional[Dict[str, Any]]:
    """Load and parse a single template JSON file.

    Returns the parsed dict or None if the file cannot be read/parsed.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("Template file is not a JSON object: %s", filepath)
            return None
        return data
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        logger.warning("Failed to load template %s: %s", filepath, exc)
        return None


def _build_summary(template_id: str, data: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Build a summary dict from a full template dict."""
    metadata = data.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, ValueError):
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "id": template_id,
        "title": data.get("title", "Untitled Template"),
        "subject": data.get("subject", ""),
        "grade_level": data.get("grade_level", ""),
        "question_count": data.get("question_count", len(data.get("questions", []))),
        "tags": metadata.get("tags", []),
        "description": metadata.get("description", ""),
        "created_by": metadata.get("created_by", ""),
        "source": source,
    }


def _collect_templates_from_dir(
    directory: str, source: str
) -> List[Dict[str, Any]]:
    """Scan a directory for .json template files and return summaries."""
    results = []
    if not os.path.isdir(directory):
        return results

    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(directory, filename)
        if not os.path.isfile(filepath):
            continue
        data = _load_template_file(filepath)
        if data is None:
            continue
        template_id = _template_id_from_path(filepath)
        results.append(_build_summary(template_id, data, source))

    return results


def list_templates(
    include_builtin: bool = True,
    user_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all available templates (built-in + user-uploaded).

    Args:
        include_builtin: Whether to include built-in templates.
        user_dir: Optional path to a user templates directory.
            Defaults to data/user_templates if None.

    Returns:
        List of template summary dicts sorted by title.
    """
    templates: List[Dict[str, Any]] = []

    if include_builtin:
        templates.extend(_collect_templates_from_dir(BUILT_IN_TEMPLATES_DIR, "builtin"))

    effective_user_dir = user_dir if user_dir is not None else USER_TEMPLATES_DIR
    templates.extend(_collect_templates_from_dir(effective_user_dir, "user"))

    templates.sort(key=lambda t: t.get("title", "").lower())
    return templates


def get_template(
    template_id: str,
    user_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Load a specific template by ID (filename without .json).

    Searches built-in templates first, then user templates.

    Args:
        template_id: The template identifier (e.g. 'elementary_science_mc').
        user_dir: Optional path to a user templates directory.

    Returns:
        Full template dict with an added '_source' key, or None if not found.
    """
    # Sanitize template_id to prevent path traversal
    safe_id = re.sub(r"[^\w\-]", "", template_id)
    if not safe_id:
        return None

    # Check built-in first
    builtin_path = os.path.join(BUILT_IN_TEMPLATES_DIR, f"{safe_id}.json")
    if os.path.isfile(builtin_path):
        data = _load_template_file(builtin_path)
        if data is not None:
            data["_source"] = "builtin"
            data["_id"] = safe_id
            return data

    # Check user directory
    effective_user_dir = user_dir if user_dir is not None else USER_TEMPLATES_DIR
    user_path = os.path.join(effective_user_dir, f"{safe_id}.json")
    if os.path.isfile(user_path):
        data = _load_template_file(user_path)
        if data is not None:
            data["_source"] = "user"
            data["_id"] = safe_id
            return data

    return None


def search_templates(
    query: Optional[str] = None,
    subject: Optional[str] = None,
    grade_level: Optional[str] = None,
    tags: Optional[List[str]] = None,
    user_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Filter templates by search criteria.

    All filters are combined with AND logic. An empty/None filter is ignored.

    Args:
        query: Free-text search across title, description, and tags.
        subject: Filter by subject (case-insensitive substring match).
        grade_level: Filter by grade level (case-insensitive substring match).
        tags: Filter by tags (template must contain ALL specified tags).
        user_dir: Optional path to a user templates directory.

    Returns:
        List of matching template summary dicts.
    """
    all_templates = list_templates(include_builtin=True, user_dir=user_dir)
    results = []

    for t in all_templates:
        # Subject filter
        if subject and subject.lower() not in t.get("subject", "").lower():
            continue

        # Grade level filter
        if grade_level and grade_level.lower() not in t.get("grade_level", "").lower():
            continue

        # Tags filter (all specified tags must be present)
        if tags:
            template_tags = [tag.lower() for tag in t.get("tags", [])]
            if not all(tag.lower() in template_tags for tag in tags):
                continue

        # Free-text query filter
        if query:
            q_lower = query.lower()
            searchable = " ".join([
                t.get("title", ""),
                t.get("description", ""),
                t.get("subject", ""),
                t.get("grade_level", ""),
                " ".join(t.get("tags", [])),
            ]).lower()
            if q_lower not in searchable:
                continue

        results.append(t)

    return results


def get_template_preview(
    template_id: str,
    max_questions: int = 3,
    user_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get a preview of a template (limited questions + metadata).

    Args:
        template_id: The template identifier.
        max_questions: Maximum number of questions to include in preview.
        user_dir: Optional path to a user templates directory.

    Returns:
        Dict with template metadata and a truncated questions list,
        or None if template not found.
    """
    data = get_template(template_id, user_dir=user_dir)
    if data is None:
        return None

    questions = data.get("questions", [])
    metadata = data.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, ValueError):
            metadata = {}

    # Count question types
    type_counts: Dict[str, int] = {}
    for q in questions:
        qt = q.get("question_type", "unknown")
        type_counts[qt] = type_counts.get(qt, 0) + 1

    preview = {
        "id": data.get("_id", template_id),
        "title": data.get("title", "Untitled Template"),
        "subject": data.get("subject", ""),
        "grade_level": data.get("grade_level", ""),
        "standards": data.get("standards", []),
        "cognitive_framework": data.get("cognitive_framework", ""),
        "question_count": data.get("question_count", len(questions)),
        "questions_preview": questions[:max_questions],
        "question_types": type_counts,
        "total_points": sum(q.get("points", 0) for q in questions),
        "tags": metadata.get("tags", []),
        "description": metadata.get("description", ""),
        "created_by": metadata.get("created_by", ""),
        "source": data.get("_source", "unknown"),
    }

    return preview


def save_user_template(
    template_data: Dict[str, Any],
    user_dir: Optional[str] = None,
) -> tuple:
    """Save a user-contributed template to the user templates directory.

    Validates the template before saving. Generates a filename from the title.

    Args:
        template_data: The template dict to save.
        user_dir: Optional path to save to. Defaults to data/user_templates.

    Returns:
        Tuple of (success: bool, template_id_or_error: str).
    """
    # Validate first
    is_valid, errors = validate_template(template_data)
    if not is_valid:
        return False, "; ".join(errors)

    effective_dir = user_dir if user_dir is not None else USER_TEMPLATES_DIR

    # Ensure directory exists
    os.makedirs(effective_dir, exist_ok=True)

    # Generate a safe filename from the title
    title = template_data.get("title", "untitled")
    safe_name = re.sub(r"[^\w\s\-]", "", title)
    safe_name = re.sub(r"\s+", "_", safe_name.strip()).lower()[:60]
    if not safe_name:
        safe_name = "untitled"

    # Check for duplicates and append a suffix if needed
    template_id = safe_name
    filepath = os.path.join(effective_dir, f"{template_id}.json")
    counter = 1
    while os.path.exists(filepath):
        template_id = f"{safe_name}_{counter}"
        filepath = os.path.join(effective_dir, f"{template_id}.json")
        counter += 1

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(template_data, f, indent=2, ensure_ascii=False)
        logger.info("Saved user template: %s -> %s", template_id, filepath)
        return True, template_id
    except OSError as exc:
        logger.error("Failed to save user template: %s", exc)
        return False, f"Failed to save template: {exc}"
