"""
Standards database module for QuizWeaver.

Provides CRUD operations and search functionality for educational standards.
Standards are DETERMINISTIC data -- rule-based, not AI-generated.
This is a core AI literacy principle: standards alignment uses rule-based
systems, not LLM inference.

Supports multiple standard sets:
- Virginia SOL (sol)
- Common Core ELA (ccss_ela)
- Common Core Math (ccss_math)
- Next Generation Science Standards (ngss)
- Texas Essential Knowledge and Skills (teks)
- Custom teacher-imported sets
"""

import json
import os
from typing import Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.database import Standard

# Registry of available standard sets with metadata
STANDARD_SETS = {
    "sol": {"label": "Virginia SOL", "file": "sol_standards.json"},
    "ccss_ela": {"label": "Common Core ELA", "file": "ccss_ela_standards.json"},
    "ccss_math": {"label": "Common Core Math", "file": "ccss_math_standards.json"},
    "ngss": {"label": "Next Generation Science Standards", "file": "ngss_standards.json"},
    "teks": {"label": "Texas TEKS", "file": "teks_standards.json"},
}


def get_available_standard_sets() -> List[Dict]:
    """Return list of available standard sets with metadata.

    Returns:
        List of dicts with 'key', 'label', and 'file' for each set.
    """
    result = []
    for key, info in STANDARD_SETS.items():
        result.append(
            {
                "key": key,
                "label": info["label"],
                "file": info["file"],
            }
        )
    return result


def get_data_dir() -> str:
    """Return the path to the data directory."""
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
    )


def load_standard_set(session: Session, standard_set: str = "sol") -> int:
    """Load a specific standard set into the database from its JSON file.

    Args:
        session: SQLAlchemy session
        standard_set: Key from STANDARD_SETS (e.g., 'sol', 'ccss_ela')

    Returns:
        Number of standards imported

    Raises:
        ValueError: If standard_set is not recognized
        FileNotFoundError: If the data file does not exist
    """
    if standard_set not in STANDARD_SETS:
        raise ValueError(f"Unknown standard set '{standard_set}'. Available: {list(STANDARD_SETS.keys())}")

    info = STANDARD_SETS[standard_set]
    json_path = os.path.join(get_data_dir(), info["file"])

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Standards data file not found: {json_path}")

    return load_standards_from_json(session, json_path)


def ensure_standard_set_loaded(session: Session, standard_set: str) -> int:
    """Load a standard set only if it has no records in the database.

    Args:
        session: SQLAlchemy session
        standard_set: Key from STANDARD_SETS

    Returns:
        Number of standards imported (0 if already loaded)
    """
    existing = session.query(Standard).filter_by(standard_set=standard_set).count()
    if existing > 0:
        return 0
    try:
        return load_standard_set(session, standard_set)
    except (ValueError, FileNotFoundError):
        return 0


def create_standard(
    session: Session,
    code: str,
    description: str,
    subject: str,
    grade_band: Optional[str] = None,
    strand: Optional[str] = None,
    full_text: Optional[str] = None,
    source: str = "Virginia SOL",
    version: Optional[str] = None,
    standard_set: str = "sol",
) -> Standard:
    """
    Create a new Standard record.

    Args:
        session: SQLAlchemy session
        code: Unique standard code (e.g., "SOL 8.3")
        description: Short description of the standard
        subject: Subject area (e.g., "Mathematics")
        grade_band: Grade range (e.g., "6-8")
        strand: Curriculum strand or category
        full_text: Full official text of the standard
        source: Origin framework (default "Virginia SOL")
        version: Version/year of the standard set
        standard_set: Standard set key (default "sol")

    Returns:
        The created Standard object
    """
    standard = Standard(
        code=code,
        description=description,
        subject=subject,
        grade_band=grade_band,
        strand=strand,
        full_text=full_text,
        source=source,
        version=version,
        standard_set=standard_set,
    )
    session.add(standard)
    session.commit()
    return standard


def get_standard(session: Session, standard_id: int) -> Optional[Standard]:
    """
    Fetch a single standard by ID.

    Args:
        session: SQLAlchemy session
        standard_id: The standard ID to look up

    Returns:
        Standard object or None if not found
    """
    return session.query(Standard).filter_by(id=standard_id).first()


def get_standard_by_code(session: Session, code: str) -> Optional[Standard]:
    """
    Fetch a single standard by its code.

    Args:
        session: SQLAlchemy session
        code: The standard code (e.g., "SOL 8.3")

    Returns:
        Standard object or None if not found
    """
    return session.query(Standard).filter_by(code=code).first()


def list_standards(
    session: Session,
    subject: Optional[str] = None,
    grade_band: Optional[str] = None,
    source: Optional[str] = None,
    standard_set: Optional[str] = None,
) -> List[Standard]:
    """
    List standards with optional filtering.

    Args:
        session: SQLAlchemy session
        subject: Filter by subject (e.g., "Mathematics")
        grade_band: Filter by grade band (e.g., "6-8")
        source: Filter by source (e.g., "Virginia SOL")
        standard_set: Filter by standard set key (e.g., "sol", "ccss_ela")

    Returns:
        List of Standard objects matching the filters
    """
    query = session.query(Standard)
    if subject:
        query = query.filter(Standard.subject == subject)
    if grade_band:
        query = query.filter(Standard.grade_band == grade_band)
    if source:
        query = query.filter(Standard.source == source)
    if standard_set:
        query = query.filter(Standard.standard_set == standard_set)
    return query.order_by(Standard.code).all()


def search_standards(
    session: Session,
    query_text: str,
    subject: Optional[str] = None,
    grade_band: Optional[str] = None,
    standard_set: Optional[str] = None,
) -> List[Standard]:
    """
    Search standards by code, description, or full text.

    Args:
        session: SQLAlchemy session
        query_text: Search term to match against code, description, or full_text
        subject: Optional subject filter
        grade_band: Optional grade band filter
        standard_set: Optional standard set filter

    Returns:
        List of Standard objects matching the search
    """
    like_pattern = f"%{query_text}%"
    q = session.query(Standard).filter(
        or_(
            Standard.code.ilike(like_pattern),
            Standard.description.ilike(like_pattern),
            Standard.full_text.ilike(like_pattern),
            Standard.strand.ilike(like_pattern),
        )
    )
    if subject:
        q = q.filter(Standard.subject == subject)
    if grade_band:
        q = q.filter(Standard.grade_band == grade_band)
    if standard_set:
        q = q.filter(Standard.standard_set == standard_set)
    return q.order_by(Standard.code).all()


def delete_standard(session: Session, standard_id: int) -> bool:
    """
    Delete a standard by ID.

    Args:
        session: SQLAlchemy session
        standard_id: ID of the standard to delete

    Returns:
        True if found and deleted, False otherwise
    """
    standard = session.query(Standard).filter_by(id=standard_id).first()
    if standard is None:
        return False
    session.delete(standard)
    session.commit()
    return True


def bulk_import_standards(session: Session, standards_data: list) -> int:
    """
    Import multiple standards from a list of dicts.
    Skips standards whose code already exists in the database.

    Args:
        session: SQLAlchemy session
        standards_data: List of dicts with standard fields

    Returns:
        Number of standards imported (excluding duplicates)
    """
    imported = 0
    for item in standards_data:
        existing = session.query(Standard).filter_by(code=item["code"]).first()
        if existing:
            continue
        standard = Standard(
            code=item["code"],
            # standard_id mirrors code (legacy column from migration 001)
            standard_id=item["code"],
            description=item["description"],
            subject=item["subject"],
            grade_band=item.get("grade_band"),
            strand=item.get("strand"),
            full_text=item.get("full_text"),
            source=item.get("source", "Virginia SOL"),
            version=item.get("version"),
            standard_set=item.get("standard_set", "sol"),
        )
        session.add(standard)
        imported += 1
    if imported > 0:
        session.commit()
    return imported


def load_standards_from_json(session: Session, json_path: str) -> int:
    """
    Load standards from a JSON file.
    The JSON should have a "standards" key containing a list of standard dicts.

    Args:
        session: SQLAlchemy session
        json_path: Path to the JSON file

    Returns:
        Number of standards imported

    Raises:
        FileNotFoundError: If the JSON file does not exist
        json.JSONDecodeError: If the file is not valid JSON
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    standards_list = data.get("standards", [])
    version = data.get("version")
    file_standard_set = data.get("standard_set")

    # Apply file-level version to each standard if not set
    if version:
        for item in standards_list:
            if not item.get("version"):
                item["version"] = version

    # Apply file-level source to each standard if not set
    source = data.get("source")
    if source:
        for item in standards_list:
            if not item.get("source"):
                item["source"] = source

    # Apply file-level standard_set to each standard if not set
    if file_standard_set:
        for item in standards_list:
            if not item.get("standard_set"):
                item["standard_set"] = file_standard_set

    return bulk_import_standards(session, standards_list)


def import_custom_standards(
    session: Session,
    json_data: list,
    set_name: str,
    set_label: str,
) -> int:
    """
    Allow teachers to import their own standards from a list of dicts.

    Each dict should have at minimum 'code', 'description', and 'subject'.
    The set_name and set_label are used to tag all imported standards.

    Args:
        session: SQLAlchemy session
        json_data: List of dicts with standard fields
        set_name: Internal key for the custom set (e.g., 'my_school')
        set_label: Display label for the custom set (e.g., 'My School Standards')

    Returns:
        Number of standards imported
    """
    for item in json_data:
        item["standard_set"] = set_name
        if not item.get("source"):
            item["source"] = set_label

    return bulk_import_standards(session, json_data)


def get_subjects(session: Session, standard_set: Optional[str] = None) -> List[str]:
    """
    Get distinct subjects from standards.

    Args:
        session: SQLAlchemy session
        standard_set: Optional filter by standard set

    Returns:
        Sorted list of unique subject names
    """
    q = session.query(Standard.subject).distinct()
    if standard_set:
        q = q.filter(Standard.standard_set == standard_set)
    results = q.all()
    return sorted([r[0] for r in results if r[0]])


def get_grade_bands(session: Session, standard_set: Optional[str] = None) -> List[str]:
    """
    Get distinct grade bands from standards.

    Args:
        session: SQLAlchemy session
        standard_set: Optional filter by standard set

    Returns:
        Sorted list of unique grade bands
    """
    q = session.query(Standard.grade_band).distinct()
    if standard_set:
        q = q.filter(Standard.standard_set == standard_set)
    results = q.all()
    return sorted([r[0] for r in results if r[0]])


def get_strands(session: Session, subject: Optional[str] = None, standard_set: Optional[str] = None) -> List[str]:
    """
    Get distinct strands, optionally filtered by subject.

    Args:
        session: SQLAlchemy session
        subject: Optional subject filter
        standard_set: Optional standard set filter

    Returns:
        Sorted list of unique strand names
    """
    q = session.query(Standard.strand).distinct()
    if subject:
        q = q.filter(Standard.subject == subject)
    if standard_set:
        q = q.filter(Standard.standard_set == standard_set)
    results = q.all()
    return sorted([r[0] for r in results if r[0]])


def standards_count(session: Session, standard_set: Optional[str] = None) -> int:
    """
    Get the total number of standards in the database.

    Args:
        session: SQLAlchemy session
        standard_set: Optional filter by standard set

    Returns:
        Total count of standards
    """
    q = session.query(Standard)
    if standard_set:
        q = q.filter(Standard.standard_set == standard_set)
    return q.count()


def get_standard_sets_in_db(session: Session) -> List[Dict]:
    """
    Get list of standard sets that have been loaded into the database,
    with counts.

    Args:
        session: SQLAlchemy session

    Returns:
        List of dicts with 'key', 'label', 'count'
    """
    from sqlalchemy import func

    results = session.query(Standard.standard_set, func.count(Standard.id)).group_by(Standard.standard_set).all()
    sets = []
    for set_key, count in results:
        if not set_key:
            set_key = "sol"
        label = STANDARD_SETS.get(set_key, {}).get("label", set_key)
        sets.append({"key": set_key, "label": label, "count": count})
    return sorted(sets, key=lambda x: x["label"])
