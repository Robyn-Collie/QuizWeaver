"""
Tests for QuizWeaver content blueprint routes.

Tests cover all 22 routes in src/web/blueprints/content.py:
- Question bank (list, add to bank, remove from bank)
- Variants (generate form GET/POST, list)
- Rubrics (generate GET/POST, detail, export CSV/DOCX/PDF, delete API)
- Topic-based generation (form GET/POST for quiz and study, search API)
- Lesson plans (list, generate GET/POST, detail, edit, export PDF/DOCX, delete, generate-quiz redirect)
- Quiz templates (list, export, import GET/POST, validate API)
"""

import json
import os
import tempfile
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from src.database import (
    Base,
    Class,
    LessonPlan,
    Question,
    Quiz,
    Rubric,
    RubricCriterion,
    get_engine,
    get_session,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def app():
    """Create a Flask test app with seeded content data."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed a class
    cls = Class(
        name="Test Class",
        grade_level="8th Grade",
        subject="Science",
        standards=json.dumps(["SOL 8.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    # Seed a quiz with questions
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
        text="What is gravity?",
        points=5.0,
        saved_to_bank=0,
        data=json.dumps(
            {
                "type": "mc",
                "text": "What is gravity?",
                "options": ["A force", "A color", "A sound", "A taste"],
                "correct_index": 0,
            }
        ),
    )
    q2 = Question(
        quiz_id=quiz.id,
        question_type="tf",
        title="Q2",
        text="The sun is a star.",
        points=2.0,
        saved_to_bank=1,
        data=json.dumps({"type": "tf", "text": "The sun is a star.", "is_true": True}),
    )
    session.add(q1)
    session.add(q2)
    session.commit()

    # Seed a rubric with criteria
    rubric = Rubric(
        quiz_id=quiz.id,
        title="Test Rubric",
        status="generated",
    )
    session.add(rubric)
    session.commit()

    criterion = RubricCriterion(
        rubric_id=rubric.id,
        sort_order=1,
        criterion="Scientific Vocabulary",
        description="Uses correct scientific terms",
        max_points=5.0,
        levels=json.dumps(
            [
                {"level": 4, "label": "Exemplary", "description": "Always uses correct terms"},
                {"level": 3, "label": "Proficient", "description": "Usually uses correct terms"},
            ]
        ),
    )
    session.add(criterion)
    session.commit()

    # Seed a lesson plan
    plan = LessonPlan(
        class_id=cls.id,
        title="Test Lesson Plan",
        topics=json.dumps(["Gravity", "Forces"]),
        standards=json.dumps(["SOL 8.1"]),
        grade_level="8th Grade",
        duration_minutes=50,
        plan_data=json.dumps(
            {
                "learning_objectives": "Students will understand gravity.",
                "warm_up": "Discuss what holds us on Earth.",
            }
        ),
        status="draft",
    )
    session.add(plan)
    session.commit()

    # Seed an imported quiz (template)
    template_quiz = Quiz(
        title="Imported Template",
        class_id=cls.id,
        status="imported",
        style_profile=json.dumps({"grade_level": "8th Grade"}),
    )
    session.add(template_quiz)
    session.commit()

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "8th Grade Science"},
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


@pytest.fixture
def anon_client(app):
    """Create an unauthenticated test client."""
    return app.test_client()


# ============================================================
# Question Bank Tests
# ============================================================


class TestQuestionBank:
    """Tests for /question-bank routes."""

    def test_question_bank_get(self, client):
        """GET /question-bank returns 200 with saved questions."""
        resp = client.get("/question-bank")
        assert resp.status_code == 200
        # Q2 is saved_to_bank=1, so it should appear
        assert b"The sun is a star" in resp.data

    def test_question_bank_filter_by_type(self, client):
        """GET /question-bank?type=tf filters by question type."""
        resp = client.get("/question-bank?type=tf")
        assert resp.status_code == 200
        assert b"The sun is a star" in resp.data

    def test_question_bank_search(self, client):
        """GET /question-bank?search=sun filters by text."""
        resp = client.get("/question-bank?search=sun")
        assert resp.status_code == 200
        assert b"The sun is a star" in resp.data

    def test_question_bank_search_no_results(self, client):
        """GET /question-bank?search=xyz returns empty results."""
        resp = client.get("/question-bank?search=xyz_nonexistent")
        assert resp.status_code == 200
        # Should not contain any question text
        assert b"What is gravity" not in resp.data

    def test_question_bank_requires_login(self, anon_client):
        """Question bank requires authentication."""
        resp = anon_client.get("/question-bank")
        assert resp.status_code == 303

    def test_api_question_bank_add(self, client):
        """POST /api/question-bank/add saves a question to the bank."""
        resp = client.post(
            "/api/question-bank/add",
            json={"question_id": 1},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_api_question_bank_add_missing_id(self, client):
        """POST /api/question-bank/add without question_id returns 400."""
        resp = client.post("/api/question-bank/add", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_api_question_bank_add_not_found(self, client):
        """POST /api/question-bank/add with invalid ID returns 404."""
        resp = client.post("/api/question-bank/add", json={"question_id": 9999})
        assert resp.status_code == 404

    def test_api_question_bank_remove(self, client):
        """POST /api/question-bank/remove unsaves a question from the bank."""
        resp = client.post(
            "/api/question-bank/remove",
            json={"question_id": 2},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_api_question_bank_remove_missing_id(self, client):
        """POST /api/question-bank/remove without question_id returns 400."""
        resp = client.post("/api/question-bank/remove", json={})
        assert resp.status_code == 400

    def test_api_question_bank_remove_not_found(self, client):
        """POST /api/question-bank/remove with invalid ID returns 404."""
        resp = client.post("/api/question-bank/remove", json={"question_id": 9999})
        assert resp.status_code == 404


# ============================================================
# Variant Routes Tests
# ============================================================


class TestVariantRoutes:
    """Tests for /quizzes/<id>/generate-variant and /quizzes/<id>/variants."""

    def test_generate_variant_get(self, client):
        """GET /quizzes/1/generate-variant returns form with reading levels."""
        resp = client.get("/quizzes/1/generate-variant")
        assert resp.status_code == 200
        assert b"reading_level" in resp.data

    def test_generate_variant_get_404(self, client):
        """GET /quizzes/9999/generate-variant returns 404."""
        resp = client.get("/quizzes/9999/generate-variant")
        assert resp.status_code == 404

    def test_generate_variant_post_invalid_level(self, client):
        """POST with invalid reading level returns 400."""
        resp = client.post(
            "/quizzes/1/generate-variant",
            data={"reading_level": "invalid_level"},
        )
        assert resp.status_code == 400
        assert b"valid reading level" in resp.data

    def test_generate_variant_post_success(self, client):
        """POST with valid reading level generates variant and redirects."""
        mock_variant = MagicMock()
        mock_variant.id = 99
        with patch("src.web.blueprints.content.generate_variant", return_value=mock_variant):
            resp = client.post(
                "/quizzes/1/generate-variant",
                data={"reading_level": "ell"},
            )
        assert resp.status_code == 303

    def test_generate_variant_post_failure(self, client):
        """POST that fails returns 500 with error message."""
        with patch("src.web.blueprints.content.generate_variant", return_value=None):
            resp = client.post(
                "/quizzes/1/generate-variant",
                data={"reading_level": "ell"},
            )
        assert resp.status_code == 500
        assert b"generation failed" in resp.data.lower()

    def test_generate_variant_post_provider_error(self, client):
        """POST that raises ProviderError shows error message."""
        from src.llm_provider import ProviderError

        with patch(
            "src.web.blueprints.content.generate_variant",
            side_effect=ProviderError("API failed", "The LLM provider is unavailable."),
        ):
            resp = client.post(
                "/quizzes/1/generate-variant",
                data={"reading_level": "ell"},
            )
        assert resp.status_code == 500

    def test_generate_variant_post_with_provider_override(self, client):
        """POST with provider override saves last-used provider."""
        mock_variant = MagicMock()
        mock_variant.id = 99
        with (
            patch("src.web.blueprints.content.generate_variant", return_value=mock_variant),
            patch("src.web.config_utils.save_config"),
        ):
            resp = client.post(
                "/quizzes/1/generate-variant",
                data={"reading_level": "ell", "provider": "mock"},
            )
        assert resp.status_code == 303

    def test_quiz_variants_list(self, client):
        """GET /quizzes/1/variants returns variant list."""
        resp = client.get("/quizzes/1/variants")
        assert resp.status_code == 200

    def test_quiz_variants_list_404(self, client):
        """GET /quizzes/9999/variants returns 404."""
        resp = client.get("/quizzes/9999/variants")
        assert resp.status_code == 404

    def test_generate_variant_requires_login(self, anon_client):
        """Variant generation requires authentication."""
        resp = anon_client.get("/quizzes/1/generate-variant")
        assert resp.status_code == 303


# ============================================================
# Rubric Routes Tests
# ============================================================


class TestRubricRoutes:
    """Tests for rubric generation, detail, export, and delete."""

    def test_generate_rubric_get(self, client):
        """GET /quizzes/1/generate-rubric returns form."""
        resp = client.get("/quizzes/1/generate-rubric")
        assert resp.status_code == 200

    def test_generate_rubric_get_404(self, client):
        """GET /quizzes/9999/generate-rubric returns 404 for missing quiz."""
        resp = client.get("/quizzes/9999/generate-rubric")
        assert resp.status_code == 404

    def test_generate_rubric_post_success(self, client):
        """POST generate rubric with valid data redirects to detail."""
        mock_rubric = MagicMock()
        mock_rubric.id = 99
        with patch("src.web.blueprints.content.generate_rubric", return_value=mock_rubric):
            resp = client.post(
                "/quizzes/1/generate-rubric",
                data={"title": "My Rubric"},
            )
        assert resp.status_code == 303

    def test_generate_rubric_post_failure(self, client):
        """POST generate rubric failure returns 500."""
        with patch("src.web.blueprints.content.generate_rubric", return_value=None):
            resp = client.post(
                "/quizzes/1/generate-rubric",
                data={"title": "My Rubric"},
            )
        assert resp.status_code == 500

    def test_generate_rubric_post_provider_error(self, client):
        """POST that raises ProviderError shows error."""
        from src.llm_provider import ProviderError

        with patch(
            "src.web.blueprints.content.generate_rubric",
            side_effect=ProviderError("API failed", "Provider unavailable."),
        ):
            resp = client.post(
                "/quizzes/1/generate-rubric",
                data={"title": "My Rubric"},
            )
        assert resp.status_code == 500

    def test_generate_rubric_post_with_provider_override(self, client):
        """POST with provider override saves last-used provider."""
        mock_rubric = MagicMock()
        mock_rubric.id = 99
        with (
            patch("src.web.blueprints.content.generate_rubric", return_value=mock_rubric),
            patch("src.web.config_utils.save_config"),
        ):
            resp = client.post(
                "/quizzes/1/generate-rubric",
                data={"title": "My Rubric", "provider": "mock"},
            )
        assert resp.status_code == 303

    def test_rubric_detail(self, client):
        """GET /rubrics/1 returns rubric detail with criteria."""
        resp = client.get("/rubrics/1")
        assert resp.status_code == 200
        assert b"Scientific Vocabulary" in resp.data

    def test_rubric_detail_404(self, client):
        """GET /rubrics/9999 returns 404."""
        resp = client.get("/rubrics/9999")
        assert resp.status_code == 404

    def test_rubric_export_csv(self, client):
        """GET /rubrics/1/export/csv downloads CSV file."""
        with patch("src.web.blueprints.content.export_rubric_csv", return_value="col1,col2\nval1,val2"):
            resp = client.get("/rubrics/1/export/csv")
        assert resp.status_code == 200
        assert resp.content_type == "text/csv; charset=utf-8"

    def test_rubric_export_docx(self, client):
        """GET /rubrics/1/export/docx downloads DOCX file."""
        buf = BytesIO(b"fake docx content")
        with patch("src.web.blueprints.content.export_rubric_docx", return_value=buf):
            resp = client.get("/rubrics/1/export/docx")
        assert resp.status_code == 200
        assert "wordprocessingml" in resp.content_type

    def test_rubric_export_pdf(self, client):
        """GET /rubrics/1/export/pdf downloads PDF file."""
        buf = BytesIO(b"%PDF-1.4 fake pdf content")
        with patch("src.web.blueprints.content.export_rubric_pdf", return_value=buf):
            resp = client.get("/rubrics/1/export/pdf")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    def test_rubric_export_invalid_format(self, client):
        """GET /rubrics/1/export/xml returns 404 for unsupported format."""
        resp = client.get("/rubrics/1/export/xml")
        assert resp.status_code == 404

    def test_rubric_export_missing_rubric(self, client):
        """GET /rubrics/9999/export/csv returns 404."""
        resp = client.get("/rubrics/9999/export/csv")
        assert resp.status_code == 404

    def test_api_rubric_delete(self, client):
        """DELETE /api/rubrics/1 deletes rubric and returns ok."""
        resp = client.delete("/api/rubrics/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_api_rubric_delete_not_found(self, client):
        """DELETE /api/rubrics/9999 returns 404."""
        resp = client.delete("/api/rubrics/9999")
        assert resp.status_code == 404

    def test_rubric_detail_requires_login(self, anon_client):
        """Rubric detail requires authentication."""
        resp = anon_client.get("/rubrics/1")
        assert resp.status_code == 303


# ============================================================
# Topic-Based Generation Tests
# ============================================================


class TestTopicGeneration:
    """Tests for /generate/topics and /api/topics/search."""

    def test_generate_topics_get(self, client):
        """GET /generate/topics returns form."""
        resp = client.get("/generate/topics")
        assert resp.status_code == 200

    def test_generate_topics_get_with_class_id(self, client):
        """GET /generate/topics?class_id=1 pre-selects class."""
        resp = client.get("/generate/topics?class_id=1")
        assert resp.status_code == 200

    def test_generate_topics_post_quiz_success(self, client):
        """POST /generate/topics with output_type=quiz generates and redirects."""
        mock_quiz = MagicMock()
        mock_quiz.id = 99
        with patch("src.web.blueprints.content.generate_from_topics", return_value=mock_quiz):
            resp = client.post(
                "/generate/topics",
                data={
                    "class_id": 1,
                    "topics": "Gravity, Forces",
                    "output_type": "quiz",
                    "num_questions": 10,
                    "difficulty": 3,
                },
            )
        assert resp.status_code == 303

    def test_generate_topics_post_quiz_failure(self, client):
        """POST /generate/topics quiz failure returns form with error."""
        with patch("src.web.blueprints.content.generate_from_topics", return_value=None):
            resp = client.post(
                "/generate/topics",
                data={
                    "class_id": 1,
                    "topics": "Gravity",
                    "output_type": "quiz",
                },
            )
        assert resp.status_code == 200
        assert b"generation failed" in resp.data.lower() or b"failed" in resp.data.lower()

    def test_generate_topics_post_study_success(self, client):
        """POST /generate/topics with output_type=flashcard generates study material."""
        mock_study = MagicMock()
        mock_study.id = 99
        with patch("src.web.blueprints.content.generate_from_topics", return_value=mock_study):
            resp = client.post(
                "/generate/topics",
                data={
                    "class_id": 1,
                    "topics": "Gravity, Forces",
                    "output_type": "flashcard",
                },
            )
        assert resp.status_code == 303

    def test_generate_topics_post_study_failure(self, client):
        """POST /generate/topics study failure returns form with error."""
        with patch("src.web.blueprints.content.generate_from_topics", return_value=None):
            resp = client.post(
                "/generate/topics",
                data={
                    "class_id": 1,
                    "topics": "Gravity",
                    "output_type": "flashcard",
                },
            )
        assert resp.status_code == 200
        assert b"failed" in resp.data.lower()

    def test_generate_topics_post_empty_topics(self, client):
        """POST /generate/topics with empty topics shows error."""
        resp = client.post(
            "/generate/topics",
            data={
                "class_id": 1,
                "topics": "",
                "output_type": "quiz",
            },
        )
        assert resp.status_code == 200
        assert b"topic" in resp.data.lower()

    def test_generate_topics_post_provider_error_quiz(self, client):
        """POST /generate/topics quiz ProviderError shows user message."""
        from src.llm_provider import ProviderError

        with patch(
            "src.web.blueprints.content.generate_from_topics",
            side_effect=ProviderError("API err", "Provider unavailable."),
        ):
            resp = client.post(
                "/generate/topics",
                data={
                    "class_id": 1,
                    "topics": "Gravity",
                    "output_type": "quiz",
                },
            )
        assert resp.status_code == 200

    def test_generate_topics_post_provider_error_study(self, client):
        """POST /generate/topics study ProviderError shows user message."""
        from src.llm_provider import ProviderError

        with patch(
            "src.web.blueprints.content.generate_from_topics",
            side_effect=ProviderError("API err", "Provider unavailable."),
        ):
            resp = client.post(
                "/generate/topics",
                data={
                    "class_id": 1,
                    "topics": "Gravity",
                    "output_type": "flashcard",
                },
            )
        assert resp.status_code == 200

    def test_generate_topics_requires_login(self, anon_client):
        """Topic generation requires authentication."""
        resp = anon_client.get("/generate/topics")
        assert resp.status_code == 303

    def test_api_topics_search(self, client):
        """GET /api/topics/search returns JSON topics list."""
        with patch("src.web.blueprints.content.search_topics", return_value=["Gravity", "Forces"]):
            resp = client.get("/api/topics/search?class_id=1&q=grav")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "topics" in data
        assert "Gravity" in data["topics"]

    def test_api_topics_search_no_class(self, client):
        """GET /api/topics/search without class_id returns empty topics."""
        resp = client.get("/api/topics/search?q=grav")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["topics"] == []


class TestTopicGenerationNoClasses:
    """Tests for /generate/topics when no classes exist."""

    def test_generate_topics_no_classes_redirects(self, make_flask_app):
        """GET /generate/topics redirects to class creation when no classes exist."""
        app = make_flask_app()
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        resp = c.get("/generate/topics")
        assert resp.status_code == 303


# ============================================================
# Lesson Plan Routes Tests
# ============================================================


class TestLessonPlanRoutes:
    """Tests for lesson plan list, generate, detail, edit, export, delete."""

    def test_lesson_plan_list(self, client):
        """GET /lesson-plans returns list of plans."""
        resp = client.get("/lesson-plans")
        assert resp.status_code == 200
        assert b"Test Lesson Plan" in resp.data

    def test_lesson_plan_list_filter_by_class(self, client):
        """GET /lesson-plans?class_id=1 filters by class."""
        resp = client.get("/lesson-plans?class_id=1")
        assert resp.status_code == 200
        assert b"Test Lesson Plan" in resp.data

    def test_lesson_plan_list_search(self, client):
        """GET /lesson-plans?q=Test filters by title."""
        resp = client.get("/lesson-plans?q=Test")
        assert resp.status_code == 200
        assert b"Test Lesson Plan" in resp.data

    def test_lesson_plan_list_search_no_results(self, client):
        """GET /lesson-plans?q=xyz returns no plans."""
        resp = client.get("/lesson-plans?q=xyz_nonexistent")
        assert resp.status_code == 200
        assert b"Test Lesson Plan" not in resp.data

    def test_lesson_plan_generate_get(self, client):
        """GET /lesson-plans/generate returns form."""
        resp = client.get("/lesson-plans/generate")
        assert resp.status_code == 200

    def test_lesson_plan_generate_get_with_prefill(self, client):
        """GET /lesson-plans/generate?topics=Gravity&standards=SOL+8.1 prefills form."""
        resp = client.get("/lesson-plans/generate?topics=Gravity&standards=SOL+8.1&class_id=1")
        assert resp.status_code == 200

    def test_lesson_plan_generate_post_success(self, client):
        """POST /lesson-plans/generate with valid data redirects to detail."""
        mock_plan = MagicMock()
        mock_plan.id = 99
        with patch("src.lesson_plan_generator.generate_lesson_plan", return_value=mock_plan):
            resp = client.post(
                "/lesson-plans/generate",
                data={
                    "class_id": 1,
                    "topics": "Gravity, Forces",
                    "standards": "SOL 8.1",
                    "duration_minutes": 50,
                    "grade_level": "8th Grade",
                },
            )
        assert resp.status_code == 303

    def test_lesson_plan_generate_post_no_class(self, client):
        """POST /lesson-plans/generate without class_id returns 400."""
        resp = client.post(
            "/lesson-plans/generate",
            data={
                "topics": "Gravity",
                "duration_minutes": 50,
            },
        )
        assert resp.status_code == 400

    def test_lesson_plan_generate_post_failure(self, client):
        """POST /lesson-plans/generate that fails returns 500."""
        with patch("src.lesson_plan_generator.generate_lesson_plan", return_value=None):
            resp = client.post(
                "/lesson-plans/generate",
                data={
                    "class_id": 1,
                    "topics": "Gravity",
                },
            )
        assert resp.status_code == 500

    def test_lesson_plan_generate_post_provider_error(self, client):
        """POST that raises ProviderError shows error."""
        from src.llm_provider import ProviderError

        with patch(
            "src.lesson_plan_generator.generate_lesson_plan",
            side_effect=ProviderError("API err", "Provider unavailable."),
        ):
            resp = client.post(
                "/lesson-plans/generate",
                data={
                    "class_id": 1,
                    "topics": "Gravity",
                },
            )
        assert resp.status_code == 500

    def test_lesson_plan_generate_post_with_provider_override(self, client):
        """POST with provider override saves last-used provider."""
        mock_plan = MagicMock()
        mock_plan.id = 99
        with (
            patch("src.lesson_plan_generator.generate_lesson_plan", return_value=mock_plan),
            patch("src.web.config_utils.save_config"),
        ):
            resp = client.post(
                "/lesson-plans/generate",
                data={
                    "class_id": 1,
                    "topics": "Gravity",
                    "provider": "mock",
                },
            )
        assert resp.status_code == 303

    def test_lesson_plan_detail(self, client):
        """GET /lesson-plans/1 returns detail page."""
        resp = client.get("/lesson-plans/1")
        assert resp.status_code == 200
        assert b"Test Lesson Plan" in resp.data

    def test_lesson_plan_detail_404(self, client):
        """GET /lesson-plans/9999 returns 404."""
        resp = client.get("/lesson-plans/9999")
        assert resp.status_code == 404

    def test_lesson_plan_detail_saved_message(self, client):
        """GET /lesson-plans/1?saved=1 shows success message."""
        resp = client.get("/lesson-plans/1?saved=1")
        assert resp.status_code == 200

    def test_lesson_plan_edit(self, client):
        """POST /lesson-plans/1/edit saves section and redirects."""
        resp = client.post(
            "/lesson-plans/1/edit",
            data={
                "section_key": "warm_up",
                "section_content": "Updated warm-up activity",
            },
        )
        assert resp.status_code == 303

    def test_lesson_plan_edit_404(self, client):
        """POST /lesson-plans/9999/edit returns 404."""
        resp = client.post(
            "/lesson-plans/9999/edit",
            data={"section_key": "warm_up", "section_content": "Updated"},
        )
        assert resp.status_code == 404

    def test_lesson_plan_edit_no_section_key(self, client):
        """POST /lesson-plans/1/edit without section_key redirects with error."""
        resp = client.post(
            "/lesson-plans/1/edit",
            data={"section_key": "", "section_content": "Content"},
        )
        assert resp.status_code == 303

    def test_lesson_plan_export_pdf(self, client):
        """GET /lesson-plans/1/export/pdf downloads PDF."""
        buf = BytesIO(b"%PDF-1.4 fake pdf")
        with patch("src.lesson_plan_export.export_lesson_plan_pdf", return_value=buf):
            resp = client.get("/lesson-plans/1/export/pdf")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    def test_lesson_plan_export_docx(self, client):
        """GET /lesson-plans/1/export/docx downloads DOCX."""
        buf = BytesIO(b"fake docx")
        with patch("src.lesson_plan_export.export_lesson_plan_docx", return_value=buf):
            resp = client.get("/lesson-plans/1/export/docx")
        assert resp.status_code == 200
        assert "wordprocessingml" in resp.content_type

    def test_lesson_plan_export_invalid_format(self, client):
        """GET /lesson-plans/1/export/xml returns 400."""
        resp = client.get("/lesson-plans/1/export/xml")
        assert resp.status_code == 400

    def test_lesson_plan_export_404(self, client):
        """GET /lesson-plans/9999/export/pdf returns 404."""
        resp = client.get("/lesson-plans/9999/export/pdf")
        assert resp.status_code == 404

    def test_lesson_plan_delete(self, client):
        """POST /lesson-plans/1/delete removes plan and redirects."""
        resp = client.post("/lesson-plans/1/delete")
        assert resp.status_code == 303

    def test_lesson_plan_delete_404(self, client):
        """POST /lesson-plans/9999/delete returns 404."""
        resp = client.post("/lesson-plans/9999/delete")
        assert resp.status_code == 404

    def test_lesson_plan_generate_quiz_redirect(self, client):
        """GET /lesson-plans/1/generate-quiz redirects to quiz generation."""
        resp = client.get("/lesson-plans/1/generate-quiz")
        assert resp.status_code == 303
        assert "/generate" in resp.headers["Location"]

    def test_lesson_plan_generate_quiz_redirect_404(self, client):
        """GET /lesson-plans/9999/generate-quiz returns 404."""
        resp = client.get("/lesson-plans/9999/generate-quiz")
        assert resp.status_code == 404

    def test_lesson_plan_requires_login(self, anon_client):
        """Lesson plan list requires authentication."""
        resp = anon_client.get("/lesson-plans")
        assert resp.status_code == 303


# ============================================================
# Quiz Template Routes Tests
# ============================================================


class TestQuizTemplateRoutes:
    """Tests for quiz template list, export, import, and validate."""

    def test_quiz_template_list(self, client):
        """GET /quiz-templates returns list of imported templates."""
        resp = client.get("/quiz-templates")
        assert resp.status_code == 200
        assert b"Imported Template" in resp.data

    def test_quiz_template_list_requires_login(self, anon_client):
        """Template list requires authentication."""
        resp = anon_client.get("/quiz-templates")
        assert resp.status_code == 303

    def test_quiz_export_template(self, client):
        """GET /quizzes/1/export-template downloads JSON template."""
        template_data = {
            "title": "Test Quiz",
            "questions": [{"text": "Q1", "type": "mc"}],
        }
        with patch("src.template_manager.export_quiz_template", return_value=template_data):
            resp = client.get("/quizzes/1/export-template")
        assert resp.status_code == 200
        assert resp.content_type == "application/json"

    def test_quiz_export_template_404(self, client):
        """GET /quizzes/9999/export-template returns 404 if export returns None."""
        with patch("src.template_manager.export_quiz_template", return_value=None):
            resp = client.get("/quizzes/9999/export-template")
        assert resp.status_code == 404

    def test_quiz_template_import_get(self, client):
        """GET /quiz-templates/import returns import form."""
        resp = client.get("/quiz-templates/import")
        assert resp.status_code == 200

    def test_quiz_template_import_post_success(self, client):
        """POST /quiz-templates/import with valid file imports template."""
        template_data = {
            "title": "Imported Quiz",
            "version": "1.0",
            "questions": [{"text": "Q1", "type": "mc", "options": ["A", "B"], "correct_index": 0}],
        }
        file_content = json.dumps(template_data).encode("utf-8")

        mock_quiz = MagicMock()
        mock_quiz.id = 99
        mock_quiz.title = "Imported Quiz"

        with (
            patch("src.template_manager.validate_template", return_value=(True, [])),
            patch("src.template_manager.import_quiz_template", return_value=mock_quiz),
        ):
            resp = client.post(
                "/quiz-templates/import",
                data={
                    "template_file": (BytesIO(file_content), "template.json"),
                    "class_id": 1,
                },
                content_type="multipart/form-data",
            )
        assert resp.status_code == 303

    def test_quiz_template_import_post_no_file(self, client):
        """POST /quiz-templates/import without file shows error."""
        resp = client.post(
            "/quiz-templates/import",
            data={"class_id": 1},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert b"select a template file" in resp.data.lower()

    def test_quiz_template_import_post_no_class(self, client):
        """POST /quiz-templates/import without class_id shows error."""
        file_content = json.dumps({"title": "Test"}).encode("utf-8")
        resp = client.post(
            "/quiz-templates/import",
            data={
                "template_file": (BytesIO(file_content), "template.json"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert b"select a class" in resp.data.lower()

    def test_quiz_template_import_post_invalid_json(self, client):
        """POST /quiz-templates/import with bad JSON shows error."""
        resp = client.post(
            "/quiz-templates/import",
            data={
                "template_file": (BytesIO(b"not json"), "bad.json"),
                "class_id": 1,
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert b"invalid json" in resp.data.lower()

    def test_quiz_template_import_post_validation_failure(self, client):
        """POST /quiz-templates/import with invalid template shows validation errors."""
        file_content = json.dumps({"title": "Test"}).encode("utf-8")
        with patch(
            "src.template_manager.validate_template",
            return_value=(False, ["Missing 'questions' field"]),
        ):
            resp = client.post(
                "/quiz-templates/import",
                data={
                    "template_file": (BytesIO(file_content), "template.json"),
                    "class_id": 1,
                },
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200
        assert b"validation failed" in resp.data.lower()

    def test_quiz_template_import_post_import_failure(self, client):
        """POST /quiz-templates/import where import returns None shows error."""
        file_content = json.dumps({"title": "Test", "questions": []}).encode("utf-8")
        with (
            patch("src.template_manager.validate_template", return_value=(True, [])),
            patch("src.template_manager.import_quiz_template", return_value=None),
        ):
            resp = client.post(
                "/quiz-templates/import",
                data={
                    "template_file": (BytesIO(file_content), "template.json"),
                    "class_id": 1,
                },
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200
        assert b"failed to import" in resp.data.lower()

    def test_api_quiz_template_validate_valid(self, client):
        """POST /api/quiz-templates/validate with valid data returns valid=True."""
        with patch("src.template_manager.validate_template", return_value=(True, [])):
            resp = client.post(
                "/api/quiz-templates/validate",
                json={"title": "Test", "questions": [{"text": "Q1"}]},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True
        assert data["errors"] == []

    def test_api_quiz_template_validate_invalid(self, client):
        """POST /api/quiz-templates/validate with invalid data returns errors."""
        with patch(
            "src.template_manager.validate_template",
            return_value=(False, ["Missing questions"]),
        ):
            resp = client.post(
                "/api/quiz-templates/validate",
                json={"title": "Test"},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_api_quiz_template_validate_no_json(self, client):
        """POST /api/quiz-templates/validate without JSON returns 400."""
        resp = client.post(
            "/api/quiz-templates/validate",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["valid"] is False
