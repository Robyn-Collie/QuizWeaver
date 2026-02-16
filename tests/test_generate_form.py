"""
Tests for the redesigned quiz generation form.

Covers:
- F1/F3: Topics and content text fields
- F2: Standards search returns more results (50 limit)
- F6: Independent question types (decoupled from Bloom's)
- F8: Difficulty slider descriptions
- Pipeline wiring: topics/content reach the generator context
"""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, Quiz, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database for form tests."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Bio Period 3",
        grade_level="10th Grade",
        subject="Biology",
        standards=json.dumps(["SOL BIO.4"]),
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
        "generation": {
            "default_grade_level": "10th Grade Biology",
            "quiz_title": "Generated Quiz",
            "sol_standards": [],
            "target_image_ratio": 0.0,
        },
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


# ============================================================
# F1/F3: Topics and Content Fields
# ============================================================


class TestTopicsAndContentFields:
    """Test that the generate form has topics and content textarea."""

    def test_form_has_topics_field(self, client):
        """Generate form includes a topics input."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert 'name="topics"' in html

    def test_form_has_content_text_field(self, client):
        """Generate form includes a content textarea."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert 'name="content_text"' in html

    def test_form_has_content_placeholder(self, client):
        """Content textarea has helpful placeholder text."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "curriculum framework" in html.lower()

    def test_post_with_topics(self, client):
        """POST with topics generates a quiz successfully."""
        response = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "topics": "cell transport, osmosis, diffusion",
                "question_types": ["mc", "tf"],
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)
        assert "/quizzes/" in response.headers["Location"]

    def test_post_with_content_text(self, client):
        """POST with content text generates a quiz successfully."""
        response = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "content_text": "Students should understand that cell membranes are selectively permeable.",
                "question_types": ["mc"],
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)
        assert "/quizzes/" in response.headers["Location"]

    def test_post_with_both_topics_and_content(self, client):
        """POST with both topics and content text works."""
        response = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "topics": "osmosis",
                "content_text": "Water moves from high to low concentration across a membrane.",
                "question_types": ["mc", "tf"],
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)

    def test_topics_stored_in_style_profile(self, client, app):
        """Topics are saved in the quiz style_profile for traceability."""
        client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "topics": "osmosis, diffusion",
                "question_types": ["mc"],
            },
            follow_redirects=True,
        )
        with app.app_context():
            from src.web.blueprints.helpers import _get_session

            session = _get_session()
            quiz = session.query(Quiz).order_by(Quiz.id.desc()).first()
            profile = json.loads(quiz.style_profile)
            assert "osmosis" in profile.get("topics", "")


# ============================================================
# F6: Independent Question Types
# ============================================================


class TestIndependentQuestionTypes:
    """Test that question types are decoupled from cognitive levels."""

    def test_form_has_question_type_checkboxes(self, client):
        """Generate form includes independent question type checkboxes."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert 'name="question_types"' in html
        assert 'value="mc"' in html
        assert 'value="tf"' in html
        assert 'value="short_answer"' in html
        assert 'value="fill_in_blank"' in html
        assert 'value="matching"' in html
        assert 'value="ordering"' in html

    def test_cognitive_table_has_no_type_column(self, client):
        """Cognitive distribution table header has Level and Count, not Question Types."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "cognitive-table" in html
        # Extract the cognitive table HTML to check its headers
        table_start = html.find('id="cognitive-table"')
        table_end = html.find("</table>", table_start)
        table_html = html[table_start:table_end]
        assert "<th>Level</th>" in table_html
        assert "<th>Count</th>" in table_html
        assert "Question Types" not in table_html

    def test_post_with_question_types(self, client):
        """POST with specific question types generates a quiz."""
        response = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "topics": "photosynthesis",
                "question_types": ["mc", "short_answer", "fill_in_blank"],
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)

    def test_question_types_stored_in_style_profile(self, client, app):
        """Selected question types are saved in style_profile."""
        client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "topics": "genetics",
                "question_types": ["mc", "tf", "short_answer"],
            },
            follow_redirects=True,
        )
        with app.app_context():
            from src.web.blueprints.helpers import _get_session

            session = _get_session()
            quiz = session.query(Quiz).order_by(Quiz.id.desc()).first()
            profile = json.loads(quiz.style_profile)
            assert "mc" in profile.get("question_types", [])
            assert "tf" in profile.get("question_types", [])
            assert "short_answer" in profile.get("question_types", [])

    def test_default_question_types_when_none_selected(self, client):
        """When no question types are posted, defaults to mc + tf."""
        response = client.post(
            "/classes/1/generate",
            data={
                "num_questions": "5",
                "topics": "ecology",
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)


# ============================================================
# F2: Standards Search
# ============================================================


class TestStandardsSearch:
    """Test standards search API improvements."""

    def test_standards_search_returns_json(self, client):
        """Standards search API returns JSON with results array."""
        response = client.get("/api/standards/search?q=test")
        assert response.status_code == 200
        data = response.get_json()
        assert "results" in data

    def test_standards_search_includes_total(self, client):
        """Standards search response includes total count and truncated flag."""
        response = client.get("/api/standards/search?q=test")
        data = response.get_json()
        assert "total" in data
        assert "truncated" in data

    def test_standards_search_empty_query(self, client):
        """Empty query returns empty results."""
        response = client.get("/api/standards/search?q=")
        data = response.get_json()
        assert data["results"] == []


# ============================================================
# F8: Difficulty Slider
# ============================================================


class TestDifficultySlider:
    """Test difficulty slider labels and behavior."""

    def test_form_has_difficulty_slider(self, client):
        """Generate form has a difficulty range slider."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert 'name="difficulty"' in html
        assert 'type="range"' in html

    def test_difficulty_has_tooltip(self, client):
        """Difficulty slider has a descriptive tooltip."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "basic recall" in html.lower() or "complexity" in html.lower()


# ============================================================
# Form Structure
# ============================================================


class TestFormStructure:
    """Test form is organized into logical sections."""

    def test_form_has_fieldsets(self, client):
        """Generate form is organized into fieldset sections."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "<fieldset" in html
        assert "<legend>" in html

    def test_form_has_content_section_first(self, client):
        """The 'what should the quiz cover' section appears before quiz structure."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        topics_pos = html.find('name="topics"')
        num_q_pos = html.find('name="num_questions"')
        assert topics_pos < num_q_pos, "Topics should appear before num_questions"


# ============================================================
# Pipeline Wiring
# ============================================================


class TestPipelineWiring:
    """Test that topics and content flow through the generation pipeline."""

    def test_generate_quiz_accepts_topics(self):
        """generate_quiz() accepts topics parameter."""
        from src.quiz_generator import generate_quiz
        import inspect

        sig = inspect.signature(generate_quiz)
        assert "topics" in sig.parameters
        assert "content_text" in sig.parameters
        assert "question_types" in sig.parameters

    def test_build_class_context_with_user_content(self):
        """_build_class_context_section prioritizes user content."""
        from src.agents import _build_class_context_section

        context = {
            "content_summary": "Cell transport and osmosis",
            "user_provided_content": True,
            "lesson_logs": [
                {"date": "2026-02-01", "topics": ["photosynthesis"]},
            ],
        }
        result = _build_class_context_section(context)
        assert "Teacher-Provided Content" in result
        assert "Cell transport and osmosis" in result
        assert "Supplementary" in result

    def test_build_class_context_without_user_content(self):
        """Without user content, lesson logs are primary context."""
        from src.agents import _build_class_context_section

        context = {
            "content_summary": "",
            "user_provided_content": False,
            "lesson_logs": [
                {"date": "2026-02-01", "topics": ["photosynthesis"]},
            ],
        }
        result = _build_class_context_section(context)
        assert "Teacher-Provided Content" not in result
        assert "Class Context" in result

    def test_build_cognitive_section_with_question_types(self):
        """_build_cognitive_section includes question types in prompt."""
        from src.agents import _build_cognitive_section

        context = {
            "question_types": ["mc", "tf", "short_answer"],
            "difficulty": 3,
        }
        result = _build_cognitive_section(context)
        assert "Multiple Choice" in result
        assert "True/False" in result
        assert "Short Answer" in result

    def test_extract_teacher_config_uses_question_types(self):
        """_extract_teacher_config prefers context question_types."""
        from src.agents import _extract_teacher_config

        context = {
            "question_types": ["mc", "tf", "fill_in_blank"],
        }
        config = _extract_teacher_config(context)
        assert config is not None
        assert set(config["allowed_types"]) == {"mc", "tf", "fill_in_blank"}
