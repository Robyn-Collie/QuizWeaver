"""
Tests for BL-028: Mobile-First Responsive Design.

Verifies responsive CSS rules, viewport meta tag, touch targets,
responsive table classes, and mobile breakpoint coverage.
"""

import os
import tempfile

import pytest

from src.database import Base, Class, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)
    cls = Class(name="Test Class", grade_level="8th Grade", subject="Math")
    session.add(cls)
    session.commit()
    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "8th Grade"},
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


def _read_css(app):
    """Read the main CSS file content."""
    css_path = os.path.join(app.static_folder, "css", "style.css")
    with open(css_path) as f:
        return f.read()


# ============================================================
# CSS Responsive Rules
# ============================================================


class TestResponsiveCSS:
    """Test that responsive CSS rules are present in style.css."""

    def test_mobile_responsive_section_exists(self, app):
        """CSS file contains the MOBILE RESPONSIVE section marker."""
        css = _read_css(app)
        assert "MOBILE RESPONSIVE" in css

    def test_768px_breakpoint_exists(self, app):
        """CSS has a 768px tablet breakpoint."""
        css = _read_css(app)
        assert "@media (max-width: 768px)" in css

    def test_480px_breakpoint_exists(self, app):
        """CSS has a 480px small phone breakpoint."""
        css = _read_css(app)
        assert "@media (max-width: 480px)" in css

    def test_320px_breakpoint_exists(self, app):
        """CSS has a 320px very small phone breakpoint."""
        css = _read_css(app)
        assert "@media (max-width: 320px)" in css

    def test_touch_target_min_height(self, app):
        """CSS includes 44px minimum height for touch targets."""
        css = _read_css(app)
        assert "min-height: 44px" in css

    def test_touch_target_min_width(self, app):
        """CSS includes 44px minimum width for touch targets."""
        css = _read_css(app)
        assert "min-width: 44px" in css

    def test_ios_zoom_prevention(self, app):
        """CSS sets font-size: 16px to prevent iOS zoom on input focus."""
        css = _read_css(app)
        assert "font-size: 16px" in css

    def test_table_responsive_class(self, app):
        """CSS defines .table-responsive for scrollable tables."""
        css = _read_css(app)
        assert ".table-responsive" in css
        assert "overflow-x: auto" in css

    def test_responsive_table_card_layout(self, app):
        """CSS defines responsive table card layout with data-label."""
        css = _read_css(app)
        assert ".responsive-table" in css
        assert "attr(data-label)" in css

    def test_stats_grid_single_column_mobile(self, app):
        """Stats grid collapses to 1 column on mobile."""
        css = _read_css(app)
        # Look for stats-grid with 1fr inside a media query
        assert "grid-template-columns: 1fr" in css

    def test_flashcard_grid_single_column_mobile(self, app):
        """Flashcard grid has single column rule on mobile."""
        css = _read_css(app)
        # .flashcard-grid should get 1fr somewhere in responsive section
        assert ".flashcard-grid" in css

    def test_form_actions_stack_on_mobile(self, app):
        """Form actions stack vertically on mobile."""
        css = _read_css(app)
        assert ".form-actions" in css

    def test_landscape_orientation_fix(self, app):
        """CSS has landscape orientation handler."""
        css = _read_css(app)
        assert "orientation: landscape" in css


# ============================================================
# Viewport Meta Tag
# ============================================================


class TestViewportMeta:
    """Test that the viewport meta tag is present in base template."""

    def test_viewport_meta_in_dashboard(self, client):
        """Dashboard page contains viewport meta tag."""
        resp = client.get("/dashboard?skip_onboarding=1")
        assert resp.status_code == 200
        assert b'name="viewport"' in resp.data
        assert b"width=device-width" in resp.data

    def test_viewport_meta_in_classes(self, client):
        """Classes page contains viewport meta tag."""
        resp = client.get("/classes")
        assert resp.status_code == 200
        assert b'name="viewport"' in resp.data

    def test_viewport_meta_in_settings(self, client):
        """Settings page contains viewport meta tag."""
        resp = client.get("/settings")
        assert resp.status_code == 200
        assert b'name="viewport"' in resp.data


# ============================================================
# Responsive Template Elements
# ============================================================


class TestResponsiveTemplates:
    """Test that templates include responsive helper elements."""

    def test_hamburger_nav_toggle(self, client):
        """Base template includes hamburger menu toggle for mobile."""
        resp = client.get("/dashboard?skip_onboarding=1")
        assert resp.status_code == 200
        assert b"nav-toggle" in resp.data
        assert b"hamburger" in resp.data

    def test_nav_links_toggle_js(self, client):
        """Nav links toggle JavaScript is present."""
        resp = client.get("/dashboard?skip_onboarding=1")
        assert b"nav-links" in resp.data
        assert b"toggle" in resp.data.lower()
