"""
Performance data import module for QuizWeaver.

Handles CSV parsing, validation, and import of performance data
into the database. Supports manual entry, CSV upload, and
per-question quiz score import.
"""

import csv
import io
import json
import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.database import PerformanceData, Quiz, Question

logger = logging.getLogger(__name__)


def get_sample_csv() -> str:
    """Return a downloadable CSV template with example rows.

    Returns:
        CSV string with header and 3 example rows.
    """
    lines = [
        "topic,score,date,standard,weak_areas,sample_size",
        "photosynthesis,78,2025-03-15,SOL 7.1,light reactions;calvin cycle,25",
        "cell division,65,2025-03-16,SOL 7.2,mitosis phases,25",
        "genetics,85,2025-03-17,SOL 7.3,,25",
    ]
    return "\n".join(lines) + "\n"


def validate_csv_row(
    row: Dict[str, str], row_num: int
) -> Tuple[Optional[Dict], Optional[str]]:
    """Validate and normalize a single CSV row.

    Args:
        row: Dict from csv.DictReader (keys are column headers).
        row_num: 1-based row number for error messages.

    Returns:
        Tuple of (normalized_dict, error_string).
        On success error_string is None; on failure normalized_dict is None.
    """
    # Required: topic
    topic = (row.get("topic") or "").strip()
    if not topic:
        return None, f"Row {row_num}: missing required field 'topic'"

    # Required: score (0-100 range, converted to 0.0-1.0)
    score_raw = (row.get("score") or "").strip()
    if not score_raw:
        return None, f"Row {row_num}: missing required field 'score'"

    try:
        score = float(score_raw)
    except ValueError:
        return None, f"Row {row_num}: invalid score '{score_raw}' (must be a number)"

    if score < 0 or score > 100:
        return None, f"Row {row_num}: score {score} out of range (must be 0-100)"

    avg_score = score / 100.0  # Convert to 0.0-1.0

    # Optional: date
    date_raw = (row.get("date") or "").strip()
    parsed_date = date.today()
    if date_raw:
        try:
            parsed_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except ValueError:
            return None, f"Row {row_num}: invalid date '{date_raw}' (use YYYY-MM-DD)"

    # Optional: standard
    standard = (row.get("standard") or "").strip() or None

    # Optional: weak_areas (semicolon-delimited)
    weak_areas_raw = (row.get("weak_areas") or "").strip()
    weak_areas = (
        [w.strip() for w in weak_areas_raw.split(";") if w.strip()]
        if weak_areas_raw
        else []
    )

    # Optional: sample_size
    sample_size_raw = (row.get("sample_size") or "").strip()
    sample_size = 0
    if sample_size_raw:
        try:
            sample_size = int(sample_size_raw)
            if sample_size < 0:
                return None, f"Row {row_num}: sample_size must be >= 0"
        except ValueError:
            return None, f"Row {row_num}: invalid sample_size '{sample_size_raw}'"

    return {
        "topic": topic,
        "avg_score": avg_score,
        "date": parsed_date,
        "standard": standard,
        "weak_areas": weak_areas,
        "sample_size": sample_size,
    }, None


def parse_performance_csv(csv_text: str) -> Tuple[List[Dict], List[str]]:
    """Parse a CSV string into validated performance rows.

    Args:
        csv_text: Raw CSV text with header row.

    Returns:
        Tuple of (valid_rows, errors).
        Each valid_row is a normalized dict ready for DB import.
    """
    rows = []
    errors = []

    reader = csv.DictReader(io.StringIO(csv_text))

    for i, raw_row in enumerate(reader, start=1):
        # Skip completely empty rows (check only named columns)
        topic_val = (raw_row.get("topic") or "").strip()
        score_val = (raw_row.get("score") or "").strip()
        if not topic_val and not score_val:
            continue

        normalized, error = validate_csv_row(raw_row, i)
        if error:
            errors.append(error)
        else:
            rows.append(normalized)

    return rows, errors


def import_csv_data(
    session: Session,
    class_id: int,
    csv_text: str,
    quiz_id: Optional[int] = None,
) -> Tuple[int, List[str]]:
    """Parse CSV and write performance records to the database.

    Args:
        session: SQLAlchemy session.
        class_id: Class to associate data with.
        csv_text: Raw CSV text.
        quiz_id: Optional quiz ID to link records to.

    Returns:
        Tuple of (records_created, errors).
    """
    rows, errors = parse_performance_csv(csv_text)

    if not rows:
        return 0, errors

    count = 0
    for row in rows:
        record = PerformanceData(
            class_id=class_id,
            quiz_id=quiz_id,
            topic=row["topic"],
            avg_score=row["avg_score"],
            weak_areas=json.dumps(row["weak_areas"]) if row["weak_areas"] else None,
            standard=row["standard"],
            source="csv_upload",
            sample_size=row["sample_size"],
            date=row["date"],
        )
        session.add(record)
        count += 1

    session.commit()
    return count, errors


def import_quiz_scores(
    session: Session,
    class_id: int,
    quiz_id: int,
    question_scores: Dict[int, float],
    sample_size: int = 0,
    score_date: Optional[date] = None,
) -> int:
    """Import per-question class averages as performance records.

    Groups questions by topic (from question data) and creates
    one PerformanceData record per topic.

    Args:
        session: SQLAlchemy session.
        class_id: Class ID.
        quiz_id: Quiz these scores came from.
        question_scores: Dict mapping question_id -> class average (0-100).
        sample_size: Number of students.
        score_date: Date of assessment (defaults to today).

    Returns:
        Number of records created.
    """
    if not question_scores:
        return 0

    score_date = score_date or date.today()

    # Load questions and group scores by topic
    topic_scores: Dict[str, List[float]] = {}
    topic_standards: Dict[str, Optional[str]] = {}

    for qid, score_pct in question_scores.items():
        question = session.query(Question).filter_by(id=qid).first()
        if not question:
            continue

        # Extract topic from question data
        q_data = question.data
        if isinstance(q_data, str):
            try:
                q_data = json.loads(q_data)
            except (json.JSONDecodeError, ValueError):
                q_data = {}
        if not isinstance(q_data, dict):
            q_data = {}

        # Use question text as topic fallback
        topic = q_data.get("topic") or question.text or f"Question {qid}"
        # Truncate long question text used as topic
        if len(topic) > 100:
            topic = topic[:97] + "..."

        if topic not in topic_scores:
            topic_scores[topic] = []
            topic_standards[topic] = q_data.get("standard")
        topic_scores[topic].append(score_pct / 100.0)

    # Create one record per topic
    count = 0
    for topic, scores in topic_scores.items():
        avg = sum(scores) / len(scores)
        record = PerformanceData(
            class_id=class_id,
            quiz_id=quiz_id,
            topic=topic,
            avg_score=avg,
            standard=topic_standards.get(topic),
            source="quiz_score",
            sample_size=sample_size,
            date=score_date,
        )
        session.add(record)
        count += 1

    session.commit()
    return count
