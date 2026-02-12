"""
Performance analytics and gap analysis engine for QuizWeaver.

Compares assumed knowledge (what was taught) against actual performance
(assessment scores) to identify gaps and inform re-teaching decisions.
"""

import json
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.database import PerformanceData
from src.lesson_tracker import get_assumed_knowledge

logger = logging.getLogger(__name__)

# Maps assumed knowledge depth (1-5) to expected performance score
DEPTH_EXPECTATION = {
    1: 0.40,  # introduced
    2: 0.55,  # reinforced
    3: 0.70,  # practiced
    4: 0.85,  # mastered
    5: 0.95,  # expert
}


def _severity(gap: float) -> str:
    """Classify gap severity based on difference from expectation.

    Args:
        gap: actual - expected (negative means underperforming).

    Returns:
        One of "critical", "concerning", "on_track", "exceeding".
    """
    if gap <= -0.25:
        return "critical"
    elif gap <= -0.10:
        return "concerning"
    elif gap < 0.10:
        return "on_track"
    else:
        return "exceeding"


def compute_gap_analysis(session: Session, class_id: int) -> List[Dict[str, Any]]:
    """Compare assumed knowledge against actual performance data.

    For each topic that has performance data, computes the gap between
    actual score and expected score (based on teaching depth).

    Args:
        session: SQLAlchemy session.
        class_id: Class to analyze.

    Returns:
        List of gap analysis dicts sorted by gap (worst first).
    """
    knowledge = get_assumed_knowledge(session, class_id)

    # Aggregate performance data by topic
    perf_rows = session.query(PerformanceData).filter(PerformanceData.class_id == class_id).all()

    if not perf_rows:
        return []

    # Group by topic
    topic_data: Dict[str, Dict] = {}
    for row in perf_rows:
        topic = row.topic
        if topic not in topic_data:
            topic_data[topic] = {
                "scores": [],
                "last_assessed": row.date,
                "weak_areas": [],
            }
        topic_data[topic]["scores"].append(row.avg_score)

        if row.date and (topic_data[topic]["last_assessed"] is None or row.date > topic_data[topic]["last_assessed"]):
            topic_data[topic]["last_assessed"] = row.date

        # Collect weak areas
        weak = row.weak_areas
        if isinstance(weak, str):
            try:
                weak = json.loads(weak)
            except (json.JSONDecodeError, ValueError):
                weak = []
        if isinstance(weak, list):
            for w in weak:
                if w and w not in topic_data[topic]["weak_areas"]:
                    topic_data[topic]["weak_areas"].append(w)

    results = []
    for topic, data in topic_data.items():
        avg_score = sum(data["scores"]) / len(data["scores"])

        # Get expected score from knowledge depth
        depth = 0
        if topic in knowledge:
            depth = knowledge[topic].get("depth", 0)
        expected = DEPTH_EXPECTATION.get(depth, 0.40)

        gap = avg_score - expected
        severity = _severity(gap)

        results.append(
            {
                "topic": topic,
                "depth": depth,
                "expected_score": expected,
                "actual_score": round(avg_score, 3),
                "gap": round(gap, 3),
                "gap_severity": severity,
                "data_points": len(data["scores"]),
                "last_assessed": (data["last_assessed"].isoformat() if data["last_assessed"] else None),
                "weak_areas": data["weak_areas"],
            }
        )

    # Sort by gap ascending (worst gaps first)
    results.sort(key=lambda x: x["gap"])
    return results


def get_topic_trends(
    session: Session,
    class_id: int,
    topic: Optional[str] = None,
    days: int = 90,
) -> List[Dict[str, Any]]:
    """Get performance trend data over time.

    Args:
        session: SQLAlchemy session.
        class_id: Class to query.
        topic: Optional topic filter.
        days: Number of days to look back.

    Returns:
        List of {date, topic, avg_score} dicts sorted by date.
    """
    threshold = date.today() - timedelta(days=days)

    query = session.query(PerformanceData).filter(
        PerformanceData.class_id == class_id,
        PerformanceData.date >= threshold,
    )

    if topic:
        query = query.filter(PerformanceData.topic == topic)

    rows = query.order_by(PerformanceData.date).all()

    return [
        {
            "date": row.date.isoformat() if row.date else None,
            "topic": row.topic,
            "avg_score": row.avg_score,
        }
        for row in rows
    ]


def get_class_summary(session: Session, class_id: int) -> Dict[str, Any]:
    """Get overall performance summary for a class.

    Args:
        session: SQLAlchemy session.
        class_id: Class to summarize.

    Returns:
        Summary dict with overall stats.
    """
    perf_rows = session.query(PerformanceData).filter(PerformanceData.class_id == class_id).all()

    if not perf_rows:
        return {
            "total_topics_assessed": 0,
            "overall_avg_score": 0.0,
            "topics_at_risk": 0,
            "topics_on_track": 0,
            "strongest_topic": None,
            "weakest_topic": None,
            "total_data_points": 0,
        }

    # Group by topic
    topic_scores: Dict[str, List[float]] = {}
    for row in perf_rows:
        if row.topic not in topic_scores:
            topic_scores[row.topic] = []
        topic_scores[row.topic].append(row.avg_score)

    # Compute averages per topic
    topic_avgs = {t: sum(s) / len(s) for t, s in topic_scores.items()}

    all_scores = [s for scores in topic_scores.values() for s in scores]
    overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0.0

    # At-risk: avg < 0.60
    at_risk = sum(1 for avg in topic_avgs.values() if avg < 0.60)
    on_track = sum(1 for avg in topic_avgs.values() if avg >= 0.60)

    strongest = max(topic_avgs, key=topic_avgs.get) if topic_avgs else None
    weakest = min(topic_avgs, key=topic_avgs.get) if topic_avgs else None

    return {
        "total_topics_assessed": len(topic_avgs),
        "overall_avg_score": round(overall_avg, 3),
        "topics_at_risk": at_risk,
        "topics_on_track": on_track,
        "strongest_topic": strongest,
        "weakest_topic": weakest,
        "total_data_points": len(perf_rows),
    }


def get_standards_mastery(session: Session, class_id: int) -> List[Dict[str, Any]]:
    """Get mastery levels grouped by standard.

    Args:
        session: SQLAlchemy session.
        class_id: Class to analyze.

    Returns:
        List of {standard, avg_score, topics, mastery_level} dicts.
    """
    perf_rows = (
        session.query(PerformanceData)
        .filter(
            PerformanceData.class_id == class_id,
            PerformanceData.standard.isnot(None),
            PerformanceData.standard != "",
        )
        .all()
    )

    # Group by standard
    standard_data: Dict[str, Dict] = {}
    for row in perf_rows:
        std = row.standard
        if std not in standard_data:
            standard_data[std] = {"scores": [], "topics": set()}
        standard_data[std]["scores"].append(row.avg_score)
        standard_data[std]["topics"].add(row.topic)

    results = []
    for std, data in standard_data.items():
        avg = sum(data["scores"]) / len(data["scores"])

        if avg >= 0.85:
            level = "mastered"
        elif avg >= 0.70:
            level = "proficient"
        elif avg >= 0.50:
            level = "developing"
        else:
            level = "beginning"

        results.append(
            {
                "standard": std,
                "avg_score": round(avg, 3),
                "topics": sorted(data["topics"]),
                "mastery_level": level,
            }
        )

    results.sort(key=lambda x: x["avg_score"])
    return results


def identify_weak_areas(
    session: Session,
    class_id: int,
    threshold: float = 0.60,
) -> List[Dict[str, Any]]:
    """Identify topics scoring below a threshold.

    Args:
        session: SQLAlchemy session.
        class_id: Class to analyze.
        threshold: Score cutoff (default 0.60).

    Returns:
        List of weak topic dicts with recommended actions.
    """
    gap_data = compute_gap_analysis(session, class_id)

    results = []
    for item in gap_data:
        if item["actual_score"] < threshold:
            # Determine recommended action
            if item["gap_severity"] == "critical":
                action = "Re-teach with different approach; consider small group intervention"
            elif item["gap_severity"] == "concerning":
                action = "Review and reinforce; provide additional practice"
            else:
                action = "Monitor; provide supplemental resources"

            results.append(
                {
                    "topic": item["topic"],
                    "avg_score": item["actual_score"],
                    "gap": item["gap"],
                    "recommended_action": action,
                }
            )

    return results
