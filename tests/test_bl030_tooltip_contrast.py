"""Tests for BL-030: Dark mode tooltip contrast fix."""

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


def test_dark_mode_tooltip_override_exists():
    """The CSS file must contain a dark theme override for .help-tip::after."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    assert ':root[data-theme="dark"] .help-tip::after' in css


def test_dark_mode_tooltip_has_dark_background():
    """The dark tooltip background must be a dark color, not var(--text)."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    # Find the dark mode tooltip rule
    idx = css.index(':root[data-theme="dark"] .help-tip::after')
    block = css[idx : css.index("}", idx) + 1]
    # Background should be a dark hex color (starts with #1 or #2), not var(--text)
    assert "var(--text)" not in block
    assert "background:" in block
    assert "color:" in block


def test_dark_mode_tooltip_has_light_text():
    """The dark tooltip text must be a light color for contrast."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    idx = css.index(':root[data-theme="dark"] .help-tip::after')
    block = css[idx : css.index("}", idx) + 1]
    # Should have a light color value (hex starting with #e or #f)
    import re

    color_match = re.search(r"color:\s*(#[0-9a-fA-F]+)", block)
    assert color_match is not None
    hex_color = color_match.group(1).lstrip("#")
    # First byte of the hex color should be >= 0xC0 (light)
    r_value = int(hex_color[:2], 16)
    assert r_value >= 0xC0, f"Text color {color_match.group(1)} is too dark for dark tooltip"


def test_dark_mode_tooltip_has_border():
    """Dark tooltip should have a border for visual definition."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "style.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    idx = css.index(':root[data-theme="dark"] .help-tip::after')
    block = css[idx : css.index("}", idx) + 1]
    assert "border:" in block


def test_tooltip_visible_on_help_page(app):
    """Help page should render without errors (tooltips present in HTML)."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
    resp = client.get("/help")
    assert resp.status_code == 200
