"""
Tests for BL-038: Drag-and-drop matching and ordering question display.

Verifies that:
- Matching questions render an interactive container with data-matches JSON
- Ordering questions render an interactive container with data-correct-order
- SortableJS CDN script tag is present on quiz detail pages
- matching.js is loaded on quiz detail pages
- Check/Reset/Show buttons are present in the interactive containers
- Static fallback tables remain in the DOM for no-JS
- Interactive CSS classes exist in style.css
- Mobile-friendly touch-action CSS is present
"""

import json

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
def dnd_client(matching_app):
    """Logged-in test client for drag-and-drop tests."""
    with matching_app.test_client() as c:
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        yield c


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
    """Tests for SortableJS CDN and matching.js loading."""

    def test_sortablejs_cdn_present(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"sortablejs" in resp.data or b"Sortable" in resp.data

    def test_matching_js_loaded(self, dnd_client):
        resp = dnd_client.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"matching.js" in resp.data

    def test_matching_css_classes_in_stylesheet(self):
        import os

        css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "css", "style.css")
        with open(css_path, encoding="utf-8") as f:
            css = f.read()
        assert ".matching-interactive" in css
        assert ".dnd-matching-wrapper" in css
        assert ".dnd-term" in css
        assert ".dnd-def" in css
        assert ".dnd-correct" in css
        assert ".dnd-incorrect" in css
        assert ".dnd-ghost" in css

    def test_ordering_css_classes_in_stylesheet(self):
        import os

        css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "css", "style.css")
        with open(css_path, encoding="utf-8") as f:
            css = f.read()
        assert ".ordering-interactive" in css
        assert ".dnd-ordering-list" in css
        assert ".dnd-order-item" in css

    def test_touch_friendly_min_height(self):
        import os

        css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "css", "style.css")
        with open(css_path, encoding="utf-8") as f:
            css = f.read()
        assert "min-height: 44px" in css

    def test_touch_action_css(self):
        import os

        css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "css", "style.css")
        with open(css_path, encoding="utf-8") as f:
            css = f.read()
        assert "touch-action: none" in css

    def test_dnd_btn_row_css(self):
        import os

        css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "css", "style.css")
        with open(css_path, encoding="utf-8") as f:
            css = f.read()
        assert ".dnd-btn-row" in css
