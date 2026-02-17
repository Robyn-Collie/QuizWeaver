"""Tests for BL-029: Username display in nav bar."""

import os
import tempfile

import pytest

from src.database import Base, get_engine


@pytest.fixture
def app():
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
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
        sess["display_name"] = "Teacher"
    return c


def test_nav_has_user_section(client):
    """Nav should have a dedicated user section separate from nav links."""
    resp = client.get("/dashboard?skip_onboarding=1")
    html = resp.data.decode("utf-8")
    assert "nav-user-section" in html


def test_nav_user_has_icon(client):
    """Username display should include a user icon SVG."""
    resp = client.get("/dashboard?skip_onboarding=1")
    html = resp.data.decode("utf-8")
    assert "nav-user-icon" in html


def test_nav_user_has_display_name(client):
    """Username should be rendered inside .nav-user-name span."""
    resp = client.get("/dashboard?skip_onboarding=1")
    html = resp.data.decode("utf-8")
    assert "nav-user-name" in html


def test_css_has_user_section_styles():
    """CSS must contain styles for the nav user section."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    assert ".nav-user-section" in css


def test_css_has_username_truncation():
    """CSS must truncate long usernames with ellipsis."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    assert "text-overflow: ellipsis" in css
    assert "max-width:" in css


def test_css_has_user_icon_styles():
    """CSS must have styles for the user icon in the nav."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    assert ".nav-user-icon" in css


def test_css_mobile_user_section():
    """CSS must handle user section in mobile view."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    # The mobile responsive block should restyle the user section with border-top
    assert "border-top:" in css


def test_logout_still_present(client):
    """Logout button should still be present in the user section."""
    resp = client.get("/dashboard?skip_onboarding=1")
    html = resp.data.decode("utf-8")
    assert 'action="/logout"' in html or "/logout" in html
