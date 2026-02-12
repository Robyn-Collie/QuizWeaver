"""
Tests for QuizWeaver performance analytics and gap analysis engine.

Covers gap analysis, trends, class summary, standards mastery,
and weak area identification.
"""

import json
import os
import tempfile
from datetime import date, timedelta

import pytest

from src.database import (
    Base,
    Class,
    PerformanceData,
    get_engine,
    get_session,
)
from src.lesson_tracker import log_lesson
from src.performance_analytics import (
    DEPTH_EXPECTATION,
    compute_gap_analysis,
    get_class_summary,
    get_standards_mastery,
    get_topic_trends,
    identify_weak_areas,
)


@pytest.fixture
def db_session():
    """Create a temporary database with test data."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Test Science",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1", "SOL 7.2"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    yield session, cls.id

    session.close()
    engine.dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


def _seed_performance(session, class_id, topic, score, standard=None, days_ago=0):
    """Helper to add a performance record."""
    record = PerformanceData(
        class_id=class_id,
        topic=topic,
        avg_score=score,
        standard=standard,
        source="manual_entry",
        sample_size=25,
        date=date.today() - timedelta(days=days_ago),
    )
    session.add(record)
    session.commit()
    return record


class TestGapAnalysis:
    def test_basic_gap_analysis(self, db_session):
        session, class_id = db_session
        # Teach photosynthesis (depth 1)
        log_lesson(session, class_id, "Learned about photosynthesis", topics=["photosynthesis"])
        # Score below expectation for depth 1 (expected 0.40)
        _seed_performance(session, class_id, "photosynthesis", 0.30)

        gaps = compute_gap_analysis(session, class_id)
        assert len(gaps) == 1
        assert gaps[0]["topic"] == "photosynthesis"
        assert gaps[0]["depth"] == 1
        assert gaps[0]["expected_score"] == 0.40
        assert gaps[0]["actual_score"] == pytest.approx(0.30)
        assert gaps[0]["gap"] < 0  # underperforming

    def test_no_data_returns_empty(self, db_session):
        session, class_id = db_session
        gaps = compute_gap_analysis(session, class_id)
        assert gaps == []

    def test_severity_levels(self, db_session):
        session, class_id = db_session

        # Default depth 0 → expected 0.40
        # Critical: gap <= -0.25 → actual <= 0.15
        _seed_performance(session, class_id, "critical_topic", 0.10)
        # Concerning: gap between -0.25 and -0.10 → actual between 0.15 and 0.30
        _seed_performance(session, class_id, "concerning_topic", 0.25)
        # On track: gap between -0.10 and 0.10 → actual between 0.30 and 0.50
        _seed_performance(session, class_id, "on_track_topic", 0.40)
        # Exceeding: gap >= 0.10 → actual >= 0.50
        _seed_performance(session, class_id, "exceeding_topic", 0.60)

        gaps = compute_gap_analysis(session, class_id)
        severity_map = {g["topic"]: g["gap_severity"] for g in gaps}

        assert severity_map["critical_topic"] == "critical"
        assert severity_map["concerning_topic"] == "concerning"
        assert severity_map["on_track_topic"] == "on_track"
        assert severity_map["exceeding_topic"] == "exceeding"

    def test_multiple_data_points_averaged(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.60)
        _seed_performance(session, class_id, "photosynthesis", 0.80)

        gaps = compute_gap_analysis(session, class_id)
        assert len(gaps) == 1
        assert gaps[0]["actual_score"] == pytest.approx(0.70)
        assert gaps[0]["data_points"] == 2

    def test_depth_mapping(self, db_session):
        session, class_id = db_session
        # Teach photosynthesis twice to reach depth 2
        log_lesson(session, class_id, "Intro photosynthesis", topics=["photosynthesis"])
        log_lesson(session, class_id, "Review photosynthesis", topics=["photosynthesis"])

        _seed_performance(session, class_id, "photosynthesis", 0.50)

        gaps = compute_gap_analysis(session, class_id)
        assert gaps[0]["depth"] == 2
        assert gaps[0]["expected_score"] == DEPTH_EXPECTATION[2]

    def test_sorted_by_gap(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "good_topic", 0.90)
        _seed_performance(session, class_id, "bad_topic", 0.10)
        _seed_performance(session, class_id, "medium_topic", 0.50)

        gaps = compute_gap_analysis(session, class_id)
        # Sorted by gap ascending (worst first)
        assert gaps[0]["topic"] == "bad_topic"
        assert gaps[-1]["topic"] == "good_topic"


class TestTrends:
    def test_trends_sorted_by_date(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.60, days_ago=10)
        _seed_performance(session, class_id, "photosynthesis", 0.75, days_ago=5)
        _seed_performance(session, class_id, "photosynthesis", 0.85, days_ago=0)

        trends = get_topic_trends(session, class_id)
        assert len(trends) == 3
        dates = [t["date"] for t in trends]
        assert dates == sorted(dates)

    def test_trends_topic_filter(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.60)
        _seed_performance(session, class_id, "genetics", 0.70)

        trends = get_topic_trends(session, class_id, topic="photosynthesis")
        assert len(trends) == 1
        assert trends[0]["topic"] == "photosynthesis"

    def test_trends_date_filter(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.60, days_ago=100)
        _seed_performance(session, class_id, "photosynthesis", 0.75, days_ago=10)

        trends = get_topic_trends(session, class_id, days=30)
        assert len(trends) == 1  # Only the recent one

    def test_trends_empty(self, db_session):
        session, class_id = db_session
        trends = get_topic_trends(session, class_id)
        assert trends == []


class TestClassSummary:
    def test_overall_avg(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.60)
        _seed_performance(session, class_id, "genetics", 0.80)

        summary = get_class_summary(session, class_id)
        assert summary["total_topics_assessed"] == 2
        assert summary["overall_avg_score"] == pytest.approx(0.70)

    def test_at_risk_count(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.40)
        _seed_performance(session, class_id, "genetics", 0.80)

        summary = get_class_summary(session, class_id)
        assert summary["topics_at_risk"] == 1
        assert summary["topics_on_track"] == 1

    def test_strongest_weakest(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.90)
        _seed_performance(session, class_id, "genetics", 0.40)

        summary = get_class_summary(session, class_id)
        assert summary["strongest_topic"] == "photosynthesis"
        assert summary["weakest_topic"] == "genetics"

    def test_empty_class(self, db_session):
        session, class_id = db_session
        summary = get_class_summary(session, class_id)
        assert summary["total_topics_assessed"] == 0
        assert summary["overall_avg_score"] == 0.0
        assert summary["strongest_topic"] is None
        assert summary["weakest_topic"] is None


class TestStandardsMastery:
    def test_standards_grouping(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.80, standard="SOL 7.1")
        _seed_performance(session, class_id, "genetics", 0.70, standard="SOL 7.2")

        mastery = get_standards_mastery(session, class_id)
        assert len(mastery) == 2
        standards = [m["standard"] for m in mastery]
        assert "SOL 7.1" in standards
        assert "SOL 7.2" in standards

    def test_mastery_levels(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "topic_a", 0.90, standard="STD-A")  # mastered
        _seed_performance(session, class_id, "topic_b", 0.75, standard="STD-B")  # proficient
        _seed_performance(session, class_id, "topic_c", 0.55, standard="STD-C")  # developing
        _seed_performance(session, class_id, "topic_d", 0.30, standard="STD-D")  # beginning

        mastery = get_standards_mastery(session, class_id)
        level_map = {m["standard"]: m["mastery_level"] for m in mastery}
        assert level_map["STD-A"] == "mastered"
        assert level_map["STD-B"] == "proficient"
        assert level_map["STD-C"] == "developing"
        assert level_map["STD-D"] == "beginning"

    def test_no_standards_returns_empty(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.80)  # no standard
        mastery = get_standards_mastery(session, class_id)
        assert mastery == []


class TestWeakAreas:
    def test_below_threshold(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.40)
        _seed_performance(session, class_id, "genetics", 0.80)

        weak = identify_weak_areas(session, class_id, threshold=0.60)
        assert len(weak) == 1
        assert weak[0]["topic"] == "photosynthesis"
        assert "recommended_action" in weak[0]

    def test_custom_threshold(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.65)
        _seed_performance(session, class_id, "genetics", 0.75)

        weak = identify_weak_areas(session, class_id, threshold=0.70)
        assert len(weak) == 1
        assert weak[0]["topic"] == "photosynthesis"

    def test_no_weak_areas(self, db_session):
        session, class_id = db_session
        _seed_performance(session, class_id, "photosynthesis", 0.90)

        weak = identify_weak_areas(session, class_id, threshold=0.60)
        assert len(weak) == 0
