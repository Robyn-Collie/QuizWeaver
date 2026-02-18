"""Tests for image search links, Pixabay API search, and image-from-URL endpoints."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session


@pytest.fixture
def app_with_image_question():
    """Flask app with a question that has image_description in its data."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

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
        title="Image Test Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "7th Grade"}),
    )
    session.add(quiz)
    session.commit()

    q1 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q1",
        text="What organelle does photosynthesis?",
        points=2.0,
        data=json.dumps(
            {
                "type": "mc",
                "options": ["Chloroplast", "Nucleus", "Ribosome", "Golgi"],
                "correct_index": 0,
                "image_description": "diagram of a chloroplast",
            }
        ),
    )
    q2 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q2",
        text="What is mitosis?",
        points=2.0,
        data=json.dumps(
            {
                "type": "mc",
                "options": ["Cell division", "Cell death", "Cell growth", "Cell repair"],
                "correct_index": 0,
            }
        ),
    )
    session.add(q1)
    session.add(q2)
    session.commit()

    quiz_id = quiz.id
    q1_id = q1.id
    q2_id = q2.id

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path, "upload_dir": tempfile.mkdtemp()},
        "llm": {"provider": "mock"},
        "generation": {
            "default_grade_level": "7th Grade Science",
            "quiz_title": "Test",
            "sol_standards": [],
            "target_image_ratio": 0.0,
            "generate_ai_images": False,
            "interactive_review": False,
        },
    }
    app = create_app(test_config)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    app.config["_test_ids"] = {
        "quiz_id": quiz_id,
        "q1_id": q1_id,
        "q2_id": q2_id,
    }

    yield app

    app.config["DB_ENGINE"].dispose()
    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app_with_image_question):
    """Logged-in test client."""
    with app_with_image_question.test_client() as c:
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        c._app = app_with_image_question
        yield c


@pytest.fixture
def anon_client(app_with_image_question):
    """Unauthenticated test client."""
    with app_with_image_question.test_client() as c:
        c._app = app_with_image_question
        yield c


# ---------------------------------------------------------------------------
# PART 1: Search links in HTML
# ---------------------------------------------------------------------------


class TestSearchLinksInTemplate:
    """Verify that image search links appear when image_description exists."""

    def test_search_links_appear_for_image_description(self, client):
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/quizzes/{ids['quiz_id']}?skip_onboarding=1")
        html = resp.data.decode()
        assert resp.status_code == 200
        assert "Pixabay" in html
        assert "Wikimedia" in html
        assert "image-search-link" in html
        assert "diagram of a chloroplast" in html

    def test_search_links_absent_without_image_description(self, client):
        """Q2 has no image_description, so no search links for that question."""
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/quizzes/{ids['quiz_id']}?skip_onboarding=1")
        html = resp.data.decode()
        # Q2 section should not have search links
        # We verify by checking the Search button exists (it's on all questions)
        # but only Q1 has the actual Pixabay/Wikimedia links in image-placeholder
        assert html.count("image-search-links") == 1  # only Q1

    def test_search_button_on_all_questions(self, client):
        """The 'Search' button appears on all question cards."""
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/quizzes/{ids['quiz_id']}?skip_onboarding=1")
        html = resp.data.decode()
        # 2 buttons in question cards + 1 reference in JS event handler
        assert html.count("btn-search-image") >= 2


# ---------------------------------------------------------------------------
# PART 2: /api/image-search endpoint
# ---------------------------------------------------------------------------


class TestImageSearchAPI:
    """Tests for the Pixabay image search API endpoint."""

    def test_requires_login(self, anon_client):
        resp = anon_client.get("/api/image-search?q=cat")
        assert resp.status_code == 303

    def test_no_api_key_returns_helpful_error(self, client):
        with patch.dict(os.environ, {}, clear=False):
            # Ensure PIXABAY_API_KEY is not set
            os.environ.pop("PIXABAY_API_KEY", None)
            resp = client.get("/api/image-search?q=chloroplast")
            data = resp.get_json()
            assert data["ok"] is False
            assert "PIXABAY_API_KEY" in data["error"]

    def test_empty_query_returns_error(self, client):
        with patch.dict(os.environ, {"PIXABAY_API_KEY": "test-key-123"}):
            resp = client.get("/api/image-search?q=")
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["ok"] is False

    def test_successful_search_with_mock_api(self, client):
        fake_pixabay_response = {
            "totalHits": 2,
            "hits": [
                {
                    "id": 101,
                    "previewURL": "https://cdn.pixabay.com/photo/preview/101.jpg",
                    "webformatURL": "https://pixabay.com/get/101_640.jpg",
                    "tags": "chloroplast, cell, biology",
                    "pageURL": "https://pixabay.com/photos/chloroplast-101/",
                    "webformatWidth": 640,
                    "webformatHeight": 480,
                },
                {
                    "id": 102,
                    "previewURL": "https://cdn.pixabay.com/photo/preview/102.jpg",
                    "webformatURL": "https://pixabay.com/get/102_640.jpg",
                    "tags": "plant, green",
                    "pageURL": "https://pixabay.com/photos/plant-102/",
                    "webformatWidth": 640,
                    "webformatHeight": 480,
                },
            ],
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_pixabay_response
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"PIXABAY_API_KEY": "test-key-123"}):
            with patch("requests.get", return_value=mock_resp) as mock_get:
                resp = client.get("/api/image-search?q=chloroplast&type=illustration")
                data = resp.get_json()
                assert data["ok"] is True
                assert len(data["hits"]) == 2
                assert data["hits"][0]["id"] == 101
                assert data["hits"][0]["thumbnail"] == "https://cdn.pixabay.com/photo/preview/101.jpg"
                assert data["hits"][0]["tags"] == "chloroplast, cell, biology"
                # Verify the API was called with correct params
                mock_get.assert_called_once()
                call_kwargs = mock_get.call_args
                assert call_kwargs[1]["params"]["q"] == "chloroplast"
                assert call_kwargs[1]["params"]["safesearch"] == "true"

    def test_api_error_returns_502(self, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("Connection error")

        with patch.dict(os.environ, {"PIXABAY_API_KEY": "test-key-123"}):
            with patch("requests.get", side_effect=Exception("timeout")):
                resp = client.get("/api/image-search?q=test")
                assert resp.status_code == 502
                data = resp.get_json()
                assert data["ok"] is False


# ---------------------------------------------------------------------------
# PART 3: /api/questions/<id>/image-from-url endpoint
# ---------------------------------------------------------------------------


class TestImageFromURL:
    """Tests for downloading an image from URL and attaching to a question."""

    def test_requires_login(self, anon_client):
        resp = anon_client.post(
            "/api/questions/1/image-from-url",
            data=json.dumps({"url": "https://example.com/img.jpg"}),
            content_type="application/json",
        )
        assert resp.status_code == 303

    def test_question_not_found(self, client):
        resp = client.post(
            "/api/questions/99999/image-from-url",
            data=json.dumps({"url": "https://example.com/img.jpg"}),
            content_type="application/json",
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["ok"] is False

    def test_missing_url(self, client):
        ids = client._app.config["_test_ids"]
        resp = client.post(
            f"/api/questions/{ids['q1_id']}/image-from-url",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_rejects_non_image_content_type(self, client):
        ids = client._app.config["_test_ids"]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/html", "Content-Length": "1000"}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            resp = client.post(
                f"/api/questions/{ids['q1_id']}/image-from-url",
                data=json.dumps({"url": "https://example.com/page.html"}),
                content_type="application/json",
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert "not point to an image" in data["error"]

    def test_successful_image_download(self, client):
        ids = client._app.config["_test_ids"]
        # Create a fake image response (1x1 PNG)
        fake_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "image/png", "Content-Length": str(len(fake_png))}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content = MagicMock(return_value=[fake_png])

        with patch("requests.get", return_value=mock_resp):
            resp = client.post(
                f"/api/questions/{ids['q1_id']}/image-from-url",
                data=json.dumps({"url": "https://pixabay.com/get/image_640.png"}),
                content_type="application/json",
            )
            data = resp.get_json()
            assert data["ok"] is True
            assert data["image_ref"].endswith(".png")
            assert data["url"].startswith("/uploads/images/")

    def test_download_failure_returns_400(self, client):
        ids = client._app.config["_test_ids"]
        with patch("requests.get", side_effect=Exception("Connection refused")):
            resp = client.post(
                f"/api/questions/{ids['q1_id']}/image-from-url",
                data=json.dumps({"url": "https://example.com/broken.jpg"}),
                content_type="application/json",
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["ok"] is False
