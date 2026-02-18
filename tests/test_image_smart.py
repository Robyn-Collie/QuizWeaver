"""
Tests for GH #47 — Smart image workflow (search terms + answer-reveal warning).

Covers:
- normalize_question_data passthrough of image_search_terms and image_reveals_answer
- export normalize_question inclusion of new fields
- Mock provider responses include the new fields
- Quiz detail template shows warning when image_reveals_answer is true
- Search links use image_search_terms when available
- Fallback to image_description when no search terms
"""

import json

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session
from src.question_regenerator import normalize_question_data

# ---------------------------------------------------------------------------
# Unit tests: normalize_question_data
# ---------------------------------------------------------------------------


class TestNormalizeQuestionData:
    """Tests for normalize_question_data passing through smart image fields."""

    def test_passes_through_image_search_terms(self):
        """image_search_terms should survive normalization."""
        q = {
            "type": "mc",
            "text": "What organelle does photosynthesis?",
            "options": ["Chloroplast", "Mitochondria", "Ribosome", "Nucleus"],
            "correct_index": 0,
            "image_description": "Diagram of a plant cell",
            "image_search_terms": ["plant cell", "chloroplast", "diagram"],
        }
        result = normalize_question_data(q)
        assert result["image_search_terms"] == ["plant cell", "chloroplast", "diagram"]

    def test_passes_through_image_reveals_answer_true(self):
        """image_reveals_answer=True should survive normalization."""
        q = {
            "type": "mc",
            "text": "What organelle does photosynthesis?",
            "options": ["Chloroplast", "Mitochondria", "Ribosome", "Nucleus"],
            "correct_index": 0,
            "image_reveals_answer": True,
        }
        result = normalize_question_data(q)
        assert result["image_reveals_answer"] is True

    def test_passes_through_image_reveals_answer_false(self):
        """image_reveals_answer=False should survive normalization."""
        q = {
            "type": "mc",
            "text": "What is the cell?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
            "image_reveals_answer": False,
        }
        result = normalize_question_data(q)
        assert result["image_reveals_answer"] is False

    def test_missing_image_fields_no_error(self):
        """Questions without image fields should normalize without error."""
        q = {
            "type": "mc",
            "text": "Basic question?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
        }
        result = normalize_question_data(q)
        assert "image_search_terms" not in result or result.get("image_search_terms") is None
        assert "image_reveals_answer" not in result or result.get("image_reveals_answer") is None


# ---------------------------------------------------------------------------
# Unit tests: export normalize_question
# ---------------------------------------------------------------------------


class TestExportNormalizeQuestion:
    """Tests for export.normalize_question including smart image fields."""

    def _make_question_obj(self, data_dict):
        """Create a minimal Question-like object for normalize_question."""

        class FakeQuestion:
            def __init__(self, data):
                self.data = json.dumps(data) if isinstance(data, dict) else data
                self.question_type = data.get("type", "mc")
                self.text = data.get("text", "")
                self.points = data.get("points", 5)

        return FakeQuestion(data_dict)

    def test_includes_image_search_terms(self):
        """Export normalization should include image_search_terms."""
        from src.export import normalize_question

        data = {
            "type": "mc",
            "text": "What is photosynthesis?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
            "image_description": "A plant cell diagram",
            "image_search_terms": ["plant cell", "photosynthesis", "diagram"],
        }
        q_obj = self._make_question_obj(data)
        result = normalize_question(q_obj, 0)
        assert result["image_search_terms"] == ["plant cell", "photosynthesis", "diagram"]

    def test_includes_image_reveals_answer(self):
        """Export normalization should include image_reveals_answer."""
        from src.export import normalize_question

        data = {
            "type": "mc",
            "text": "What is photosynthesis?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
            "image_reveals_answer": True,
        }
        q_obj = self._make_question_obj(data)
        result = normalize_question(q_obj, 0)
        assert result["image_reveals_answer"] is True

    def test_missing_fields_returns_none(self):
        """When fields are absent, export should return None for them."""
        from src.export import normalize_question

        data = {
            "type": "mc",
            "text": "Basic question?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
        }
        q_obj = self._make_question_obj(data)
        result = normalize_question(q_obj, 0)
        assert result["image_search_terms"] is None
        assert result["image_reveals_answer"] is None


# ---------------------------------------------------------------------------
# Unit tests: Mock provider
# ---------------------------------------------------------------------------


class TestMockProviderImageFields:
    """Tests that mock generator responses include smart image fields."""

    def test_mock_response_has_image_search_terms(self):
        """At least one question in the mock response should have image_search_terms."""
        from src.mock_responses import get_generator_response

        response_json = get_generator_response(["photosynthesis test"], ["photosynthesis"])
        questions = json.loads(response_json)
        has_search_terms = any(q.get("image_search_terms") for q in questions)
        assert has_search_terms, "Expected at least one question with image_search_terms"

    def test_mock_response_has_image_reveals_answer(self):
        """At least one question should have image_reveals_answer field."""
        from src.mock_responses import get_generator_response

        response_json = get_generator_response(["photosynthesis test"], ["photosynthesis"])
        questions = json.loads(response_json)
        has_reveals = any("image_reveals_answer" in q for q in questions)
        assert has_reveals, "Expected at least one question with image_reveals_answer"

    def test_mock_search_terms_is_list(self):
        """image_search_terms should be a list of strings."""
        from src.mock_responses import get_generator_response

        response_json = get_generator_response(["photosynthesis test"], ["photosynthesis"])
        questions = json.loads(response_json)
        for q in questions:
            if q.get("image_search_terms"):
                assert isinstance(q["image_search_terms"], list)
                assert all(isinstance(t, str) for t in q["image_search_terms"])

    def test_mock_reveals_answer_is_bool(self):
        """image_reveals_answer should be a boolean."""
        from src.mock_responses import get_generator_response

        response_json = get_generator_response(["photosynthesis test"], ["photosynthesis"])
        questions = json.loads(response_json)
        for q in questions:
            if "image_reveals_answer" in q:
                assert isinstance(q["image_reveals_answer"], bool)


# ---------------------------------------------------------------------------
# Template tests: quiz detail page
# ---------------------------------------------------------------------------


@pytest.fixture
def image_smart_app(db_path):
    """Flask app seeded with a quiz containing smart image fields."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Science 7",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    quiz = Quiz(
        title="Image Smart Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "7th Grade", "provider": "mock"}),
    )
    session.add(quiz)
    session.commit()

    # Q1: has image_search_terms AND image_reveals_answer=True
    q1 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q1",
        text="What organelle does photosynthesis?",
        points=5.0,
        data=json.dumps({
            "type": "mc",
            "options": ["Chloroplast", "Mitochondria", "Ribosome", "Nucleus"],
            "correct_index": 0,
            "image_description": "Diagram of a plant cell showing chloroplasts highlighted in green",
            "image_search_terms": ["plant cell", "chloroplast", "diagram"],
            "image_reveals_answer": True,
        }),
    )
    session.add(q1)

    # Q2: has image_description but NO search terms (fallback test)
    q2 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q2",
        text="What is the powerhouse of the cell?",
        points=5.0,
        data=json.dumps({
            "type": "mc",
            "options": ["Mitochondria", "Chloroplast", "Nucleus", "Ribosome"],
            "correct_index": 0,
            "image_description": "Detailed mitochondria cross-section with labels",
            "image_reveals_answer": False,
        }),
    )
    session.add(q2)

    # Q3: no image fields at all
    q3 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q3",
        text="What is DNA?",
        points=5.0,
        data=json.dumps({
            "type": "mc",
            "options": ["Genetic material", "A protein", "A lipid", "A sugar"],
            "correct_index": 0,
        }),
    )
    session.add(q3)
    session.commit()

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {
            "default_grade_level": "7th Grade Science",
            "quiz_title": "Test Quiz",
            "sol_standards": [],
            "target_image_ratio": 0.0,
            "generate_ai_images": False,
            "interactive_review": False,
        },
    }
    app = create_app(test_config)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    yield app
    app.config["DB_ENGINE"].dispose()


@pytest.fixture
def image_smart_client(image_smart_app):
    """Logged-in test client for the image-smart app."""
    with image_smart_app.test_client() as client:
        with client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        yield client


class TestQuizDetailTemplate:
    """Tests for the quiz detail page rendering of smart image fields."""

    def test_reveals_answer_warning_shown(self, image_smart_client):
        """When image_reveals_answer is true, the warning badge should appear."""
        resp = image_smart_client.get("/quizzes/1")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "May reveal answer" in html
        assert "image-reveals-answer-warning" in html

    def test_reveals_answer_warning_not_shown_when_false(self, image_smart_client):
        """Q2 has image_reveals_answer=False, so no warning for that question."""
        resp = image_smart_client.get("/quizzes/1")
        html = resp.data.decode()
        # Count occurrences: should be exactly 1 (from Q1 only)
        assert html.count("image-reveals-answer-warning") == 1

    def test_search_terms_in_data_attribute(self, image_smart_client):
        """Q1 should have data-search-terms attribute with joined search terms."""
        resp = image_smart_client.get("/quizzes/1")
        html = resp.data.decode()
        assert 'data-search-terms="plant cell chloroplast diagram"' in html

    def test_no_search_terms_attribute_when_absent(self, image_smart_client):
        """Q2 has no image_search_terms, so no data-search-terms attribute for it."""
        resp = image_smart_client.get("/quizzes/1")
        html = resp.data.decode()
        # Only one data-search-terms should exist (from Q1)
        assert html.count("data-search-terms=") == 1

    def test_question_without_image_has_no_placeholder(self, image_smart_client):
        """Q3 has no image fields so should have no image-placeholder div."""
        resp = image_smart_client.get("/quizzes/1")
        html = resp.data.decode()
        # Should have exactly 2 image-placeholder opening divs (Q1 and Q2)
        # Use the class attribute pattern to avoid matching CSS/JS references
        assert html.count('<div class="image-placeholder"') == 2


# ---------------------------------------------------------------------------
# Regeneration preserve tests
# ---------------------------------------------------------------------------


class TestRegeneratePreservesImageFields:
    """Test that regenerate_question preserves image_search_terms and image_reveals_answer."""

    def test_preserve_keys_in_regen_list(self):
        """The preserve-on-regen key list should include new image fields."""
        import inspect

        from src.question_regenerator import regenerate_question

        source = inspect.getsource(regenerate_question)
        assert "image_search_terms" in source
        assert "image_reveals_answer" in source
