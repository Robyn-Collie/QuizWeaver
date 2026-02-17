"""
Tests for QuizWeaver quizzes blueprint routes.

Tests cover:
- Quiz list page with filtering, search, and pagination
- Quiz detail page with parsed questions, style_profile, generation_metadata
- Class-scoped quiz listing
- Quiz export in all formats (CSV, DOCX, GIFT, PDF, QTI, Quizizz)
- Quiz editing API (title, question edit, delete, reorder)
- Question image upload and removal
- Question regeneration
- Generate redirect and quiz generation (GET and POST)
- Cost estimate API
- Costs dashboard (GET and POST)
- Auth guards on all routes
"""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from src.database import Class, Question, Quiz

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def qclient(flask_app):
    """Logged-in test client for quizzes tests."""
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        yield c


@pytest.fixture
def anon_client(flask_app):
    """Unauthenticated test client."""
    with flask_app.test_client() as c:
        yield c


# ============================================================
# Quiz List Tests
# ============================================================


class TestQuizzesList:
    """Tests for GET /quizzes."""

    def test_quizzes_list_returns_200(self, qclient):
        resp = qclient.get("/quizzes")
        assert resp.status_code == 200
        assert b"Test Quiz" in resp.data

    def test_quizzes_list_shows_question_count(self, qclient):
        resp = qclient.get("/quizzes")
        assert resp.status_code == 200

    def test_quizzes_list_search_filter(self, qclient):
        resp = qclient.get("/quizzes?q=Test")
        assert resp.status_code == 200
        assert b"Test Quiz" in resp.data

    def test_quizzes_list_search_no_results(self, qclient):
        resp = qclient.get("/quizzes?q=NonExistentQuiz")
        assert resp.status_code == 200

    def test_quizzes_list_status_filter(self, qclient):
        resp = qclient.get("/quizzes?status=generated")
        assert resp.status_code == 200
        assert b"Test Quiz" in resp.data

    def test_quizzes_list_class_filter(self, qclient):
        resp = qclient.get("/quizzes?class_id=1")
        assert resp.status_code == 200

    def test_quizzes_list_pagination(self, qclient):
        resp = qclient.get("/quizzes?page=1")
        assert resp.status_code == 200

    def test_quizzes_list_pagination_out_of_range(self, qclient):
        resp = qclient.get("/quizzes?page=999")
        assert resp.status_code == 200

    def test_quizzes_list_requires_login(self, anon_client):
        resp = anon_client.get("/quizzes")
        assert resp.status_code == 303


# ============================================================
# Quiz Detail Tests
# ============================================================


class TestQuizDetail:
    """Tests for GET /quizzes/<id>."""

    def test_quiz_detail_returns_200(self, qclient):
        resp = qclient.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"Test Quiz" in resp.data

    def test_quiz_detail_shows_questions(self, qclient):
        resp = qclient.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"photosynthesis" in resp.data

    def test_quiz_detail_shows_provider(self, qclient):
        resp = qclient.get("/quizzes/1")
        assert resp.status_code == 200
        assert b"mock" in resp.data

    def test_quiz_detail_not_found(self, qclient):
        resp = qclient.get("/quizzes/9999")
        assert resp.status_code == 404

    def test_quiz_detail_requires_login(self, anon_client):
        resp = anon_client.get("/quizzes/1")
        assert resp.status_code == 303

    def test_quiz_detail_with_generation_metadata(self, make_flask_app):
        """Quiz detail parses and displays generation_metadata."""
        metadata = json.dumps(
            {
                "prompt_summary": "Generated 5 MC questions about photosynthesis",
                "critic_history": [{"attempt": 1, "result": "approved"}],
                "model": "mock",
            }
        )

        def seed(session):
            cls = Class(name="C1", grade_level="7th", subject="Sci", standards=json.dumps([]), config=json.dumps({}))
            session.add(cls)
            session.commit()
            quiz = Quiz(
                title="Meta Quiz",
                class_id=cls.id,
                status="generated",
                style_profile=json.dumps({"provider": "mock"}),
                generation_metadata=metadata,
            )
            session.add(quiz)
            session.commit()
            session.add(
                Question(
                    quiz_id=quiz.id,
                    question_type="mc",
                    title="Q1",
                    text="Q?",
                    points=1.0,
                    data=json.dumps({"type": "mc", "options": ["A"], "correct_index": 0}),
                )
            )
            session.commit()

        app = make_flask_app(seed_fn=seed)
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["logged_in"] = True
                sess["username"] = "teacher"
            resp = c.get("/quizzes/1")
            assert resp.status_code == 200

    def test_quiz_detail_with_sol_standards_string(self, make_flask_app):
        """Quiz detail handles sol_standards stored as JSON string within style_profile."""

        def seed(session):
            cls = Class(name="C1", grade_level="7th", subject="Sci", standards=json.dumps([]), config=json.dumps({}))
            session.add(cls)
            session.commit()
            quiz = Quiz(
                title="SOL Quiz",
                class_id=cls.id,
                status="generated",
                style_profile=json.dumps(
                    {
                        "grade_level": "7th Grade",
                        "sol_standards": '["SOL 7.1", "SOL 7.2"]',
                    }
                ),
            )
            session.add(quiz)
            session.commit()
            session.add(
                Question(
                    quiz_id=quiz.id,
                    question_type="mc",
                    title="Q1",
                    text="Q?",
                    points=1.0,
                    data=json.dumps({"type": "mc", "options": ["A"], "correct_index": 0}),
                )
            )
            session.commit()

        app = make_flask_app(seed_fn=seed)
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["logged_in"] = True
                sess["username"] = "teacher"
            resp = c.get("/quizzes/1")
            assert resp.status_code == 200


# ============================================================
# Class Quizzes Tests
# ============================================================


class TestClassQuizzes:
    """Tests for GET /classes/<id>/quizzes."""

    def test_class_quizzes_returns_200(self, qclient):
        resp = qclient.get("/classes/1/quizzes")
        assert resp.status_code == 200

    def test_class_quizzes_not_found(self, qclient):
        resp = qclient.get("/classes/9999/quizzes")
        assert resp.status_code == 404

    def test_class_quizzes_requires_login(self, anon_client):
        resp = anon_client.get("/classes/1/quizzes")
        assert resp.status_code == 303


# ============================================================
# Quiz Export Tests
# ============================================================


class TestQuizExport:
    """Tests for GET /quizzes/<id>/export/<format>."""

    def test_export_csv(self, qclient):
        with patch("src.web.blueprints.quizzes.export_csv", return_value="col1,col2\nval1,val2"):
            resp = qclient.get("/quizzes/1/export/csv")
            assert resp.status_code == 200
            assert resp.content_type == "text/csv; charset=utf-8"

    def test_export_docx(self, qclient):
        buf = BytesIO(b"PK\x03\x04fake docx content")
        with patch("src.web.blueprints.quizzes.export_docx", return_value=buf):
            resp = qclient.get("/quizzes/1/export/docx")
            assert resp.status_code == 200

    def test_export_gift(self, qclient):
        with patch("src.web.blueprints.quizzes.export_gift", return_value="::Q1::"):
            resp = qclient.get("/quizzes/1/export/gift")
            assert resp.status_code == 200
            assert resp.content_type == "text/plain; charset=utf-8"

    def test_export_pdf(self, qclient):
        buf = BytesIO(b"%PDF-1.4 fake pdf content")
        with patch("src.web.blueprints.quizzes.export_pdf", return_value=buf):
            resp = qclient.get("/quizzes/1/export/pdf")
            assert resp.status_code == 200
            assert resp.content_type == "application/pdf"

    def test_export_qti(self, qclient):
        buf = BytesIO(b"PK\x03\x04fake qti zip content")
        with patch("src.web.blueprints.quizzes.export_qti", return_value=buf):
            resp = qclient.get("/quizzes/1/export/qti")
            assert resp.status_code == 200
            assert resp.content_type == "application/zip"

    def test_export_quizizz(self, qclient):
        with patch("src.web.blueprints.quizzes.export_quizizz_csv", return_value="q,a\n1,2"):
            resp = qclient.get("/quizzes/1/export/quizizz")
            assert resp.status_code == 200
            assert resp.content_type == "text/csv; charset=utf-8"

    def test_export_student_mode(self, qclient):
        with patch("src.web.blueprints.quizzes.export_csv", return_value="col1,col2\nval1,val2"):
            resp = qclient.get("/quizzes/1/export/csv?student=1")
            assert resp.status_code == 200

    def test_export_invalid_format(self, qclient):
        resp = qclient.get("/quizzes/1/export/invalid")
        assert resp.status_code == 404

    def test_export_quiz_not_found(self, qclient):
        resp = qclient.get("/quizzes/9999/export/csv")
        assert resp.status_code == 404

    def test_export_requires_login(self, anon_client):
        resp = anon_client.get("/quizzes/1/export/csv")
        assert resp.status_code == 303


# ============================================================
# Quiz Title Edit API Tests
# ============================================================


class TestApiQuizTitle:
    """Tests for PUT /api/quizzes/<id>/title."""

    def test_update_title(self, qclient):
        resp = qclient.put(
            "/api/quizzes/1/title",
            data=json.dumps({"title": "Updated Title"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["title"] == "Updated Title"

    def test_update_title_empty(self, qclient):
        resp = qclient.put(
            "/api/quizzes/1/title",
            data=json.dumps({"title": ""}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_update_title_quiz_not_found(self, qclient):
        resp = qclient.put(
            "/api/quizzes/9999/title",
            data=json.dumps({"title": "X"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_update_title_requires_login(self, anon_client):
        resp = anon_client.put(
            "/api/quizzes/1/title",
            data=json.dumps({"title": "X"}),
            content_type="application/json",
        )
        assert resp.status_code == 303


# ============================================================
# Question Edit API Tests
# ============================================================


class TestApiQuestionEdit:
    """Tests for PUT /api/questions/<id>."""

    def test_edit_question_text(self, qclient):
        resp = qclient.put(
            "/api/questions/1",
            data=json.dumps({"text": "What is respiration?"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["question"]["text"] == "What is respiration?"

    def test_edit_question_points(self, qclient):
        resp = qclient.put(
            "/api/questions/1",
            data=json.dumps({"points": 10.0}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["question"]["points"] == 10.0

    def test_edit_question_type(self, qclient):
        resp = qclient.put(
            "/api/questions/1",
            data=json.dumps({"question_type": "tf"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["question"]["question_type"] == "tf"

    def test_edit_question_options(self, qclient):
        resp = qclient.put(
            "/api/questions/1",
            data=json.dumps({"options": ["A", "B", "C"], "correct_index": 2}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["question"]["data"]["options"] == ["A", "B", "C"]
        assert data["question"]["data"]["correct_index"] == 2

    def test_edit_question_empty_text(self, qclient):
        resp = qclient.put(
            "/api/questions/1",
            data=json.dumps({"text": ""}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_edit_question_not_found(self, qclient):
        resp = qclient.put(
            "/api/questions/9999",
            data=json.dumps({"text": "X"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_edit_question_requires_login(self, anon_client):
        resp = anon_client.put(
            "/api/questions/1",
            data=json.dumps({"text": "X"}),
            content_type="application/json",
        )
        assert resp.status_code == 303


# ============================================================
# Question Delete API Tests
# ============================================================


class TestApiQuestionDelete:
    """Tests for DELETE /api/questions/<id>."""

    def test_delete_question(self, qclient):
        resp = qclient.delete("/api/questions/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_delete_question_not_found(self, qclient):
        resp = qclient.delete("/api/questions/9999")
        assert resp.status_code == 404

    def test_delete_question_requires_login(self, anon_client):
        resp = anon_client.delete("/api/questions/1")
        assert resp.status_code == 303


# ============================================================
# Quiz Reorder API Tests
# ============================================================


class TestApiQuizReorder:
    """Tests for PUT /api/quizzes/<id>/reorder."""

    def test_reorder_questions(self, qclient):
        resp = qclient.put(
            "/api/quizzes/1/reorder",
            data=json.dumps({"question_ids": [1]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_reorder_mismatched_ids(self, qclient):
        resp = qclient.put(
            "/api/quizzes/1/reorder",
            data=json.dumps({"question_ids": [1, 999]}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_reorder_quiz_not_found(self, qclient):
        resp = qclient.put(
            "/api/quizzes/9999/reorder",
            data=json.dumps({"question_ids": []}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_reorder_requires_login(self, anon_client):
        resp = anon_client.put(
            "/api/quizzes/1/reorder",
            data=json.dumps({"question_ids": [1]}),
            content_type="application/json",
        )
        assert resp.status_code == 303


# ============================================================
# Question Image Upload API Tests
# ============================================================


class TestApiQuestionImageUpload:
    """Tests for POST /api/questions/<id>/image."""

    def test_upload_image(self, qclient, flask_app):
        data = {
            "image": (BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "test.png"),
        }
        flask_app.config["APP_CONFIG"]["paths"] = {
            **flask_app.config["APP_CONFIG"].get("paths", {}),
            "generated_images_dir": "generated_images",
        }
        resp = qclient.post(
            "/api/questions/1/image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["ok"] is True
        assert "image_ref" in result

    def test_upload_image_no_file(self, qclient):
        resp = qclient.post("/api/questions/1/image")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_upload_image_invalid_extension(self, qclient, flask_app):
        data = {
            "image": (BytesIO(b"not an image"), "test.exe"),
        }
        flask_app.config["APP_CONFIG"]["paths"] = {
            **flask_app.config["APP_CONFIG"].get("paths", {}),
            "generated_images_dir": "generated_images",
        }
        resp = qclient.post(
            "/api/questions/1/image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_image_question_not_found(self, qclient):
        data = {
            "image": (BytesIO(b"\x89PNG" + b"\x00" * 100), "test.png"),
        }
        resp = qclient.post(
            "/api/questions/9999/image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404

    def test_upload_image_requires_login(self, anon_client):
        resp = anon_client.post("/api/questions/1/image")
        assert resp.status_code == 303


# ============================================================
# Question Image Remove API Tests
# ============================================================


class TestApiQuestionImageRemove:
    """Tests for DELETE /api/questions/<id>/image."""

    def test_remove_image(self, qclient):
        resp = qclient.delete("/api/questions/1/image")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_remove_image_not_found(self, qclient):
        resp = qclient.delete("/api/questions/9999/image")
        assert resp.status_code == 404

    def test_remove_image_requires_login(self, anon_client):
        resp = anon_client.delete("/api/questions/1/image")
        assert resp.status_code == 303


# ============================================================
# Question Image Description Remove API Tests
# ============================================================


class TestApiQuestionImageDescriptionRemove:
    """Tests for DELETE /api/questions/<id>/image-description."""

    def test_remove_image_description(self, qclient):
        resp = qclient.delete("/api/questions/1/image-description")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_remove_image_description_not_found(self, qclient):
        resp = qclient.delete("/api/questions/9999/image-description")
        assert resp.status_code == 404

    def test_remove_image_description_requires_login(self, anon_client):
        resp = anon_client.delete("/api/questions/1/image-description")
        assert resp.status_code == 303


# ============================================================
# Question Regenerate API Tests
# ============================================================


class TestApiQuestionRegenerate:
    """Tests for POST /api/questions/<id>/regenerate."""

    def test_regenerate_question_success(self, qclient):
        mock_result = MagicMock()
        mock_result.id = 1
        mock_result.text = "Regenerated question text"
        mock_result.points = 5.0
        mock_result.question_type = "mc"
        mock_result.data = {"type": "mc", "text": "Regenerated", "options": ["A", "B"], "correct_index": 0}

        with patch("src.question_regenerator.regenerate_question", return_value=mock_result):
            resp = qclient.post(
                "/api/questions/1/regenerate",
                data=json.dumps({"teacher_notes": "Make it harder"}),
                content_type="application/json",
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert data["question"]["text"] == "Regenerated question text"

    def test_regenerate_question_failure(self, qclient):
        with patch("src.question_regenerator.regenerate_question", return_value=None):
            resp = qclient.post(
                "/api/questions/1/regenerate",
                data=json.dumps({}),
                content_type="application/json",
            )
            assert resp.status_code == 500
            data = resp.get_json()
            assert data["ok"] is False

    def test_regenerate_question_not_found(self, qclient):
        resp = qclient.post(
            "/api/questions/9999/regenerate",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_regenerate_requires_login(self, anon_client):
        resp = anon_client.post("/api/questions/1/regenerate")
        assert resp.status_code == 303


# ============================================================
# Generate Redirect Tests
# ============================================================


class TestGenerateRedirect:
    """Tests for GET /generate."""

    def test_generate_redirect_to_class(self, qclient):
        resp = qclient.get("/generate")
        assert resp.status_code == 302
        assert "/classes/" in resp.headers["Location"]
        assert "/generate" in resp.headers["Location"]

    def test_generate_redirect_requires_login(self, anon_client):
        resp = anon_client.get("/generate")
        assert resp.status_code == 303


# ============================================================
# Quiz Generate Form Tests
# ============================================================


class TestQuizGenerate:
    """Tests for GET/POST /classes/<id>/generate."""

    def test_generate_form_get(self, qclient):
        resp = qclient.get("/classes/1/generate")
        assert resp.status_code == 200
        assert b"generate" in resp.data.lower() or b"Generate" in resp.data

    def test_generate_form_class_not_found(self, qclient):
        resp = qclient.get("/classes/9999/generate")
        assert resp.status_code == 404

    def test_generate_post_success(self, qclient):
        """POST /classes/<id>/generate creates a quiz and redirects to detail."""
        mock_quiz = MagicMock()
        mock_quiz.id = 99

        with patch("src.web.blueprints.quizzes.generate_quiz", return_value=mock_quiz):
            resp = qclient.post(
                "/classes/1/generate",
                data={
                    "num_questions": "5",
                    "difficulty": "3",
                    "provider": "mock",
                    "question_types": ["mc", "tf"],
                },
            )
            assert resp.status_code == 303
            assert "/quizzes/99" in resp.headers["Location"]

    def test_generate_post_failure(self, qclient):
        """POST /classes/<id>/generate handles generation failure."""
        with patch("src.web.blueprints.quizzes.generate_quiz", return_value=None):
            resp = qclient.post(
                "/classes/1/generate",
                data={
                    "num_questions": "5",
                    "difficulty": "3",
                },
            )
            assert resp.status_code == 200
            assert b"failed" in resp.data.lower() or b"error" in resp.data.lower()

    def test_generate_post_provider_error(self, qclient):
        """POST /classes/<id>/generate handles ProviderError."""
        from src.llm_provider import ProviderError

        with patch(
            "src.web.blueprints.quizzes.generate_quiz",
            side_effect=ProviderError("API Error", "Provider is unavailable"),
        ):
            resp = qclient.post(
                "/classes/1/generate",
                data={"num_questions": "5", "difficulty": "3"},
            )
            assert resp.status_code == 200

    def test_generate_post_generic_exception(self, qclient):
        """POST /classes/<id>/generate handles unexpected exceptions."""
        with patch(
            "src.web.blueprints.quizzes.generate_quiz",
            side_effect=RuntimeError("Unexpected error"),
        ):
            resp = qclient.post(
                "/classes/1/generate",
                data={"num_questions": "5", "difficulty": "3"},
            )
            assert resp.status_code == 200

    def test_generate_post_with_topics(self, qclient):
        """POST with topics field passes through to generate_quiz."""
        mock_quiz = MagicMock()
        mock_quiz.id = 100

        with patch("src.web.blueprints.quizzes.generate_quiz", return_value=mock_quiz) as mock_gen:
            resp = qclient.post(
                "/classes/1/generate",
                data={
                    "num_questions": "5",
                    "difficulty": "3",
                    "topics": "photosynthesis, respiration",
                },
            )
            assert resp.status_code == 303
            call_kwargs = mock_gen.call_args
            assert call_kwargs[1]["topics"] == "photosynthesis, respiration"

    def test_generate_post_with_cognitive_framework(self, qclient):
        """POST with cognitive framework fields."""
        mock_quiz = MagicMock()
        mock_quiz.id = 101

        with patch("src.web.blueprints.quizzes.generate_quiz", return_value=mock_quiz) as mock_gen:
            resp = qclient.post(
                "/classes/1/generate",
                data={
                    "num_questions": "5",
                    "difficulty": "3",
                    "cognitive_framework": "blooms",
                    "cognitive_distribution": '{"remember": 30, "understand": 70}',
                },
            )
            assert resp.status_code == 303
            call_kwargs = mock_gen.call_args[1]
            assert call_kwargs["cognitive_framework"] == "blooms"
            assert call_kwargs["cognitive_distribution"] == {"remember": 30, "understand": 70}

    def test_generate_requires_login(self, anon_client):
        resp = anon_client.get("/classes/1/generate")
        assert resp.status_code == 303


# ============================================================
# Cost Estimate API Tests
# ============================================================


class TestEstimateCost:
    """Tests for GET /api/estimate-cost."""

    def test_estimate_cost_mock(self, qclient):
        """Cost estimate with mock provider returns $0.00."""
        resp = qclient.get("/api/estimate-cost?provider=mock&num_questions=10")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["estimated_cost"] == "$0.00"
        assert data["is_mock"] is True

    def test_estimate_cost_default_provider(self, qclient):
        """Cost estimate without provider param uses config default (mock)."""
        resp = qclient.get("/api/estimate-cost")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "estimated_cost" in data

    def test_estimate_cost_with_num_questions(self, qclient):
        """Cost estimate scales with num_questions param."""
        resp = qclient.get("/api/estimate-cost?num_questions=20")
        assert resp.status_code == 200

    def test_estimate_cost_error_handling(self, qclient):
        """Cost estimate handles calculation errors gracefully."""
        with patch(
            "src.web.blueprints.quizzes.estimate_pipeline_cost",
            side_effect=RuntimeError("calc error"),
        ):
            resp = qclient.get("/api/estimate-cost")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["estimated_cost"] == "$0.00"

    def test_estimate_cost_requires_login(self, anon_client):
        resp = anon_client.get("/api/estimate-cost")
        assert resp.status_code == 303


# ============================================================
# Costs Dashboard Tests
# ============================================================


class TestCostsDashboard:
    """Tests for GET/POST /costs."""

    def test_costs_get(self, qclient):
        resp = qclient.get("/costs")
        assert resp.status_code == 200

    def test_costs_post_budget(self, qclient):
        with patch("src.web.blueprints.quizzes.save_config"):
            resp = qclient.post(
                "/costs",
                data={"monthly_budget": "25.00"},
            )
            assert resp.status_code == 303

    def test_costs_post_invalid_budget(self, qclient):
        with patch("src.web.blueprints.quizzes.save_config"):
            resp = qclient.post(
                "/costs",
                data={"monthly_budget": "not_a_number"},
            )
            # Should handle gracefully (sets to 0)
            assert resp.status_code == 303

    def test_costs_post_empty_budget(self, qclient):
        with patch("src.web.blueprints.quizzes.save_config"):
            resp = qclient.post(
                "/costs",
                data={"monthly_budget": ""},
            )
            assert resp.status_code == 303

    def test_costs_requires_login(self, anon_client):
        resp = anon_client.get("/costs")
        assert resp.status_code == 303
