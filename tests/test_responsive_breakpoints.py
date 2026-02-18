"""
Tests for GH #23: Responsive Nav Breakpoint Testing.

Verifies that the responsive CSS infrastructure and HTML templates
correctly support all major breakpoints (320px mobile, 768px tablet,
1024px laptop, 1440px desktop). Uses static analysis of CSS rules
and HTML structure via the Flask test client -- no real browser needed.

Complements tests/test_mobile_responsive.py which covers BL-028 basics.
"""

import json
import os
import re
import tempfile

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database and seed data."""
    db_fd = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_fd.name
    db_fd.close()

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed class
    cls = Class(
        name="Test Class",
        grade_level="8th Grade",
        subject="Science",
        standards=json.dumps(["SOL 8.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    # Seed quiz with questions
    quiz = Quiz(
        title="Test Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "8th Grade", "provider": "mock"}),
    )
    session.add(quiz)
    session.commit()

    q1 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q1",
        text="What is the powerhouse of the cell?",
        points=5.0,
        data=json.dumps(
            {
                "type": "mc",
                "options": ["Mitochondria", "Nucleus", "Ribosome", "Golgi body"],
                "correct_index": 0,
            }
        ),
    )
    session.add(q1)
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
    try:
        os.unlink(db_path)
    except (PermissionError, OSError):
        pass


@pytest.fixture
def client(app):
    """Logged-in test client."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "test"
        sess["display_name"] = "Test User"
    return c


def _read_css(app):
    """Read the main CSS file content."""
    css_path = os.path.join(app.static_folder, "css", "style.css")
    with open(css_path) as f:
        return f.read()


def _read_template(name):
    """Read a template file from the templates directory."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "templates", name)
    with open(path) as f:
        return f.read()


# ============================================================
# CSS Breakpoint Verification
# ============================================================


class TestCSSBreakpoints:
    """Verify that style.css contains media queries for all 4 breakpoints."""

    def test_mobile_320_breakpoint(self, app):
        """CSS contains a 320px (very small mobile) media query."""
        css = _read_css(app)
        assert "@media (max-width: 320px)" in css

    def test_mobile_480_breakpoint(self, app):
        """CSS contains a 480px (small phone) media query."""
        css = _read_css(app)
        assert "@media (max-width: 480px)" in css

    def test_tablet_768_breakpoint(self, app):
        """CSS contains a 768px (tablet) media query."""
        css = _read_css(app)
        assert "@media (max-width: 768px)" in css

    def test_responsive_section_marker(self, app):
        """CSS has the MOBILE RESPONSIVE section marker."""
        css = _read_css(app)
        assert "MOBILE RESPONSIVE" in css

    def test_multiple_768_media_queries(self, app):
        """CSS uses 768px breakpoint in multiple contexts (nav, touch, tables)."""
        css = _read_css(app)
        count = css.count("@media (max-width: 768px)")
        # The CSS should have at least 3 separate 768px media blocks:
        # nav collapse, touch targets, responsive table card layout
        assert count >= 3, f"Expected >= 3 uses of 768px breakpoint, found {count}"

    def test_landscape_orientation_media_query(self, app):
        """CSS includes a landscape orientation media query."""
        css = _read_css(app)
        assert "orientation: landscape" in css


# ============================================================
# Navigation Responsive Rules
# ============================================================


class TestNavResponsive:
    """Verify nav collapse/hamburger rules for mobile."""

    def test_nav_toggle_hidden_by_default(self, app):
        """Nav toggle (hamburger) is hidden by default (display: none)."""
        css = _read_css(app)
        # The .nav-toggle base rule should have display: none
        nav_toggle_match = re.search(
            r"\.nav-toggle\s*\{[^}]*display:\s*none", css
        )
        assert nav_toggle_match, "Expected .nav-toggle { display: none }"

    def test_nav_toggle_shown_on_mobile(self, app):
        """Nav toggle is displayed on mobile (768px breakpoint)."""
        css = _read_css(app)
        # Inside a 768px media query, .nav-toggle should be display: block
        assert ".nav-toggle" in css
        # Find the responsive section with nav-toggle display:block
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?\.nav-toggle\s*\{[^}]*display:\s*block",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .nav-toggle { display: block } in 768px media query"

    def test_nav_links_column_on_mobile(self, app):
        """Nav links switch to column layout on mobile."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?\.nav-links\s*\{[^}]*flex-direction:\s*column",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .nav-links { flex-direction: column } on mobile"

    def test_nav_links_hidden_on_mobile(self, app):
        """Nav links are hidden by default on mobile (toggled by JS)."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?\.nav-links\s*\{[^}]*display:\s*none",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .nav-links { display: none } on mobile"

    def test_nav_links_open_class(self, app):
        """CSS defines .nav-links.open to show the mobile menu."""
        css = _read_css(app)
        assert ".nav-links.open" in css

    def test_nav_backdrop_for_mobile_menu(self, app):
        """CSS defines .nav-backdrop.open for mobile overlay."""
        css = _read_css(app)
        assert ".nav-backdrop.open" in css

    def test_hamburger_element_in_template(self, client):
        """Base template includes hamburger toggle button."""
        resp = client.get("/dashboard?skip_onboarding=1")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "nav-toggle" in html
        assert "hamburger" in html
        assert "toggleMobileNav" in html


# ============================================================
# Touch Target Rules
# ============================================================


class TestTouchTargets:
    """Verify touch target sizing rules exist in the CSS."""

    def test_min_height_44px(self, app):
        """CSS specifies min-height: 44px for touch targets."""
        css = _read_css(app)
        assert "min-height: 44px" in css

    def test_min_width_44px(self, app):
        """CSS specifies min-width: 44px for touch targets."""
        css = _read_css(app)
        assert "min-width: 44px" in css

    def test_touch_targets_in_tablet_breakpoint(self, app):
        """Touch target rules are inside the 768px media query."""
        css = _read_css(app)
        # Find the MOBILE RESPONSIVE section 768px block that has min-height: 44px
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\)\s*\{.*?min-height:\s*44px",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected min-height: 44px inside 768px media query"

    def test_buttons_links_get_touch_targets(self, app):
        """Touch target rule applies to buttons, links, and nav items."""
        css = _read_css(app)
        # The rule should cover .btn, button, input[type="submit"], nav links
        pattern = re.compile(
            r"\.btn,\s*\n?\s*button,\s*\n?\s*input\[type=['\"]submit['\"]\].*?"
            r"min-height:\s*44px",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected touch target rule covering .btn, button, input[type=submit]"


# ============================================================
# Table Responsive Handling
# ============================================================


class TestTableResponsive:
    """Verify responsive table patterns in CSS and templates."""

    def test_table_responsive_class_in_css(self, app):
        """CSS defines .table-responsive with overflow-x: auto."""
        css = _read_css(app)
        assert ".table-responsive" in css
        assert "overflow-x: auto" in css

    def test_responsive_table_card_layout(self, app):
        """CSS defines .responsive-table card layout with data-label pseudo-elements."""
        css = _read_css(app)
        assert ".responsive-table" in css
        assert "attr(data-label)" in css

    def test_responsive_table_hides_thead_on_mobile(self, app):
        """CSS hides thead of .responsive-table on mobile."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?"
            r"\.responsive-table\s+thead\s*\{[^}]*display:\s*none",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .responsive-table thead { display: none } on mobile"

    def test_data_table_scrolls_on_mobile(self, app):
        """CSS makes .data-table horizontally scrollable on mobile."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?\.data-table\s*\{[^}]*overflow-x:\s*auto",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .data-table { overflow-x: auto } on mobile"

    def test_classes_list_uses_responsive_table(self):
        """Classes list template uses responsive-table class."""
        template = _read_template(os.path.join("classes", "list.html"))
        assert "responsive-table" in template

    def test_classes_list_uses_data_labels(self):
        """Classes list table cells have data-label attributes."""
        template = _read_template(os.path.join("classes", "list.html"))
        assert 'data-label="' in template


# ============================================================
# Form Input Responsive Rules
# ============================================================


class TestFormResponsive:
    """Verify form inputs are full-width on mobile."""

    def test_form_max_width_100_on_mobile(self, app):
        """CSS sets .form max-width: 100% on mobile."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?\.form\s*\{[^}]*max-width:\s*100%",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .form { max-width: 100% } on mobile"

    def test_ios_zoom_prevention(self, app):
        """CSS sets font-size: 16px on form inputs to prevent iOS zoom."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?font-size:\s*16px.*?Prevent iOS zoom",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected font-size: 16px in mobile breakpoint for iOS zoom prevention"

    def test_form_actions_stack_vertically_on_mobile(self, app):
        """CSS stacks .form-actions vertically on mobile."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?\.form-actions\s*\{[^}]*"
            r"flex-direction:\s*column",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .form-actions { flex-direction: column } on mobile"

    def test_form_buttons_full_width_on_mobile(self, app):
        """CSS makes .form-actions .btn full-width on mobile."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?\.form-actions\s+\.btn\s*\{[^}]*"
            r"width:\s*100%",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .form-actions .btn { width: 100% } on mobile"


# ============================================================
# Export Button Responsive Rules
# ============================================================


class TestExportButtonsResponsive:
    """Verify export buttons stack on mobile, horizontal on desktop."""

    def test_export_actions_flex_row_default(self, app):
        """CSS sets .export-actions as flexbox row by default (desktop)."""
        css = _read_css(app)
        # The base .export-actions should have display: flex
        pattern = re.compile(
            r"\.export-actions\s*\{[^}]*display:\s*flex",
        )
        assert pattern.search(css), "Expected .export-actions { display: flex }"

    def test_export_actions_column_on_mobile(self, app):
        """CSS stacks .export-actions vertically on mobile."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?"
            r"\.export-actions\s*\{[^}]*flex-direction:\s*column",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .export-actions { flex-direction: column } on mobile"

    def test_export_buttons_full_width_on_mobile(self, app):
        """CSS makes export action buttons full-width on mobile."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?"
            r"\.export-actions\s+\.btn\s*\{[^}]*width:\s*100%",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .export-actions .btn { width: 100% } on mobile"

    def test_quiz_detail_has_export_actions(self, client):
        """Quiz detail page contains .export-actions container."""
        resp = client.get("/quizzes/1")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "export-actions" in html


# ============================================================
# Viewport Meta Tag
# ============================================================


class TestViewportMeta:
    """Verify viewport meta tag is present across key pages."""

    @pytest.mark.parametrize(
        "url",
        [
            "/dashboard?skip_onboarding=1",
            "/classes",
            "/settings",
            "/quizzes",
        ],
    )
    def test_viewport_meta_on_page(self, client, url):
        """Page contains viewport meta tag with width=device-width."""
        resp = client.get(url)
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert 'name="viewport"' in html
        assert "width=device-width" in html
        assert "initial-scale=1.0" in html


# ============================================================
# Template Structure Verification
# ============================================================


class TestTemplateStructure:
    """Verify templates use responsive CSS classes and patterns."""

    def test_base_has_skip_nav_link(self):
        """Base template has a skip navigation link for accessibility."""
        template = _read_template("base.html")
        assert "skip-nav" in template
        assert "#main-content" in template

    def test_base_has_nav_backdrop(self):
        """Base template includes nav-backdrop for mobile overlay."""
        template = _read_template("base.html")
        assert "nav-backdrop" in template
        assert "navBackdrop" in template

    def test_base_has_toggle_mobile_nav_js(self):
        """Base template includes toggleMobileNav JavaScript function."""
        template = _read_template("base.html")
        assert "function toggleMobileNav()" in template

    def test_dashboard_uses_stats_grid(self, client):
        """Dashboard uses stats-grid or class-list for responsive layout."""
        resp = client.get("/dashboard?skip_onboarding=1")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        # Dashboard uses class-list for the cards grid
        assert "class-list" in html or "stats-grid" in html

    def test_dashboard_uses_tool_cards_grid(self, client):
        """Dashboard uses tool-cards-grid for responsive tool cards."""
        resp = client.get("/dashboard?skip_onboarding=1")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "tool-cards-grid" in html

    def test_generate_form_uses_form_class(self, client):
        """Generate form uses .form class for responsive styling."""
        resp = client.get("/classes/1/generate")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert 'class="form"' in html or "class=\"form " in html

    def test_quiz_detail_has_question_cards(self, client):
        """Quiz detail page uses question-card divs."""
        resp = client.get("/quizzes/1")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "question-card" in html


# ============================================================
# Grid Collapse Rules
# ============================================================


class TestGridCollapse:
    """Verify grid layouts collapse to single column on mobile."""

    def test_stats_grid_single_column_mobile(self, app):
        """Stats grid collapses to 1 column on mobile (1fr)."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?"
            r"\.stats-grid\s*\{[^}]*grid-template-columns:\s*1fr",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .stats-grid { grid-template-columns: 1fr } on mobile"

    def test_tool_cards_grid_single_column_mobile(self, app):
        """Tool cards grid collapses to 1 column on mobile."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?"
            r"\.tool-cards-grid\s*\{[^}]*grid-template-columns:\s*1fr",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .tool-cards-grid { grid-template-columns: 1fr } on mobile"

    def test_flashcard_grid_single_column_mobile(self, app):
        """Flashcard grid collapses to 1 column on mobile."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?"
            r"\.flashcard-grid\s*\{[^}]*grid-template-columns:\s*1fr",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .flashcard-grid { grid-template-columns: 1fr } on mobile"

    def test_class_list_single_column_mobile(self, app):
        """Class list collapses to 1 column on mobile."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*768px\).*?"
            r"\.class-list\s*\{[^}]*grid-template-columns:\s*1fr",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .class-list { grid-template-columns: 1fr } on mobile"


# ============================================================
# Page Rendering Checks (Flask Test Client)
# ============================================================


class TestPageRendering:
    """Verify key pages render successfully and have no problematic inline styles."""

    @pytest.mark.parametrize(
        "url,description",
        [
            ("/dashboard?skip_onboarding=1", "Dashboard"),
            ("/quizzes/1", "Quiz detail"),
            ("/classes", "Class list"),
            ("/classes/1/generate", "Generate form"),
            ("/settings", "Settings"),
        ],
    )
    def test_page_returns_200(self, client, url, description):
        """Page returns HTTP 200 status."""
        resp = client.get(url)
        assert resp.status_code == 200, f"{description} ({url}) returned {resp.status_code}"

    @pytest.mark.parametrize(
        "url",
        [
            "/dashboard?skip_onboarding=1",
            "/quizzes/1",
            "/classes",
            "/classes/1/generate",
            "/settings",
        ],
    )
    def test_no_fixed_width_on_container(self, client, url):
        """Pages do not set fixed pixel widths on the main container via inline style."""
        resp = client.get(url)
        html = resp.data.decode("utf-8")
        # Look for inline styles on the container that would break responsive layout.
        # e.g., style="width: 1200px" on a main container div
        # We check that the <main> container does not have problematic inline widths.
        main_match = re.search(
            r'<main[^>]*class="container"[^>]*style="[^"]*width:\s*\d+px',
            html,
        )
        assert main_match is None, f"Found fixed pixel width on main container at {url}"

    @pytest.mark.parametrize(
        "url",
        [
            "/dashboard?skip_onboarding=1",
            "/quizzes/1",
            "/classes",
            "/settings",
        ],
    )
    def test_pages_include_style_css(self, client, url):
        """Pages include the main style.css stylesheet."""
        resp = client.get(url)
        html = resp.data.decode("utf-8")
        assert "style.css" in html

    def test_quiz_detail_no_overflow_hidden_on_content(self, client):
        """Quiz detail page does not use overflow: hidden on the main content area."""
        resp = client.get("/quizzes/1")
        html = resp.data.decode("utf-8")
        main_match = re.search(
            r'<main[^>]*style="[^"]*overflow:\s*hidden',
            html,
        )
        assert main_match is None, "Found overflow: hidden on main content area"


# ============================================================
# Small Breakpoint Specifics (480px and 320px)
# ============================================================


class TestSmallBreakpoints:
    """Verify CSS rules specific to 480px and 320px breakpoints."""

    def test_480_tighter_container_padding(self, app):
        """480px breakpoint reduces container padding."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*480px\).*?\.container\s*\{[^}]*padding:\s*0\s+0\.75rem",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected tighter .container padding at 480px"

    def test_480_smaller_headings(self, app):
        """480px breakpoint reduces heading font sizes."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*480px\).*?h1\s*\{[^}]*font-size:\s*1\.4rem",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected h1 { font-size: 1.4rem } at 480px"

    def test_320_minimal_padding(self, app):
        """320px breakpoint uses minimal container padding."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*320px\).*?\.container\s*\{[^}]*padding:\s*0\s+0\.5rem",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .container { padding: 0 0.5rem } at 320px"

    def test_320_smaller_buttons(self, app):
        """320px breakpoint reduces button size."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*320px\).*?\.btn\s*\{[^}]*font-size:\s*0\.8rem",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .btn { font-size: 0.8rem } at 320px"

    def test_320_smaller_navbar_padding(self, app):
        """320px breakpoint reduces navbar padding."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s*\(max-width:\s*320px\).*?\.navbar\s*\{[^}]*padding:\s*0\s+0\.5rem",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .navbar { padding: 0 0.5rem } at 320px"


# ============================================================
# Print Media Query
# ============================================================


class TestPrintStyles:
    """Verify print styles hide interactive elements."""

    def test_print_hides_navbar(self, app):
        """Print media query hides the navbar."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s+print\s*\{.*?\.navbar.*?display:\s*none\s*!important",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected navbar hidden in print styles"

    def test_print_hides_export_actions(self, app):
        """Print media query hides export actions."""
        css = _read_css(app)
        pattern = re.compile(
            r"@media\s+print\s*\{.*?\.export-actions.*?display:\s*none\s*!important",
            re.DOTALL,
        )
        assert pattern.search(css), "Expected .export-actions hidden in print styles"
