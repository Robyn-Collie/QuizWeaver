"""Tests for BL-025: Add lesson logging value explanation."""

import json
import os
import tempfile

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
    class_id = cls.id
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

    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["TEST_CLASS_ID"] = class_id
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
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
    return c


class TestLessonValueExplanation:
    """Verify lesson logging value explanation appears on lesson log page."""

    def test_info_banner_present_on_new_lesson_page(self, client, app):
        class_id = app.config["TEST_CLASS_ID"]
        resp = client.get(f"/classes/{class_id}/lessons/new")
        html = resp.data.decode()
        assert "Why log lessons?" in html

    def test_info_banner_explains_value(self, client, app):
        class_id = app.config["TEST_CLASS_ID"]
        resp = client.get(f"/classes/{class_id}/lessons/new")
        html = resp.data.decode()
        assert "generate better" in html
        assert "aligned to your actual instruction" in html

    def test_info_banner_is_before_the_form(self, client, app):
        class_id = app.config["TEST_CLASS_ID"]
        resp = client.get(f"/classes/{class_id}/lessons/new")
        html = resp.data.decode()
        banner_pos = html.find("Why log lessons?")
        form_pos = html.find(f'action="/classes/{class_id}/lessons/new"')
        assert form_pos != -1, "Lesson form not found"
        assert banner_pos < form_pos, "Info banner should appear before the form"


class TestClassDetailTooltip:
    """Verify tooltip on Log Lesson button in class detail page."""

    def test_log_lesson_button_has_tooltip(self, client, app):
        class_id = app.config["TEST_CLASS_ID"]
        resp = client.get(f"/classes/{class_id}")
        html = resp.data.decode()
        assert "Log Lesson</a>" in html
        # Verify the title attribute is present on the Log Lesson link
        assert "Record what you taught today" in html

    def test_tooltip_mentions_quizzes_and_study_materials(self, client, app):
        class_id = app.config["TEST_CLASS_ID"]
        resp = client.get(f"/classes/{class_id}")
        html = resp.data.decode()
        assert "quizzes and study materials" in html


class TestTooltipData:
    """Verify lesson_logging_value tooltip is in tooltip_data.py."""

    def test_lesson_logging_value_tooltip_exists(self):
        from src.web.tooltip_data import AI_TOOLTIPS

        assert "lesson_logging_value" in AI_TOOLTIPS

    def test_lesson_logging_value_tooltip_content(self):
        from src.web.tooltip_data import AI_TOOLTIPS

        tip = AI_TOOLTIPS["lesson_logging_value"]
        assert "context for AI generation" in tip
        assert "align quizzes and study materials" in tip
