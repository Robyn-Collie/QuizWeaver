"""
Curriculum pacing guide module for QuizWeaver.

Provides CRUD operations for pacing guides -- structured timelines that map
standards to weeks/units across a school year.  Pacing guides are
DETERMINISTIC planning tools (rule-based, not AI-generated).

A pacing guide belongs to a class and contains ordered units, each spanning
a range of weeks with associated standards, topics, and assessment types.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Session, relationship

from src.database import Base, Class, LessonLog

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TOTAL_WEEKS = 36

ASSESSMENT_TYPES = [
    "quiz",
    "test",
    "project",
    "exit_ticket",
    "performance_task",
]

# Preset pacing templates
PACING_TEMPLATES = {
    "quarterly": {
        "label": "Quarterly",
        "description": "8 units across 4 quarters with assessments at weeks 9, 18, 27, 36.",
        "units_per_quarter": 2,
        "quarters": 4,
        "assessment_weeks": [9, 18, 27, 36],
    },
    "monthly": {
        "label": "Monthly",
        "description": "9 units (one per month) with monthly assessments.",
        "units_per_month": 1,
        "months": 9,
        "assessment_weeks": [4, 8, 12, 16, 20, 24, 28, 32, 36],
    },
    "semester": {
        "label": "Semester",
        "description": "8 units across 2 semesters with midterm and final assessments.",
        "units_per_semester": 4,
        "semesters": 2,
        "assessment_weeks": [18, 36],
    },
}


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class PacingGuide(Base):
    """Represents a curriculum pacing guide for a class.

    Attributes:
        id: Primary key.
        class_id: Foreign key to the Class this guide belongs to.
        title: Title of the pacing guide.
        school_year: School year label (e.g., '2025-2026').
        total_weeks: Total instructional weeks in the school year.
        created_at: Timestamp when the guide was created.
        updated_at: Timestamp of last update.
        units: Relationship to PacingGuideUnit objects.
    """

    __tablename__ = "pacing_guides"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    title = Column(String, nullable=False)
    school_year = Column(String)
    total_weeks = Column(Integer, default=DEFAULT_TOTAL_WEEKS)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    units = relationship(
        "PacingGuideUnit",
        back_populates="guide",
        order_by="PacingGuideUnit.unit_number",
        cascade="all, delete-orphan",
    )


class PacingGuideUnit(Base):
    """Represents a single unit within a pacing guide.

    Attributes:
        id: Primary key.
        pacing_guide_id: Foreign key to the parent PacingGuide.
        unit_number: Display order / unit number.
        title: Title of the unit.
        start_week: First week of the unit (1-based).
        end_week: Last week of the unit (inclusive).
        standards: JSON array of standard codes.
        topics: JSON array of topic strings.
        assessment_type: Type of assessment for this unit.
        notes: Free-form teacher notes.
        guide: Relationship to the parent PacingGuide.
    """

    __tablename__ = "pacing_guide_units"
    id = Column(Integer, primary_key=True)
    pacing_guide_id = Column(Integer, ForeignKey("pacing_guides.id"), nullable=False)
    unit_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    start_week = Column(Integer, nullable=False)
    end_week = Column(Integer, nullable=False)
    standards = Column(Text)  # JSON array
    topics = Column(Text)  # JSON array
    assessment_type = Column(String)
    notes = Column(Text)

    guide = relationship("PacingGuide", back_populates="units")


# ---------------------------------------------------------------------------
# Helper: parse JSON text fields
# ---------------------------------------------------------------------------


def _parse_json_list(value: Any) -> list:
    """Parse a JSON text field that should be a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return []


# ---------------------------------------------------------------------------
# CRUD Functions
# ---------------------------------------------------------------------------


def create_pacing_guide(
    session: Session,
    class_id: int,
    title: str,
    school_year: Optional[str] = None,
    total_weeks: int = DEFAULT_TOTAL_WEEKS,
) -> PacingGuide:
    """Create a new pacing guide for a class.

    Args:
        session: SQLAlchemy session.
        class_id: ID of the class this guide belongs to.
        title: Title of the pacing guide.
        school_year: School year label (e.g., '2025-2026').
        total_weeks: Total instructional weeks (default 36).

    Returns:
        The created PacingGuide object.

    Raises:
        ValueError: If class_id does not exist, title is empty,
            or total_weeks is not positive.
    """
    if not title or not title.strip():
        raise ValueError("Title is required.")
    if total_weeks < 1:
        raise ValueError("total_weeks must be at least 1.")
    cls = session.query(Class).filter_by(id=class_id).first()
    if cls is None:
        raise ValueError(f"Class with id {class_id} not found.")

    guide = PacingGuide(
        class_id=class_id,
        title=title.strip(),
        school_year=school_year,
        total_weeks=total_weeks,
    )
    session.add(guide)
    session.commit()
    return guide


def get_pacing_guide(session: Session, guide_id: int) -> Optional[PacingGuide]:
    """Get a pacing guide with all its units.

    Args:
        session: SQLAlchemy session.
        guide_id: ID of the pacing guide.

    Returns:
        PacingGuide object or None if not found.
    """
    return session.query(PacingGuide).filter_by(id=guide_id).first()


def list_pacing_guides(
    session: Session, class_id: Optional[int] = None
) -> List[PacingGuide]:
    """List all pacing guides, optionally filtered by class.

    Args:
        session: SQLAlchemy session.
        class_id: Optional class filter.

    Returns:
        List of PacingGuide objects ordered by creation date (newest first).
    """
    query = session.query(PacingGuide)
    if class_id is not None:
        query = query.filter(PacingGuide.class_id == class_id)
    return query.order_by(PacingGuide.created_at.desc()).all()


def delete_pacing_guide(session: Session, guide_id: int) -> bool:
    """Delete a pacing guide and all its units.

    Args:
        session: SQLAlchemy session.
        guide_id: ID of the pacing guide to delete.

    Returns:
        True if deleted, False if not found.
    """
    guide = session.query(PacingGuide).filter_by(id=guide_id).first()
    if guide is None:
        return False
    session.delete(guide)
    session.commit()
    return True


def update_pacing_guide(
    session: Session, guide_id: int, **kwargs: Any
) -> Optional[PacingGuide]:
    """Update pacing guide metadata.

    Args:
        session: SQLAlchemy session.
        guide_id: ID of the pacing guide.
        **kwargs: Fields to update (title, school_year, total_weeks).

    Returns:
        Updated PacingGuide or None if not found.
    """
    guide = session.query(PacingGuide).filter_by(id=guide_id).first()
    if guide is None:
        return None
    for key in ("title", "school_year", "total_weeks"):
        if key in kwargs:
            setattr(guide, key, kwargs[key])
    guide.updated_at = datetime.utcnow()
    session.commit()
    return guide


# ---------------------------------------------------------------------------
# Unit CRUD
# ---------------------------------------------------------------------------


def add_unit(
    session: Session,
    guide_id: int,
    unit_number: int,
    title: str,
    start_week: int,
    end_week: int,
    standards: Optional[List[str]] = None,
    topics: Optional[List[str]] = None,
    assessment_type: Optional[str] = None,
    notes: Optional[str] = None,
) -> PacingGuideUnit:
    """Add a unit to a pacing guide.

    Args:
        session: SQLAlchemy session.
        guide_id: ID of the parent pacing guide.
        unit_number: Unit number / display order.
        title: Title of the unit.
        start_week: First week of the unit (1-based).
        end_week: Last week of the unit (inclusive).
        standards: List of standard codes.
        topics: List of topic strings.
        assessment_type: Assessment type for this unit.
        notes: Teacher notes.

    Returns:
        The created PacingGuideUnit object.

    Raises:
        ValueError: If validation fails (guide not found, weeks invalid, etc.).
    """
    guide = session.query(PacingGuide).filter_by(id=guide_id).first()
    if guide is None:
        raise ValueError(f"Pacing guide with id {guide_id} not found.")
    if not title or not title.strip():
        raise ValueError("Unit title is required.")
    if start_week < 1:
        raise ValueError("start_week must be at least 1.")
    if end_week < start_week:
        raise ValueError("end_week must be >= start_week.")
    if end_week > guide.total_weeks:
        raise ValueError(
            f"end_week ({end_week}) exceeds total_weeks ({guide.total_weeks})."
        )
    if assessment_type and assessment_type not in ASSESSMENT_TYPES:
        raise ValueError(
            f"Invalid assessment_type '{assessment_type}'. "
            f"Valid types: {ASSESSMENT_TYPES}"
        )

    # Check for week overlap with existing units
    existing_units = (
        session.query(PacingGuideUnit)
        .filter_by(pacing_guide_id=guide_id)
        .all()
    )
    for eu in existing_units:
        if start_week <= eu.end_week and end_week >= eu.start_week:
            raise ValueError(
                f"Week range {start_week}-{end_week} overlaps with "
                f"Unit {eu.unit_number} ({eu.start_week}-{eu.end_week})."
            )

    unit = PacingGuideUnit(
        pacing_guide_id=guide_id,
        unit_number=unit_number,
        title=title.strip(),
        start_week=start_week,
        end_week=end_week,
        standards=json.dumps(standards or []),
        topics=json.dumps(topics or []),
        assessment_type=assessment_type,
        notes=notes,
    )
    session.add(unit)
    guide.updated_at = datetime.utcnow()
    session.commit()
    return unit


def update_unit(session: Session, unit_id: int, **kwargs: Any) -> Optional[PacingGuideUnit]:
    """Update an existing unit.

    Args:
        session: SQLAlchemy session.
        unit_id: ID of the unit to update.
        **kwargs: Fields to update.

    Returns:
        Updated unit or None if not found.
    """
    unit = session.query(PacingGuideUnit).filter_by(id=unit_id).first()
    if unit is None:
        return None

    allowed = (
        "unit_number",
        "title",
        "start_week",
        "end_week",
        "standards",
        "topics",
        "assessment_type",
        "notes",
    )
    for key in allowed:
        if key in kwargs:
            value = kwargs[key]
            if key in ("standards", "topics") and isinstance(value, list):
                value = json.dumps(value)
            setattr(unit, key, value)

    # Update parent guide timestamp
    guide = session.query(PacingGuide).filter_by(id=unit.pacing_guide_id).first()
    if guide:
        guide.updated_at = datetime.utcnow()
    session.commit()
    return unit


def delete_unit(session: Session, unit_id: int) -> bool:
    """Delete a unit from a pacing guide.

    Args:
        session: SQLAlchemy session.
        unit_id: ID of the unit to delete.

    Returns:
        True if deleted, False if not found.
    """
    unit = session.query(PacingGuideUnit).filter_by(id=unit_id).first()
    if unit is None:
        return False
    guide = session.query(PacingGuide).filter_by(id=unit.pacing_guide_id).first()
    session.delete(unit)
    if guide:
        guide.updated_at = datetime.utcnow()
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Template-Based Generation
# ---------------------------------------------------------------------------


def generate_from_template(
    session: Session,
    class_id: int,
    title: str,
    template_name: str,
    school_year: Optional[str] = None,
    standards_list: Optional[List[str]] = None,
    total_weeks: int = DEFAULT_TOTAL_WEEKS,
) -> PacingGuide:
    """Generate a pacing guide from a preset template.

    Distributes standards evenly across units and creates a guide with
    the appropriate structure for the chosen template.

    Args:
        session: SQLAlchemy session.
        class_id: ID of the class.
        title: Title for the pacing guide.
        template_name: Key from PACING_TEMPLATES.
        school_year: School year label.
        standards_list: List of standard codes to distribute.
        total_weeks: Total weeks (default 36).

    Returns:
        The created PacingGuide with units.

    Raises:
        ValueError: If template_name is not recognized.
    """
    if template_name not in PACING_TEMPLATES:
        raise ValueError(
            f"Unknown template '{template_name}'. "
            f"Available: {list(PACING_TEMPLATES.keys())}"
        )

    template = PACING_TEMPLATES[template_name]
    guide = create_pacing_guide(
        session,
        class_id=class_id,
        title=title,
        school_year=school_year,
        total_weeks=total_weeks,
    )

    # Determine unit count and week ranges
    if template_name == "quarterly":
        num_units = template["units_per_quarter"] * template["quarters"]
        weeks_per_unit = total_weeks // num_units
    elif template_name == "monthly":
        num_units = template["months"]
        weeks_per_unit = total_weeks // num_units
    elif template_name == "semester":
        num_units = template["units_per_semester"] * template["semesters"]
        weeks_per_unit = total_weeks // num_units
    else:
        num_units = 8
        weeks_per_unit = total_weeks // num_units

    # Distribute standards across units
    standards = standards_list or []
    standards_per_unit = _distribute_items(standards, num_units)

    # Create units
    for i in range(num_units):
        start_week = i * weeks_per_unit + 1
        # Last unit absorbs any remaining weeks
        end_week = total_weeks if i == num_units - 1 else (i + 1) * weeks_per_unit

        unit_standards = standards_per_unit[i] if i < len(standards_per_unit) else []

        # Determine assessment type based on position
        assessment_type = "quiz"
        if end_week in template.get("assessment_weeks", []):
            assessment_type = "test"

        unit = PacingGuideUnit(
            pacing_guide_id=guide.id,
            unit_number=i + 1,
            title=f"Unit {i + 1}",
            start_week=start_week,
            end_week=end_week,
            standards=json.dumps(unit_standards),
            topics=json.dumps([]),
            assessment_type=assessment_type,
        )
        session.add(unit)

    session.commit()
    # Refresh to load units relationship
    session.refresh(guide)
    return guide


def _distribute_items(items: list, num_buckets: int) -> List[list]:
    """Distribute items as evenly as possible across buckets.

    Args:
        items: List of items to distribute.
        num_buckets: Number of buckets.

    Returns:
        List of lists, one per bucket.
    """
    if num_buckets <= 0:
        return []
    buckets: List[list] = [[] for _ in range(num_buckets)]
    if not items:
        return buckets
    for i, item in enumerate(items):
        buckets[i % num_buckets].append(item)
    return buckets


# ---------------------------------------------------------------------------
# Progress & Current Unit
# ---------------------------------------------------------------------------


def get_current_unit(
    session: Session,
    guide_id: int,
    current_week: Optional[int] = None,
) -> Optional[PacingGuideUnit]:
    """Get the unit that corresponds to the current week.

    Args:
        session: SQLAlchemy session.
        guide_id: ID of the pacing guide.
        current_week: Week number to look up. If None, tries to
            calculate from the current date (defaults to week 1).

    Returns:
        The matching PacingGuideUnit, or None if no unit covers that week.
    """
    if current_week is None:
        current_week = 1  # Default to first week if not specified

    units = (
        session.query(PacingGuideUnit)
        .filter_by(pacing_guide_id=guide_id)
        .order_by(PacingGuideUnit.start_week)
        .all()
    )
    for unit in units:
        if unit.start_week <= current_week <= unit.end_week:
            return unit
    return None


def get_progress(session: Session, guide_id: int) -> Dict[str, Any]:
    """Calculate progress for a pacing guide based on lesson logs.

    Compares the topics in each unit against logged lesson topics for
    the guide's class to determine coverage.

    Args:
        session: SQLAlchemy session.
        guide_id: ID of the pacing guide.

    Returns:
        Dict with:
            - total_units: Total number of units.
            - covered_units: Number of units with at least one matching lesson.
            - percent_complete: Percentage (0-100).
            - unit_details: List of dicts per unit with coverage info.
    """
    guide = session.query(PacingGuide).filter_by(id=guide_id).first()
    if guide is None:
        return {
            "total_units": 0,
            "covered_units": 0,
            "percent_complete": 0,
            "unit_details": [],
        }

    units = (
        session.query(PacingGuideUnit)
        .filter_by(pacing_guide_id=guide_id)
        .order_by(PacingGuideUnit.unit_number)
        .all()
    )

    if not units:
        return {
            "total_units": 0,
            "covered_units": 0,
            "percent_complete": 0,
            "unit_details": [],
        }

    # Get all lesson logs for this class
    lesson_logs = (
        session.query(LessonLog)
        .filter_by(class_id=guide.class_id)
        .all()
    )

    # Collect all taught topics and standards from lesson logs
    taught_topics = set()
    taught_standards = set()
    for log in lesson_logs:
        topics = _parse_json_list(log.topics)
        for t in topics:
            taught_topics.add(t.lower().strip())
        stds = _parse_json_list(log.standards_addressed)
        for s in stds:
            taught_standards.add(s.strip())

    total_units = len(units)
    covered_units = 0
    unit_details = []

    for unit in units:
        unit_topics = _parse_json_list(unit.topics)
        unit_standards = _parse_json_list(unit.standards)

        # A unit is "covered" if at least one of its topics or standards
        # has been taught
        topic_matches = [
            t for t in unit_topics if t.lower().strip() in taught_topics
        ]
        standard_matches = [
            s for s in unit_standards if s.strip() in taught_standards
        ]
        is_covered = bool(topic_matches or standard_matches)

        if is_covered:
            covered_units += 1

        unit_details.append(
            {
                "unit_number": unit.unit_number,
                "title": unit.title,
                "is_covered": is_covered,
                "topic_matches": topic_matches,
                "standard_matches": standard_matches,
                "total_topics": len(unit_topics),
                "total_standards": len(unit_standards),
            }
        )

    percent = round(covered_units / total_units * 100) if total_units > 0 else 0

    return {
        "total_units": total_units,
        "covered_units": covered_units,
        "percent_complete": percent,
        "unit_details": unit_details,
    }
