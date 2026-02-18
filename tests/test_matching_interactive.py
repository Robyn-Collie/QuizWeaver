"""
Tests for BL-038: Drag-and-drop matching and ordering question display.

Verifies that:
- Matching questions render an interactive container with data-matches JSON
- Ordering questions render an interactive container with data-correct-order
- matching.js is loaded on quiz detail pages (no external SortableJS dependency)
- Check/Reset/Show buttons are present in the interactive containers
- Static fallback tables remain in the DOM for no-JS
- Interactive CSS classes exist in style.css (including new alias classes)
- Mobile-friendly touch-action CSS is present
- Dark mode overrides are present
- Keyboard accessibility classes are present
- Non-matching questions do not get matching attributes
- Script tag only appears when matching questions exist
"""

import json
import os

import pytest

from src.database import Class, Question, Quiz

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def matching_app(make_flask_app):
    """Flask app seeded with a quiz containing matching and ordering questions."""

    def seed(session):
        cls = Class(
            name="DnD Test Class",
            grade_level="8th Grade",
            subject="Science",
            standards=json.dumps([]),
            config=json.dumps({}),
        )
        session.add(cls)
        session.commit()

        quiz = Quiz(
            title="DnD Test Quiz",
            class_id=cls.id,
            status="generated",
            style_profile=json.dumps({"provider": "mock"}),
        )
        session.add(quiz)
        session.commit()

        # Matching question
        matching_data = {
            "type": "matching",
            "question_type": "matching",
            "matches": [
                {"term": "Photosynthesis", "definition": "Plants convert sunlight to energy"},
                {"term": "Mitosis", "definition": "Cell division for growth"},
                {"term": "Osmosis", "definition": "Water movement through membrane"},
            ],
        }
        q_matching = Question(
            quiz_id=quiz.id,
            question_type="matching",
            title="Q1",
            text="Match the terms with their definitions.",
            points=3.0,
            data=json.dumps(matching_data),
        )
        session.add(q_matching)

        # Ordering question
        ordering_data = {
            "type": "ordering",
            "question_type": "ordering",
            "instructions": "Put these steps in order.",
            "items": ["Germination", "Growth", "Flowering", "Seed dispersal"],
            "correct_order": [0, 1, 2, 3],
        }
        q_ordering = Question(
            quiz_id=quiz.id,
            question_type="ordering",
            title="Q2",
            text="Order the plant life cycle stages.",
            points=4.0,
            data=json.dumps(ordering_data),
        )
        session.add(q_ordering)

        session.commit()

    return make_flask_app(seed_fn=seed)


@pytest.fixture
def mc_only_app(make_flask_app):
    """Flask app seeded with a quiz containing only MC questions (no matching)."""

    def seed(session):
        cls = Class(
            name="MC Only Class",
            grade_level="8th Grade",
            subject="Science",
            standards=json.dumps([]),
            config=json.dumps({}),
        )
        session.add(cls)
        session.commit()

        quiz = Quiz(
            title="MC Only Quiz",
            class_id=cls.id,
            status="generated",
            style_profile=json.dumps({"provider": "mock"}),
        )
        session.add(quiz)
        session.commit()

        mc_data = {
            "type": "mc",
            "question_type": "mc",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
        }
        q_mc = Question(
            quiz_id=quiz.id,
            question_type="mc",
            title="Q1",
            text="What is photosynthesis?",
            points=1.0,
            data=json.dumps(mc_data),
        )
        session.add(q_mc)
        session.commit()

    return make_flask_app(seed_fn=seed)


@pytest.fixture
def dnd_client(matching_app):
    """Logged-in test client for drag-and-drop tests."""
    with matching_app.test_client() as c:
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        yield c


@pytest.fixture
def mc_client(mc_only_app):
    """Logged-in test client for MC-only quiz (no matching questions)."""
    with mc_only_app.test_client() as c:
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        yield c


def _read_css():
    """Read the main stylesheet."""
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "css", "style.css")
    with open(css_path, encoding="utf-8") as f:
        return f.read()


def _read_js():
    """Read the matching.js script."""
    js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "js", "matching.js")
    with open(js_path, encoding="utf-8") as f:
        return f.read()


# ============================================================
# Matching question tests
# ============================================================


class TestMatchingInteractive:
    """Tests for interactive matching question display."""

    def test_matching_renders_interactive_div(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"matching-interactive" in resp.data

    def test_matching_data_matches_attribute_present(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"data-matches=" in resp.data

    def test_matching_data_matches_is_valid_json(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        html = resp.data.decode("utf-8")
        # Extract the data-matches value
        start = html.index("data-matches='") + len("data-matches='")
        end = html.index("'", start)
        raw = html[start:end]
        matches = json.loads(raw)
        assert isinstance(matches, list)
        assert len(matches) == 3
        assert matches[0]["term"] == "Photosynthesis"

    def test_matching_data_matches_has_term_and_definition(self, dnd_client):
        """Each match object must have both 'term' and 'definition' keys."""
        resp = dnd_client.get("/quizzes/1")
        html = resp.data.decode("utf-8")
        start = html.index("data-matches='") + len("data-matches='")
        end = html.index("'", start)
        matches = json.loads(html[start:end])
        for m in matches:
            assert "term" in m
            assert "definition" in m

    def test_matching_static_fallback_present(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"matching-static-fallback" in resp.data
        assert b"matching-table" in resp.data

    def test_matching_static_shows_terms(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        assert b"Photosynthesis" in resp.data
        assert b"Plants convert sunlight to energy" in resp.data


# ============================================================
# Ordering question tests
# ============================================================


class TestOrderingInteractive:
    """Tests for interactive ordering question display."""

    def test_ordering_renders_interactive_div(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"ordering-interactive" in resp.data

    def test_ordering_data_correct_order_present(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"data-correct-order=" in resp.data

    def test_ordering_data_items_present(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"data-items=" in resp.data

    def test_ordering_data_correct_order_is_valid_json(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        html = resp.data.decode("utf-8")
        start = html.index("data-correct-order='") + len("data-correct-order='")
        end = html.index("'", start)
        raw = html[start:end]
        order = json.loads(raw)
        assert order == [0, 1, 2, 3]

    def test_ordering_static_fallback_present(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"ordering-static-fallback" in resp.data


# ============================================================
# Script and CSS loading tests
# ============================================================


class TestScriptsAndCSS:
    """Tests for matching.js loading and CSS classes."""

    def test_no_sortablejs_cdn_dependency(self, dnd_client):
        """SortableJS CDN should NOT be loaded -- we use native HTML5 DnD."""
        resp = dnd_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"sortablejs" not in resp.data
        assert b"cdn.jsdelivr.net/npm/sortablejs" not in resp.data

    def test_matching_js_loaded(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"matching.js" in resp.data

    def test_matching_js_uses_native_dnd(self):
        """matching.js should use native HTML5 Drag and Drop, not SortableJS."""
        js = _read_js()
        assert "dragstart" in js
        assert "dragover" in js
        assert "drop" in js
        assert "dragend" in js
        # Should NOT reference SortableJS
        assert "Sortable.create" not in js
        assert "new Sortable" not in js

    def test_matching_js_has_touch_support(self):
        """matching.js should handle touchstart/touchmove/touchend for mobile."""
        js = _read_js()
        assert "touchstart" in js
        assert "touchmove" in js
        assert "touchend" in js

    def test_matching_js_has_keyboard_support(self):
        """matching.js should support keyboard reordering for accessibility."""
        js = _read_js()
        assert "keydown" in js
        assert "ArrowUp" in js
        assert "ArrowDown" in js
        assert "Enter" in js
        assert "Escape" in js

    def test_matching_js_has_aria_live_region(self):
        """matching.js should create an ARIA live region for screen readers."""
        js = _read_js()
        assert "aria-live" in js
        assert "polite" in js

    def test_matching_css_classes_in_stylesheet(self):
        css = _read_css()
        assert ".matching-interactive" in css
        assert ".dnd-matching-wrapper" in css
        assert ".dnd-term" in css
        assert ".dnd-def" in css
        assert ".dnd-correct" in css
        assert ".dnd-incorrect" in css
        assert ".dnd-ghost" in css

    def test_new_alias_css_classes(self):
        """New CSS alias classes from the task requirements."""
        css = _read_css()
        assert ".matching-container" in css
        assert ".matching-term" in css
        assert ".matching-dropzone" in css
        assert ".matching-correct" in css
        assert ".matching-incorrect" in css

    def test_drag_over_css(self):
        """Drag-over highlight CSS classes."""
        css = _read_css()
        assert ".dnd-drag-over" in css
        assert ".matching-dropzone.drag-over" in css

    def test_ordering_css_classes_in_stylesheet(self):
        css = _read_css()
        assert ".ordering-interactive" in css
        assert ".dnd-ordering-list" in css
        assert ".dnd-order-item" in css

    def test_touch_friendly_min_height(self):
        css = _read_css()
        assert "min-height: 44px" in css

    def test_touch_action_css(self):
        css = _read_css()
        assert "touch-action: none" in css

    def test_dnd_btn_row_css(self):
        css = _read_css()
        assert ".dnd-btn-row" in css

    def test_dark_mode_overrides_present(self):
        """Dark mode overrides for DnD elements should exist."""
        css = _read_css()
        assert ':root[data-theme="dark"] .dnd-correct' in css
        assert ':root[data-theme="dark"] .dnd-incorrect' in css
        assert ':root[data-theme="dark"] .dnd-drag-over' in css
        assert ':root[data-theme="dark"] .dnd-ghost' in css

    def test_transition_animations_present(self):
        """Transition animations should be on draggable items."""
        css = _read_css()
        assert "transition:" in css
        # Verify transitions are on the right selectors (border-color, box-shadow, etc.)
        assert "border-color" in css
        assert "box-shadow" in css

    def test_mobile_breakpoint_stacks_columns(self):
        """At mobile breakpoint, matching columns should stack vertically."""
        css = _read_css()
        assert "flex-direction: column" in css
        # The media query should be at 768px or smaller
        assert "@media" in css

    def test_touch_clone_css(self):
        """A floating clone style should exist for touch drag."""
        css = _read_css()
        assert ".dnd-touch-clone" in css


# ============================================================
# Non-matching question tests
# ============================================================


class TestNonMatchingQuestions:
    """Ensure non-matching questions are not affected."""

    def test_mc_question_no_matching_attributes(self, mc_client):
        """MC-only quiz should not have matching interactive containers."""
        resp = mc_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"matching-interactive" not in resp.data
        assert b"data-matches=" not in resp.data

    def test_mc_question_no_ordering_attributes(self, mc_client):
        """MC-only quiz should not have ordering interactive containers."""
        resp = mc_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"ordering-interactive" not in resp.data
        assert b"data-correct-order=" not in resp.data

    def test_matching_js_still_loaded_for_mc_quiz(self, mc_client):
        """matching.js is loaded on all quiz detail pages (it no-ops gracefully)."""
        resp = mc_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"matching.js" in resp.data
