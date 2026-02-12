"""
Tests for QuizWeaver accessibility features.

BL-031: Dyslexia-Friendly Font Toggle (OpenDyslexic)
BL-032: Text-to-Speech for Quiz Display
BL-033: Color Blind Safe Theme
BL-034: Screen Reader Optimization (ARIA/Semantic HTML)
"""

import json
import os
import tempfile
from datetime import date

import pytest

from src.database import (
    Base,
    Class,
    LessonLog,
    Question,
    Quiz,
    StudyCard,
    StudySet,
    get_engine,
    get_session,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed test data: class
    test_class = Class(
        name="Test Class",
        grade_level="8th Grade",
        subject="Science",
        standards=json.dumps(["SOL 8.1"]),
        config=json.dumps({}),
    )
    session.add(test_class)
    session.commit()

    # Seed: lesson log
    lesson = LessonLog(
        class_id=test_class.id,
        date=date(2026, 2, 1),
        content="Introduction to ecosystems",
        topics=json.dumps(["ecosystems"]),
    )
    session.add(lesson)
    session.commit()

    # Seed: quiz with questions
    quiz = Quiz(
        title="Ecosystem Quiz",
        class_id=test_class.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "8th Grade", "provider": "mock"}),
    )
    session.add(quiz)
    session.commit()

    q1 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q1",
        text="What is an ecosystem?",
        points=5.0,
        sort_order=0,
        data=json.dumps(
            {
                "type": "mc",
                "text": "What is an ecosystem?",
                "options": ["A community of organisms", "A single plant", "A rock", "A cloud"],
                "correct_index": 0,
            }
        ),
    )
    q2 = Question(
        quiz_id=quiz.id,
        question_type="tf",
        title="Q2",
        text="All ecosystems contain water.",
        points=3.0,
        sort_order=1,
        data=json.dumps(
            {
                "type": "tf",
                "text": "All ecosystems contain water.",
                "correct_answer": "True",
            }
        ),
    )
    session.add(q1)
    session.add(q2)
    session.commit()

    # Seed: study set with cards
    study_set = StudySet(
        class_id=test_class.id,
        title="Ecosystem Flashcards",
        material_type="flashcard",
        status="generated",
        config=json.dumps({}),
    )
    session.add(study_set)
    session.commit()

    card1 = StudyCard(
        study_set_id=study_set.id,
        card_type="flashcard",
        sort_order=0,
        front="Ecosystem",
        back="A community of living organisms and their environment",
        data=json.dumps({"tags": ["ecology"]}),
    )
    card2 = StudyCard(
        study_set_id=study_set.id,
        card_type="flashcard",
        sort_order=1,
        front="Biome",
        back="A large naturally occurring community of flora and fauna",
        data=json.dumps({"tags": ["ecology"]}),
    )
    session.add(card1)
    session.add(card2)
    session.commit()

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock", "max_calls_per_session": 50, "max_cost_per_session": 5.00},
        "generation": {"default_grade_level": "8th Grade Science"},
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
    """Create a logged-in test client."""
    c = app.test_client()
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


# ============================================================
# BL-034: Base Template - Skip Nav & ARIA Landmarks
# ============================================================


class TestSkipNav:
    """BL-034: Skip navigation link for screen readers."""

    def test_skip_nav_link_present(self, client):
        """Skip-nav link exists as first child of body."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert 'class="skip-nav"' in html

    def test_skip_nav_targets_main_content(self, client):
        """Skip-nav links to #main-content."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert 'href="#main-content"' in html

    def test_main_content_id_exists(self, client):
        """Main content area has id="main-content"."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert 'id="main-content"' in html

    def test_skip_nav_text(self, client):
        """Skip-nav has descriptive text."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert "Skip to main content" in html


class TestARIALandmarks:
    """BL-034: ARIA roles and labels on landmarks."""

    def test_nav_has_role(self, client):
        """Navbar has role='navigation'."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert 'role="navigation"' in html

    def test_nav_has_aria_label(self, client):
        """Navbar has aria-label for screen readers."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert 'aria-label="Main navigation"' in html

    def test_main_has_role(self, client):
        """Main content has role='main'."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert 'role="main"' in html

    def test_footer_has_role(self, client):
        """Footer has role='contentinfo'."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert 'role="contentinfo"' in html

    def test_footer_has_aria_label(self, client):
        """Footer has aria-label."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert 'aria-label="Site footer"' in html

    def test_nav_menu_has_menubar_role(self, client):
        """Nav links list has role='menubar'."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert 'role="menubar"' in html

    def test_dropdown_has_aria_haspopup(self, client):
        """Dropdown toggles have aria-haspopup."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert 'aria-haspopup="true"' in html

    def test_dropdown_has_aria_expanded(self, client):
        """Dropdown toggles have aria-expanded."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert 'aria-expanded="false"' in html


# ============================================================
# BL-034: Accessibility CSS File Linked
# ============================================================


class TestAccessibilityCSS:
    """BL-034: Accessibility CSS loaded in base template."""

    def test_accessibility_css_linked(self, client):
        """Accessibility CSS file is linked in the base template."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert "accessibility.css" in html

    def test_accessibility_css_file_served(self, client):
        """Static file /css/accessibility.css is serveable."""
        response = client.get("/static/css/accessibility.css")
        assert response.status_code == 200
        css = response.data.decode()
        assert "dyslexia-font" in css

    def test_accessibility_css_contains_skip_nav(self, client):
        """Accessibility CSS contains skip-nav styles."""
        response = client.get("/static/css/accessibility.css")
        css = response.data.decode()
        assert ".skip-nav" in css

    def test_accessibility_css_contains_color_blind(self, client):
        """Accessibility CSS contains color-blind-mode styles."""
        response = client.get("/static/css/accessibility.css")
        css = response.data.decode()
        assert ".color-blind-mode" in css
        assert "Wong" in css or "#0072B2" in css

    def test_accessibility_css_contains_tts_styles(self, client):
        """Accessibility CSS contains TTS panel styles."""
        response = client.get("/static/css/accessibility.css")
        css = response.data.decode()
        assert ".tts-panel" in css
        assert ".tts-read-btn" in css


# ============================================================
# BL-031: Dyslexia Font Toggle in Settings
# ============================================================


class TestDyslexiaFontSettings:
    """BL-031: Dyslexia-friendly font toggle on settings page."""

    def test_settings_has_accessibility_section(self, client):
        """Settings page has an Accessibility section."""
        response = client.get("/settings")
        html = response.data.decode()
        assert "Accessibility" in html

    def test_settings_has_dyslexia_font_toggle(self, client):
        """Settings has a checkbox for dyslexia font."""
        response = client.get("/settings")
        html = response.data.decode()
        assert 'id="a11y-dyslexia-font"' in html

    def test_settings_dyslexia_font_is_checkbox(self, client):
        """Dyslexia font toggle is a checkbox input."""
        response = client.get("/settings")
        html = response.data.decode()
        # Find the checkbox
        assert 'type="checkbox" id="a11y-dyslexia-font"' in html

    def test_settings_has_spacing_toggle(self, client):
        """Settings has a checkbox for enhanced spacing."""
        response = client.get("/settings")
        html = response.data.decode()
        assert 'id="a11y-dyslexia-spacing"' in html

    def test_settings_dyslexia_font_description(self, client):
        """Dyslexia font toggle includes a description."""
        response = client.get("/settings")
        html = response.data.decode()
        assert "OpenDyslexic" in html

    def test_settings_spacing_description(self, client):
        """Spacing toggle mentions letter-spacing and line-height."""
        response = client.get("/settings")
        html = response.data.decode()
        assert "letter spacing" in html.lower() or "letter-spacing" in html.lower()

    def test_css_has_dyslexia_font_class(self, client):
        """CSS defines .dyslexia-font class with OpenDyslexic."""
        response = client.get("/static/css/accessibility.css")
        css = response.data.decode()
        assert "body.dyslexia-font" in css
        assert "OpenDyslexic" in css

    def test_css_has_dyslexia_spacing_class(self, client):
        """CSS defines .dyslexia-spacing class."""
        response = client.get("/static/css/accessibility.css")
        css = response.data.decode()
        assert "body.dyslexia-spacing" in css
        assert "letter-spacing" in css
        assert "line-height" in css

    def test_settings_has_font_preview(self, client):
        """Settings page has a preview area for dyslexia font."""
        response = client.get("/settings")
        html = response.data.decode()
        assert 'id="a11y-preview-font"' in html


# ============================================================
# BL-033: Color Blind Safe Theme in Settings
# ============================================================


class TestColorBlindSettings:
    """BL-033: Color blind safe theme toggle on settings page."""

    def test_settings_has_color_blind_toggle(self, client):
        """Settings has a checkbox for color blind mode."""
        response = client.get("/settings")
        html = response.data.decode()
        assert 'id="a11y-color-blind"' in html

    def test_color_blind_description(self, client):
        """Color blind toggle includes a description mentioning Wong palette."""
        response = client.get("/settings")
        html = response.data.decode()
        assert "color blind" in html.lower() or "Color Blind" in html

    def test_css_has_color_blind_mode_class(self, client):
        """CSS defines body.color-blind-mode with Wong palette colors."""
        response = client.get("/static/css/accessibility.css")
        css = response.data.decode()
        assert "body.color-blind-mode" in css
        # Wong palette colors
        assert "#0072B2" in css  # blue
        assert "#D55E00" in css  # vermilion
        assert "#009E73" in css  # green
        assert "#E69F00" in css  # orange

    def test_css_has_status_text_indicators(self, client):
        """Color blind mode adds text-based status indicators."""
        response = client.get("/static/css/accessibility.css")
        css = response.data.decode()
        assert ".status-generated::before" in css
        assert ".status-failed::before" in css

    def test_css_has_dark_mode_color_blind_combo(self, client):
        """CSS supports dark mode + color blind combined."""
        response = client.get("/static/css/accessibility.css")
        css = response.data.decode()
        assert 'data-theme="dark"' in css
        assert "color-blind-mode" in css


# ============================================================
# BL-032: Text-to-Speech on Quiz Detail
# ============================================================


class TestTTSQuizDetail:
    """BL-032: TTS panel and read-aloud buttons on quiz detail."""

    def test_quiz_detail_has_tts_panel(self, client):
        """Quiz detail page has a TTS panel."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'id="ttsPanel"' in html

    def test_quiz_detail_tts_panel_has_play_btn(self, client):
        """TTS panel has a Play All button."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'id="ttsPlayBtn"' in html
        assert "Play All" in html

    def test_quiz_detail_tts_panel_has_stop_btn(self, client):
        """TTS panel has a Stop button."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'id="ttsStopBtn"' in html

    def test_quiz_detail_tts_has_speed_slider(self, client):
        """TTS panel has a speed slider."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'id="ttsSpeedSlider"' in html

    def test_quiz_detail_tts_has_voice_select(self, client):
        """TTS panel has a voice selection dropdown."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'id="ttsVoiceSelect"' in html

    def test_quiz_detail_has_read_aloud_buttons(self, client):
        """Each question has a read-aloud button."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'class="tts-read-btn"' in html

    def test_quiz_detail_tts_script_loaded(self, client):
        """TTS JavaScript file is loaded on quiz detail page."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert "tts.js" in html

    def test_tts_js_file_served(self, client):
        """Static file /js/tts.js is serveable."""
        response = client.get("/static/js/tts.js")
        assert response.status_code == 200
        js = response.data.decode()
        assert "speechSynthesis" in js

    def test_tts_panel_starts_collapsed(self, client):
        """TTS panel starts in collapsed state."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'class="tts-panel collapsed"' in html

    def test_tts_read_btn_has_aria_label(self, client):
        """Per-question read buttons have aria-label."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'aria-label="Read this question aloud"' in html


# ============================================================
# BL-032: Text-to-Speech on Study Detail
# ============================================================


class TestTTSStudyDetail:
    """BL-032: TTS panel and read-aloud on study material detail."""

    def test_study_detail_has_tts_panel(self, client):
        """Study detail page has a TTS panel."""
        response = client.get("/study/1")
        html = response.data.decode()
        assert 'id="ttsPanel"' in html

    def test_study_detail_has_tts_play_btn(self, client):
        """Study TTS panel has Play All button."""
        response = client.get("/study/1")
        html = response.data.decode()
        assert 'id="ttsPlayBtn"' in html

    def test_study_detail_tts_script_loaded(self, client):
        """TTS JavaScript loaded on study detail page."""
        response = client.get("/study/1")
        html = response.data.decode()
        assert "tts.js" in html

    def test_study_detail_has_read_aloud_buttons(self, client):
        """Study detail has per-card read-aloud buttons."""
        response = client.get("/study/1")
        html = response.data.decode()
        assert 'class="tts-read-btn"' in html


# ============================================================
# BL-034: ARIA on Quiz Detail Action Buttons
# ============================================================


class TestQuizDetailARIA:
    """BL-034: ARIA labels on quiz detail action buttons."""

    def test_edit_button_has_aria_label(self, client):
        """Edit button has aria-label."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'aria-label="Edit question"' in html

    def test_delete_button_has_aria_label(self, client):
        """Delete button has aria-label."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'aria-label="Delete question"' in html

    def test_move_buttons_have_aria_labels(self, client):
        """Move up/down buttons have aria-labels."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'aria-label="Move question up"' in html
        assert 'aria-label="Move question down"' in html

    def test_regen_button_has_aria_label(self, client):
        """Regenerate button has aria-label."""
        response = client.get("/quizzes/1")
        html = response.data.decode()
        assert 'aria-label="Regenerate question"' in html


# ============================================================
# BL-031/033: localStorage Preference Script
# ============================================================


class TestPreferenceScript:
    """BL-031/033: Accessibility preference JS in settings page."""

    def test_settings_has_preference_script(self, client):
        """Settings page has JS for saving/loading accessibility prefs."""
        response = client.get("/settings")
        html = response.data.decode()
        assert "qw-a11y" in html

    def test_base_template_applies_prefs(self, client):
        """Base template has JS to apply saved accessibility prefs on load."""
        response = client.get("/dashboard?skip_onboarding=1")
        html = response.data.decode()
        assert "qw-a11y" in html
        assert "dyslexia-font" in html
        assert "color-blind-mode" in html


# ============================================================
# Migration & Static File Tests
# ============================================================


class TestMigration:
    """Migration 009: accessibility_prefs column on users."""

    def test_migration_file_exists(self):
        """Migration SQL file exists."""
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "migrations",
            "009_add_accessibility_prefs.sql",
        )
        assert os.path.exists(migration_path)

    def test_migration_contains_alter_table(self):
        """Migration adds accessibility_prefs column."""
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "migrations",
            "009_add_accessibility_prefs.sql",
        )
        with open(migration_path) as f:
            sql = f.read()
        assert "accessibility_prefs" in sql
        assert "ALTER TABLE users" in sql


class TestStaticFiles:
    """Static file existence checks."""

    def test_tts_js_exists(self):
        """TTS JavaScript file exists."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "static",
            "js",
            "tts.js",
        )
        assert os.path.exists(path)

    def test_accessibility_css_exists(self):
        """Accessibility CSS file exists."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "static",
            "css",
            "accessibility.css",
        )
        assert os.path.exists(path)

    def test_fonts_directory_exists(self):
        """Fonts directory exists."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "static",
            "fonts",
        )
        assert os.path.isdir(path)


# ============================================================
# BL-031: OpenDyslexic Font Face in CSS
# ============================================================


class TestOpenDyslexicFontFace:
    """BL-031: OpenDyslexic @font-face declarations in CSS."""

    def test_css_has_font_face_regular(self, client):
        """CSS has @font-face for OpenDyslexic regular."""
        response = client.get("/static/css/accessibility.css")
        css = response.data.decode()
        assert "@font-face" in css
        assert "OpenDyslexic" in css

    def test_css_has_font_face_bold(self, client):
        """CSS has @font-face for OpenDyslexic bold weight."""
        response = client.get("/static/css/accessibility.css")
        css = response.data.decode()
        assert "font-weight: bold" in css


# ============================================================
# BL-032: TTS JS Content Checks
# ============================================================


class TestTTSJavascript:
    """BL-032: TTS JavaScript content and API usage."""

    def test_tts_js_uses_speech_synthesis(self, client):
        """TTS JS uses Web Speech API."""
        response = client.get("/static/js/tts.js")
        js = response.data.decode()
        assert "speechSynthesis" in js
        assert "SpeechSynthesisUtterance" in js

    def test_tts_js_has_speed_control(self, client):
        """TTS JS reads speed from slider."""
        response = client.get("/static/js/tts.js")
        js = response.data.decode()
        assert "ttsSpeedSlider" in js
        assert ".rate" in js

    def test_tts_js_has_voice_selection(self, client):
        """TTS JS populates voice dropdown."""
        response = client.get("/static/js/tts.js")
        js = response.data.decode()
        assert "getVoices" in js
        assert "ttsVoiceSelect" in js

    def test_tts_js_has_play_pause_stop(self, client):
        """TTS JS has play, pause, stop functions."""
        response = client.get("/static/js/tts.js")
        js = response.data.decode()
        assert "function speak" in js or "speak" in js
        assert "function pause" in js or "pause" in js
        assert "function stop" in js or "stop" in js

    def test_tts_js_exports_api(self, client):
        """TTS JS exposes QWtts global for external use."""
        response = client.get("/static/js/tts.js")
        js = response.data.decode()
        assert "window.QWtts" in js
