"""
Standards database module for QuizWeaver.

Provides CRUD operations and search functionality for educational standards.
Standards are DETERMINISTIC data -- rule-based, not AI-generated.
This is a core AI literacy principle: standards alignment uses rule-based
systems, not LLM inference.
"""

import json
import os
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.database import Standard


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
) -> List[Standard]:
    """
    List standards with optional filtering.

    Args:
        session: SQLAlchemy session
        subject: Filter by subject (e.g., "Mathematics")
        grade_band: Filter by grade band (e.g., "6-8")
        source: Filter by source (e.g., "Virginia SOL")

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
    return query.order_by(Standard.code).all()


def search_standards(
    session: Session,
    query_text: str,
    subject: Optional[str] = None,
    grade_band: Optional[str] = None,
) -> List[Standard]:
    """
    Search standards by code, description, or full text.

    Args:
        session: SQLAlchemy session
        query_text: Search term to match against code, description, or full_text
        subject: Optional subject filter
        grade_band: Optional grade band filter

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
            description=item["description"],
            subject=item["subject"],
            grade_band=item.get("grade_band"),
            strand=item.get("strand"),
            full_text=item.get("full_text"),
            source=item.get("source", "Virginia SOL"),
            version=item.get("version"),
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
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    standards_list = data.get("standards", [])
    version = data.get("version")

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

    return bulk_import_standards(session, standards_list)


def get_subjects(session: Session) -> List[str]:
    """
    Get distinct subjects from standards.

    Args:
        session: SQLAlchemy session

    Returns:
        Sorted list of unique subject names
    """
    results = session.query(Standard.subject).distinct().all()
    return sorted([r[0] for r in results if r[0]])


def get_grade_bands(session: Session) -> List[str]:
    """
    Get distinct grade bands from standards.

    Args:
        session: SQLAlchemy session

    Returns:
        Sorted list of unique grade bands
    """
    results = session.query(Standard.grade_band).distinct().all()
    return sorted([r[0] for r in results if r[0]])


def get_strands(session: Session, subject: Optional[str] = None) -> List[str]:
    """
    Get distinct strands, optionally filtered by subject.

    Args:
        session: SQLAlchemy session
        subject: Optional subject filter

    Returns:
        Sorted list of unique strand names
    """
    q = session.query(Standard.strand).distinct()
    if subject:
        q = q.filter(Standard.subject == subject)
    results = q.all()
    return sorted([r[0] for r in results if r[0]])


def standards_count(session: Session) -> int:
    """
    Get the total number of standards in the database.

    Args:
        session: SQLAlchemy session

    Returns:
        Total count of standards
    """
    return session.query(Standard).count()
