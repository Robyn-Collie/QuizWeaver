"""
Tests for QuizWeaver performance data import.

Covers CSV parsing, validation, import to database, quiz score import,
and edge cases.
"""

import json
import os
import tempfile
from datetime import date

import pytest

from src.database import (
    Base, Class, Quiz, Question, PerformanceData,
    get_engine, get_session,
)
from src.performance_import import (
    parse_performance_csv,
    validate_csv_row,
    import_csv_data,
    import_quiz_scores,
    get_sample_csv,
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
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    quiz = Quiz(
        title="Test Quiz",
        class_id=cls.id,
        status="generated",
    )
    session.add(quiz)
    session.commit()

    for i in range(3):
        q = Question(
            quiz_id=quiz.id,
            question_type="mc",
            title=f"Q{i+1}",
            text=f"Question about topic {i+1}?",
            points=5.0,
            sort_order=i,
            data=json.dumps({
                "type": "mc",
                "topic": f"topic_{i+1}",
                "options": ["A", "B", "C", "D"],
                "correct_index": 0,
            }),
        )
        session.add(q)
    session.commit()

    yield session, cls.id, quiz.id

    session.close()
    engine.dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


class TestCSVParsing:
    def test_valid_csv(self):
        csv_text = "topic,score\nphotosynthesis,78\ncell division,65\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 2
        assert len(errors) == 0
        assert rows[0]["topic"] == "photosynthesis"
        assert rows[0]["avg_score"] == pytest.approx(0.78)

    def test_optional_columns(self):
        csv_text = "topic,score,date,standard,weak_areas,sample_size\nphotosynthesis,78,2025-03-15,SOL 7.1,light reactions;calvin cycle,25\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 1
        assert rows[0]["standard"] == "SOL 7.1"
        assert rows[0]["weak_areas"] == ["light reactions", "calvin cycle"]
        assert rows[0]["sample_size"] == 25
        assert rows[0]["date"] == date(2025, 3, 15)

    def test_missing_required_topic(self):
        csv_text = "topic,score\n,78\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 0
        assert len(errors) == 1
        assert "topic" in errors[0].lower()

    def test_missing_required_score(self):
        csv_text = "topic,score\nphotosynthesis,\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 0
        assert len(errors) == 1
        assert "score" in errors[0].lower()

    def test_invalid_score_not_number(self):
        csv_text = "topic,score\nphotosynthesis,abc\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 0
        assert len(errors) == 1

    def test_score_out_of_range(self):
        csv_text = "topic,score\nphotosynthesis,150\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 0
        assert len(errors) == 1
        assert "range" in errors[0].lower()

    def test_score_negative(self):
        csv_text = "topic,score\nphotosynthesis,-5\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 0
        assert len(errors) == 1

    def test_empty_rows_skipped(self):
        csv_text = "topic,score\nphotosynthesis,78\n,,\ncell division,65\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 2
        assert len(errors) == 0

    def test_invalid_date_format(self):
        csv_text = "topic,score,date\nphotosynthesis,78,March 15\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 0
        assert len(errors) == 1
        assert "date" in errors[0].lower()

    def test_decimal_score_conversion(self):
        csv_text = "topic,score\nphotosynthesis,78.5\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 1
        assert rows[0]["avg_score"] == pytest.approx(0.785)

    def test_empty_csv(self):
        csv_text = "topic,score\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 0
        assert len(errors) == 0

    def test_partial_errors(self):
        csv_text = "topic,score\nphotosynthesis,78\n,invalid\ncell division,65\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 2
        assert len(errors) == 1


class TestCSVImport:
    def test_creates_records(self, db_session):
        session, class_id, quiz_id = db_session
        csv_text = "topic,score\nphotosynthesis,78\ncell division,65\n"
        count, errors = import_csv_data(session, class_id, csv_text)
        assert count == 2
        assert len(errors) == 0

        records = session.query(PerformanceData).filter_by(class_id=class_id).all()
        assert len(records) == 2
        assert records[0].source == "csv_upload"

    def test_import_with_quiz_id(self, db_session):
        session, class_id, quiz_id = db_session
        csv_text = "topic,score\nphotosynthesis,78\n"
        count, errors = import_csv_data(session, class_id, csv_text, quiz_id=quiz_id)
        assert count == 1

        record = session.query(PerformanceData).filter_by(class_id=class_id).first()
        assert record.quiz_id == quiz_id

    def test_import_empty_csv(self, db_session):
        session, class_id, quiz_id = db_session
        csv_text = "topic,score\n"
        count, errors = import_csv_data(session, class_id, csv_text)
        assert count == 0


class TestQuizScoreImport:
    def test_creates_records(self, db_session):
        session, class_id, quiz_id = db_session
        questions = session.query(Question).filter_by(quiz_id=quiz_id).all()
        scores = {q.id: 75.0 for q in questions}

        count = import_quiz_scores(session, class_id, quiz_id, scores, sample_size=25)
        assert count >= 1  # At least 1 record per unique topic

        records = session.query(PerformanceData).filter_by(class_id=class_id).all()
        assert len(records) >= 1
        assert records[0].source == "quiz_score"
        assert records[0].sample_size == 25

    def test_extracts_topics(self, db_session):
        session, class_id, quiz_id = db_session
        questions = session.query(Question).filter_by(quiz_id=quiz_id).all()
        scores = {q.id: 80.0 for q in questions}

        count = import_quiz_scores(session, class_id, quiz_id, scores)
        records = session.query(PerformanceData).filter_by(class_id=class_id).all()
        topics = [r.topic for r in records]
        # Should have extracted topics from question data
        assert len(topics) >= 1

    def test_empty_scores(self, db_session):
        session, class_id, quiz_id = db_session
        count = import_quiz_scores(session, class_id, quiz_id, {})
        assert count == 0


class TestSampleCSV:
    def test_sample_csv_has_header(self):
        csv = get_sample_csv()
        assert csv.startswith("topic,score")

    def test_sample_csv_has_rows(self):
        csv = get_sample_csv()
        lines = csv.strip().split("\n")
        assert len(lines) >= 4  # header + 3 rows
