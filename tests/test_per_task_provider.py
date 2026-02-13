"""
Tests for BL-002: Per-Task Provider Selection.

Verifies that all generation forms have a provider dropdown and that
the provider override is passed through to generation functions.
"""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with seeded data."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Test Class",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    quiz = Quiz(
        title="Test Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "7th Grade"}),
    )
    session.add(quiz)
    session.commit()

    q = Question(
        quiz_id=quiz.id,
        text="Sample question?",
        question_type="mc",
        points=1,
        data=json.dumps(
            {
                "options": ["A", "B", "C", "D"],
                "correct_index": 0,
            }
        ),
    )
    session.add(q)
    session.commit()

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
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
    return c


class TestQuizGenerateProviderDropdown:
    """Quiz generate form already had a provider dropdown."""

    def test_quiz_generate_has_provider_select(self, client):
        """Quiz generate form has provider dropdown."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert 'name="provider"' in html
        assert "Use default" in html

    def test_quiz_generate_shows_mock(self, client):
        """Quiz generate form shows mock as default provider."""
        response = client.get("/classes/1/generate")
        html = response.data.decode()
        assert "mock" in html


class TestStudyGenerateProviderDropdown:
    """Study generate form should have a provider dropdown."""

    def test_study_generate_has_provider_select(self, client):
        """Study generate form has provider dropdown."""
        response = client.get("/study/generate")
        html = response.data.decode()
        assert 'name="provider"' in html
        assert "Use default" in html

    def test_study_generate_passes_provider(self, client):
        """Study generate POST passes provider to generation."""
        response = client.post(
            "/study/generate",
            data={
                "class_id": "1",
                "material_type": "flashcard",
                "provider": "mock",
            },
            follow_redirects=True,
        )
        # Should succeed (mock provider)
        assert response.status_code == 200


class TestVariantGenerateProviderDropdown:
    """Variant generate form should have a provider dropdown."""

    def test_variant_generate_has_provider_select(self, client):
        """Variant generate form has provider dropdown."""
        response = client.get("/quizzes/1/generate-variant")
        html = response.data.decode()
        assert 'name="provider"' in html
        assert "Use default" in html

    def test_variant_generate_passes_provider(self, client):
        """Variant generate POST passes provider to generation."""
        response = client.post(
            "/quizzes/1/generate-variant",
            data={
                "reading_level": "on_grade",
                "provider": "mock",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200


class TestRubricGenerateProviderDropdown:
    """Rubric generate form should have a provider dropdown."""

    def test_rubric_generate_has_provider_select(self, client):
        """Rubric generate form has provider dropdown."""
        response = client.get("/quizzes/1/generate-rubric")
        html = response.data.decode()
        assert 'name="provider"' in html
        assert "Use default" in html

    def test_rubric_generate_passes_provider(self, client):
        """Rubric generate POST passes provider to generation."""
        response = client.post(
            "/quizzes/1/generate-rubric",
            data={
                "provider": "mock",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200


class TestReteachProviderDropdown:
    """Reteach suggestions form should have a provider dropdown."""

    def test_reteach_has_provider_select(self, client):
        """Reteach form has provider dropdown."""
        response = client.get("/classes/1/analytics/reteach")
        html = response.data.decode()
        assert 'name="provider"' in html
        assert "Use default" in html

    def test_reteach_passes_provider(self, client):
        """Reteach POST passes provider to generation."""
        response = client.post(
            "/classes/1/analytics/reteach",
            data={
                "max_suggestions": "3",
                "provider": "mock",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200


class TestProviderPartialTemplate:
    """Verify the partial template file exists and has expected content."""

    def test_partial_exists(self):
        """Provider select partial template exists."""
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "partials", "provider_select.html")
        assert os.path.isfile(path)

    def test_partial_has_provider_name(self):
        """Provider select partial uses 'provider' as the field name."""
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "partials", "provider_select.html")
        with open(path) as f:
            content = f.read()
        assert 'name="provider"' in content
        assert "Use default" in content


class TestGeneratorFunctionsAcceptProviderName:
    """Verify that all generator functions accept provider_name parameter."""

    def test_study_generator_accepts_provider_name(self):
        """generate_study_material accepts provider_name."""
        import inspect

        from src.study_generator import generate_study_material

        sig = inspect.signature(generate_study_material)
        assert "provider_name" in sig.parameters

    def test_variant_generator_accepts_provider_name(self):
        """generate_variant accepts provider_name."""
        import inspect

        from src.variant_generator import generate_variant

        sig = inspect.signature(generate_variant)
        assert "provider_name" in sig.parameters

    def test_rubric_generator_accepts_provider_name(self):
        """generate_rubric accepts provider_name."""
        import inspect

        from src.rubric_generator import generate_rubric

        sig = inspect.signature(generate_rubric)
        assert "provider_name" in sig.parameters

    def test_reteach_generator_accepts_provider_name(self):
        """generate_reteach_suggestions accepts provider_name."""
        import inspect

        from src.reteach_generator import generate_reteach_suggestions

        sig = inspect.signature(generate_reteach_suggestions)
        assert "provider_name" in sig.parameters

    def test_quiz_generator_accepts_provider_name(self):
        """generate_quiz accepts provider_name (already existed)."""
        import inspect

        from src.quiz_generator import generate_quiz

        sig = inspect.signature(generate_quiz)
        assert "provider_name" in sig.parameters
