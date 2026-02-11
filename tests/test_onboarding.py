"""
Tests for BL-014: Teacher Onboarding Wizard.

Verifies the onboarding page loads, redirects for new users,
class creation via onboarding, and skip functionality.
"""

import os
import json
import tempfile
import pytest

from src.database import Base, Class, get_engine, get_session


@pytest.fixture
def app_empty():
    """Create a Flask test app with NO classes (triggers onboarding)."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "7th Grade"},
    }
    flask_app = create_app(test_config)
    flask_app.config["TESTING"] = True

    yield flask_app

    flask_app.config["DB_ENGINE"].dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def app_with_class():
    """Create a Flask test app with an existing class (no onboarding)."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Existing Class",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps([]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()
    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "7th Grade"},
    }
    flask_app = create_app(test_config)
    flask_app.config["TESTING"] = True

    yield flask_app

    flask_app.config["DB_ENGINE"].dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def empty_client(app_empty):
    c = app_empty.test_client()
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


@pytest.fixture
def existing_client(app_with_class):
    c = app_with_class.test_client()
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


class TestOnboardingRedirect:
    def test_dashboard_redirects_to_onboarding_when_no_classes(self, empty_client):
        resp = empty_client.get("/dashboard")
        assert resp.status_code == 302
        assert "/onboarding" in resp.headers["Location"]

    def test_dashboard_does_not_redirect_with_classes(self, existing_client):
        resp = existing_client.get("/dashboard")
        assert resp.status_code == 200

    def test_skip_onboarding_param(self, empty_client):
        resp = empty_client.get("/dashboard?skip_onboarding=1")
        assert resp.status_code == 200


class TestOnboardingPage:
    def test_onboarding_page_loads(self, empty_client):
        resp = empty_client.get("/onboarding")
        assert resp.status_code == 200

    def test_onboarding_has_welcome(self, empty_client):
        resp = empty_client.get("/onboarding")
        html = resp.data.decode()
        assert "Welcome to QuizWeaver" in html

    def test_onboarding_has_class_form(self, empty_client):
        resp = empty_client.get("/onboarding")
        html = resp.data.decode()
        assert "class_name" in html
        assert "grade_level" in html
        assert "subject" in html

    def test_onboarding_has_skip_link(self, empty_client):
        resp = empty_client.get("/onboarding")
        html = resp.data.decode()
        assert "skip_onboarding" in html


class TestOnboardingSubmit:
    def test_create_class_via_onboarding(self, app_empty, empty_client):
        resp = empty_client.post("/onboarding", data={
            "class_name": "My First Class",
            "grade_level": "7th Grade",
            "subject": "Science",
        })
        assert resp.status_code == 302

        # Verify class was created
        engine = app_empty.config["DB_ENGINE"]
        session = get_session(engine)
        classes = session.query(Class).all()
        assert len(classes) == 1
        assert classes[0].name == "My First Class"
        session.close()

    def test_submit_without_class_name_still_redirects(self, empty_client):
        resp = empty_client.post("/onboarding", data={
            "class_name": "",
            "grade_level": "7th Grade",
            "subject": "Science",
        })
        # Still redirects (gracefully handles empty form)
        assert resp.status_code == 302

    def test_after_onboarding_dashboard_works(self, app_empty, empty_client):
        empty_client.post("/onboarding", data={
            "class_name": "New Class",
            "grade_level": "8th Grade",
            "subject": "Math",
        })
        # Dashboard should now load without redirect
        resp = empty_client.get("/dashboard")
        assert resp.status_code == 200
