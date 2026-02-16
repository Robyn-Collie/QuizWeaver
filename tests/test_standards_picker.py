"""Tests for the standards picker UX (API endpoint + template integration)."""

import os
import tempfile

import pytest

from src.standards import create_standard


@pytest.fixture
def app():
    """Create a Flask test app with a temp DB and standards loaded."""
    db_fd = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_fd.name
    db_fd.close()

    from src.database import Class, get_engine, get_session, init_db

    engine = get_engine(db_path)
    init_db(engine)

    session = get_session(engine)

    # Create a default class for routes that need one
    default_class = Class(name="Test Class", grade_level="7th Grade", subject="Math", standards='["SOL 7.1"]')
    session.add(default_class)
    session.commit()

    # Load some standards
    create_standard(
        session,
        code="SOL 7.1",
        description="Negative exponents",
        subject="Mathematics",
        grade_band="6-8",
        strand="Number Sense",
    )
    create_standard(
        session,
        code="SOL 7.2",
        description="Rational numbers",
        subject="Mathematics",
        grade_band="6-8",
        strand="Computation",
    )
    create_standard(
        session,
        code="SOL 7.1E",
        description="Scientific investigation",
        subject="Science",
        grade_band="6-8",
        strand="Investigation",
    )
    create_standard(
        session,
        code="SOL 8.5R",
        description="Fictional texts analysis",
        subject="English",
        grade_band="6-8",
        strand="Reading",
    )
    session.close()
    engine.dispose()

    config = {
        "llm": {"provider": "mock"},
        "active_class_id": 1,
        "paths": {"database_file": db_path},
    }

    from src.web.app import create_app

    app = create_app(config)
    app.config["TESTING"] = True

    app.config["WTF_CSRF_ENABLED"] = False
    app.config["DB_PATH"] = db_path

    yield app

    app.config["DB_ENGINE"].dispose()
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    """Create a logged-in test client."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "test"
        sess["display_name"] = "Test User"
    return client


class TestStandardsSearchAPI:
    def test_search_returns_json(self, client):
        resp = client.get("/api/standards/search?q=SOL 7")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data

    def test_search_finds_matching_standards(self, client):
        resp = client.get("/api/standards/search?q=SOL 7")
        data = resp.get_json()
        codes = [r["code"] for r in data["results"]]
        assert "SOL 7.1" in codes
        assert "SOL 7.2" in codes

    def test_search_by_description(self, client):
        resp = client.get("/api/standards/search?q=rational")
        data = resp.get_json()
        assert len(data["results"]) == 1
        assert data["results"][0]["code"] == "SOL 7.2"

    def test_search_empty_query_returns_empty(self, client):
        resp = client.get("/api/standards/search?q=")
        data = resp.get_json()
        assert data["results"] == []

    def test_search_no_results(self, client):
        resp = client.get("/api/standards/search?q=quantum+physics")
        data = resp.get_json()
        assert data["results"] == []

    def test_search_with_subject_filter(self, client):
        resp = client.get("/api/standards/search?q=SOL&subject=Science")
        data = resp.get_json()
        for r in data["results"]:
            assert r["subject"] == "Science"

    def test_search_with_grade_band_filter(self, client):
        resp = client.get("/api/standards/search?q=SOL&grade_band=6-8")
        data = resp.get_json()
        for r in data["results"]:
            assert r["grade_band"] == "6-8"

    def test_search_result_structure(self, client):
        resp = client.get("/api/standards/search?q=SOL 7.1")
        data = resp.get_json()
        assert len(data["results"]) > 0
        result = data["results"][0]
        assert "id" in result
        assert "code" in result
        assert "description" in result
        assert "subject" in result
        assert "grade_band" in result
        assert "strand" in result

    def test_search_limits_results(self, client):
        # Should return at most 50 results
        resp = client.get("/api/standards/search?q=SOL")
        data = resp.get_json()
        assert len(data["results"]) <= 50

    def test_search_requires_login(self, app):
        client = app.test_client()
        resp = client.get("/api/standards/search?q=SOL")
        assert resp.status_code == 303  # redirect to login


class TestStandardsPickerInForms:
    def test_new_class_has_picker(self, client):
        resp = client.get("/classes/new")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "standards_picker.js" in html
        assert "standards_picker.css" in html
        assert "standards_search" in html
        assert "standards_chips" in html
        assert "initStandardsPicker" in html

    def test_edit_class_has_picker(self, client):
        # Create a class first
        from src.database import Class, get_engine, get_session

        engine = get_engine(client.application.config["DB_PATH"])
        session = get_session(engine)
        cls = Class(name="Test Class", standards='["SOL 7.1", "SOL 7.2"]')
        session.add(cls)
        session.commit()
        cls_id = cls.id
        session.close()
        engine.dispose()

        resp = client.get(f"/classes/{cls_id}/edit")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "standards_picker.js" in html
        assert "standards_picker.css" in html
        assert "initStandardsPicker" in html

    def test_generate_quiz_has_picker(self, client):
        # Create a class first
        from src.database import Class, get_engine, get_session

        engine = get_engine(client.application.config["DB_PATH"])
        session = get_session(engine)
        cls = Class(name="Test Class", standards='["SOL 7.1"]')
        session.add(cls)
        session.commit()
        cls_id = cls.id
        session.close()
        engine.dispose()

        resp = client.get(f"/classes/{cls_id}/generate")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "standards_picker.js" in html
        assert "standards_picker.css" in html
        assert "sol_standards_search" in html
        assert "sol_standards_chips" in html

    def test_new_class_submit_with_standards(self, client):
        resp = client.post(
            "/classes/new",
            data={
                "name": "Picker Test Class",
                "grade_level": "7th Grade",
                "subject": "Math",
                "standards": "SOL 7.1, SOL 7.2",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_standards_page_accessible(self, client):
        resp = client.get("/standards")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Standards Browser" in html

    def test_standards_page_search(self, client):
        resp = client.get("/standards?q=rational")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "SOL 7.2" in html

    def test_standards_page_filter_by_subject(self, client):
        resp = client.get("/standards?subject=Science")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "SOL 7.1E" in html
