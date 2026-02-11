"""Tests for BL-024: Prevent Edge/Chrome autofill on settings fields."""

import os
import tempfile
import json
import pytest

from src.database import Base, Class, get_engine, get_session


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)
    cls = Class(
        name="Test Class",
        grade_level="7th Grade",
        subject="Math",
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
def client(app):
    c = app.test_client()
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


class TestSettingsAutofill:
    """Verify autocomplete attributes on settings page inputs."""

    def test_model_name_has_autocomplete_off(self, client):
        resp = client.get("/settings")
        html = resp.data.decode()
        assert 'id="model_name"' in html
        assert 'autocomplete="off"' in html

    def test_api_key_has_autocomplete_new_password(self, client):
        resp = client.get("/settings")
        html = resp.data.decode()
        assert 'id="api_key"' in html
        assert 'autocomplete="new-password"' in html

    def test_base_url_has_autocomplete_off(self, client):
        resp = client.get("/settings")
        html = resp.data.decode()
        assert 'id="base_url"' in html
        # Check that the base_url input specifically has autocomplete="off"
        base_url_section = html.split('id="base_url"')[1].split(">")[0]
        assert 'autocomplete="off"' in base_url_section


class TestProviderWizardAutofill:
    """Verify autocomplete attributes on provider wizard page inputs."""

    def test_wizard_api_key_has_autocomplete_new_password(self, client):
        resp = client.get("/settings/wizard")
        html = resp.data.decode()
        assert 'id="wizard_api_key"' in html
        wizard_key_section = html.split('id="wizard_api_key"')[1].split(">")[0]
        assert 'autocomplete="new-password"' in wizard_key_section

    def test_wizard_model_has_autocomplete_off(self, client):
        resp = client.get("/settings/wizard")
        html = resp.data.decode()
        assert 'id="wizard_model"' in html
        wizard_model_section = html.split('id="wizard_model"')[1].split(">")[0]
        assert 'autocomplete="off"' in wizard_model_section
