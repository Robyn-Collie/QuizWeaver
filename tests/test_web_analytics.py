"""
Tests for QuizWeaver performance analytics web routes.

Covers auth, dashboard, import, manual entry, re-teach, API endpoints,
and sample CSV download.
"""

import json
import os
import tempfile
from datetime import date

import pytest

from src.database import (
    Base,
    Class,
    PerformanceData,
    Question,
    Quiz,
    get_engine,
    get_session,
)


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed test data
    cls = Class(
        name="Block A",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps(
            {
                "assumed_knowledge": {
                    "photosynthesis": {"depth": 2, "last_taught": "2025-03-01", "mention_count": 2},
                }
            }
        ),
    )
    session.add(cls)
    session.commit()

    # A quiz with questions
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
            title=f"Q{i + 1}",
            text=f"Question about topic {i + 1}?",
            points=5.0,
            sort_order=i,
            data=json.dumps(
                {
                    "type": "mc",
                    "topic": f"topic_{i + 1}",
                    "options": ["A", "B", "C", "D"],
                    "correct_index": 0,
                }
            ),
        )
        session.add(q)
    session.commit()

    # Performance data
    perf = PerformanceData(
        class_id=cls.id,
        topic="photosynthesis",
        avg_score=0.65,
        standard="SOL 7.1",
        source="manual_entry",
        sample_size=25,
        date=date.today(),
    )
    session.add(perf)
    session.commit()

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "7th Grade Science"},
    }
    flask_app = create_app(test_config)
    flask_app.config["TESTING"] = True

    flask_app.config["WTF_CSRF_ENABLED"] = False

    yield flask_app

    flask_app.config["DB_ENGINE"].dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def client(app):
    """Logged-in test client."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
    return c


@pytest.fixture
def anon_client(app):
    """Unauthenticated test client."""
    return app.test_client()


# --- Auth Tests ---


class TestAnalyticsAuth:
    def test_dashboard_requires_login(self, anon_client):
        resp = anon_client.get("/classes/1/analytics")
        assert resp.status_code == 303

    def test_import_requires_login(self, anon_client):
        resp = anon_client.get("/classes/1/analytics/import")
        assert resp.status_code == 303

    def test_reteach_requires_login(self, anon_client):
        resp = anon_client.get("/classes/1/analytics/reteach")
        assert resp.status_code == 303


# --- Dashboard Tests ---


class TestAnalyticsDashboard:
    def test_dashboard_loads(self, client):
        resp = client.get("/classes/1/analytics")
        assert resp.status_code == 200
        assert b"Performance Analytics" in resp.data

    def test_dashboard_shows_summary(self, client):
        resp = client.get("/classes/1/analytics")
        assert resp.status_code == 200
        assert b"Topics Assessed" in resp.data

    def test_dashboard_empty_state(self, client):
        # Create class with no performance data
        resp = client.post(
            "/classes/new",
            data={
                "name": "Empty Class",
                "grade_level": "8th",
                "subject": "Math",
            },
        )
        assert resp.status_code == 303
        resp = client.get("/classes/2/analytics")
        assert resp.status_code == 200
        assert b"No performance data" in resp.data


# --- Import Tests ---


class TestAnalyticsImport:
    def test_import_form_loads(self, client):
        resp = client.get("/classes/1/analytics/import")
        assert resp.status_code == 200
        assert b"Import Performance Data" in resp.data

    def test_csv_upload(self, client):
        from io import BytesIO

        csv_data = b"topic,score\ngenetics,72\ncell division,85\n"
        data = {
            "csv_file": (BytesIO(csv_data), "test.csv"),
        }
        resp = client.post(
            "/classes/1/analytics/import",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 303  # Redirect on success

    def test_invalid_file_type(self, client):
        from io import BytesIO

        data = {
            "csv_file": (BytesIO(b"not csv"), "test.txt"),
        }
        resp = client.post(
            "/classes/1/analytics/import",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_sample_csv_download(self, client):
        resp = client.get("/classes/1/analytics/sample-csv")
        assert resp.status_code == 200
        assert b"topic,score" in resp.data


# --- Manual Entry Tests ---


class TestAnalyticsManualEntry:
    def test_manual_form_loads(self, client):
        resp = client.get("/classes/1/analytics/manual")
        assert resp.status_code == 200
        assert b"Manual Score Entry" in resp.data

    def test_post_creates_record(self, client):
        resp = client.post(
            "/classes/1/analytics/manual",
            data={
                "topic": "genetics",
                "score": "75",
                "standard": "SOL 7.2",
                "date": date.today().isoformat(),
                "sample_size": "25",
            },
        )
        assert resp.status_code == 303  # Redirect on success


# --- Re-teach Tests ---


class TestAnalyticsReteach:
    def test_reteach_page_loads(self, client):
        resp = client.get("/classes/1/analytics/reteach")
        assert resp.status_code == 200
        assert b"Re-teach Suggestions" in resp.data

    def test_post_generates_suggestions(self, client):
        resp = client.post(
            "/classes/1/analytics/reteach",
            data={
                "focus_topics": "",
                "max_suggestions": "5",
            },
        )
        assert resp.status_code == 200
        # Should show suggestions or empty state
        assert b"Re-teach Suggestions" in resp.data


# --- API Tests ---


class TestAnalyticsAPI:
    def test_analytics_json(self, client):
        resp = client.get("/api/classes/1/analytics")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "gap_data" in data
        assert "summary" in data

    def test_trends_json(self, client):
        resp = client.get("/api/classes/1/analytics/trends")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trends" in data

    def test_delete_performance_record(self, client):
        resp = client.delete("/api/performance/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_delete_nonexistent_record(self, client):
        resp = client.delete("/api/performance/9999")
        assert resp.status_code == 404
