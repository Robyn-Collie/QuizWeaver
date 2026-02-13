"""
Tests for quiz editing API endpoints.

Covers: title editing, question editing, deletion, reorder,
image upload/remove, and question regeneration.
"""

import io
import json
import os
import tempfile

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database and seed data."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed class
    cls = Class(
        name="Test Class",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    # Seed quiz
    quiz = Quiz(
        title="Test Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps(
            {
                "grade_level": "7th Grade",
                "provider": "mock",
            }
        ),
    )
    session.add(quiz)
    session.commit()

    # Seed questions
    q1 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q1",
        text="What is photosynthesis?",
        points=5.0,
        sort_order=0,
        data=json.dumps(
            {
                "type": "mc",
                "text": "What is photosynthesis?",
                "options": ["A process", "A thing", "A place", "A person"],
                "correct_index": 0,
                "correct_answer": "A process",
            }
        ),
    )
    q2 = Question(
        quiz_id=quiz.id,
        question_type="tf",
        title="Q2",
        text="The sun is a star.",
        points=2.0,
        sort_order=1,
        data=json.dumps(
            {
                "type": "tf",
                "text": "The sun is a star.",
                "correct_answer": "True",
            }
        ),
    )
    q3 = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q3",
        text="What is mitosis?",
        points=3.0,
        sort_order=2,
        data=json.dumps(
            {
                "type": "mc",
                "text": "What is mitosis?",
                "options": ["Cell division", "Respiration", "Digestion"],
                "correct_index": 0,
                "image_ref": "existing_image.png",
            }
        ),
    )
    session.add_all([q1, q2, q3])
    session.commit()

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {
            "database_file": db_path,
            "generated_images_dir": tempfile.mkdtemp(),
        },
        "llm": {"provider": "mock", "max_calls_per_session": 50, "max_cost_per_session": 5.00},
        "generation": {"default_grade_level": "7th Grade Science"},
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
# Quiz Title Editing
# ============================================================


class TestQuizTitleEdit:
    def test_edit_title_success(self, client):
        resp = client.put(
            "/api/quizzes/1/title",
            json={"title": "Updated Quiz Title"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["title"] == "Updated Quiz Title"

    def test_edit_title_empty_rejected(self, client):
        resp = client.put("/api/quizzes/1/title", json={"title": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_edit_title_whitespace_rejected(self, client):
        resp = client.put("/api/quizzes/1/title", json={"title": "   "})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_edit_title_404(self, client):
        resp = client.put("/api/quizzes/999/title", json={"title": "Nope"})
        assert resp.status_code == 404

    def test_edit_title_auth_required(self, anon_client):
        resp = anon_client.put(
            "/api/quizzes/1/title",
            json={"title": "Hacked"},
        )
        # Should redirect to login
        assert resp.status_code == 303


# ============================================================
# Question Editing
# ============================================================


class TestQuestionEdit:
    def test_edit_text(self, client):
        resp = client.put(
            "/api/questions/1",
            json={"text": "Updated question text?"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["question"]["text"] == "Updated question text?"

    def test_edit_points(self, client):
        resp = client.put("/api/questions/1", json={"points": 10})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["question"]["points"] == 10.0

    def test_edit_options(self, client):
        resp = client.put(
            "/api/questions/1",
            json={"options": ["New A", "New B", "New C"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["question"]["data"]["options"] == ["New A", "New B", "New C"]

    def test_edit_correct_answer(self, client):
        resp = client.put(
            "/api/questions/1",
            json={"correct_index": 2, "correct_answer": "A place"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["question"]["data"]["correct_index"] == 2

    def test_edit_type_change(self, client):
        resp = client.put("/api/questions/1", json={"question_type": "tf"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["question"]["question_type"] == "tf"
        assert data["question"]["data"]["type"] == "tf"

    def test_edit_tf_question(self, client):
        resp = client.put(
            "/api/questions/2",
            json={"text": "Is the moon a planet?", "correct_answer": "False"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["question"]["text"] == "Is the moon a planet?"
        assert data["question"]["data"]["correct_answer"] == "False"

    def test_edit_empty_text_rejected(self, client):
        resp = client.put("/api/questions/1", json={"text": ""})
        assert resp.status_code == 400

    def test_edit_404(self, client):
        resp = client.put("/api/questions/999", json={"text": "Nope"})
        assert resp.status_code == 404

    def test_edit_preserves_other_data(self, client):
        """Editing text should not remove existing options."""
        resp = client.put(
            "/api/questions/1",
            json={"text": "New text only"},
        )
        data = resp.get_json()
        # Options should still be present from the original data
        assert "options" in data["question"]["data"]


# ============================================================
# Question Deletion
# ============================================================


class TestQuestionDelete:
    def test_delete_success(self, client):
        resp = client.delete("/api/questions/2")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

        # Verify it's actually gone
        resp2 = client.delete("/api/questions/2")
        assert resp2.status_code == 404

    def test_delete_404(self, client):
        resp = client.delete("/api/questions/999")
        assert resp.status_code == 404

    def test_delete_removes_from_db(self, client, app):
        client.delete("/api/questions/1")
        with app.app_context():
            from src.database import get_session as gs

            session = gs(app.config["DB_ENGINE"])
            q = session.query(Question).filter_by(id=1).first()
            assert q is None
            session.close()


# ============================================================
# Question Reorder
# ============================================================


class TestQuestionReorder:
    def test_reorder_success(self, client):
        # Reverse the order: 3, 2, 1
        resp = client.put(
            "/api/quizzes/1/reorder",
            json={"question_ids": [3, 2, 1]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_reorder_invalid_ids(self, client):
        resp = client.put(
            "/api/quizzes/1/reorder",
            json={"question_ids": [1, 2, 999]},
        )
        assert resp.status_code == 400

    def test_reorder_partial_list(self, client):
        """Missing an ID should fail."""
        resp = client.put(
            "/api/quizzes/1/reorder",
            json={"question_ids": [1, 2]},
        )
        assert resp.status_code == 400

    def test_reorder_quiz_404(self, client):
        resp = client.put(
            "/api/quizzes/999/reorder",
            json={"question_ids": [1]},
        )
        assert resp.status_code == 404


# ============================================================
# Image Upload
# ============================================================


class TestImageUpload:
    def test_upload_success(self, client):
        data = {
            "image": (io.BytesIO(b"fake png data"), "test_image.png"),
        }
        resp = client.post(
            "/api/questions/1/image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["ok"] is True
        assert "upload_1_" in result["image_ref"]
        assert result["image_ref"].endswith(".png")

    def test_upload_wrong_extension(self, client):
        data = {
            "image": (io.BytesIO(b"not an image"), "malicious.exe"),
        }
        resp = client.post(
            "/api/questions/1/image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_no_file(self, client):
        resp = client.post(
            "/api/questions/1/image",
            data={},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_updates_data_json(self, client):
        data = {
            "image": (io.BytesIO(b"fake"), "photo.jpg"),
        }
        resp = client.post(
            "/api/questions/1/image",
            data=data,
            content_type="multipart/form-data",
        )
        result = resp.get_json()
        assert result["ok"] is True

        # Verify via question edit endpoint
        resp2 = client.put("/api/questions/1", json={"points": 5})
        q_data = resp2.get_json()["question"]["data"]
        assert "image_ref" in q_data

    def test_upload_question_404(self, client):
        data = {
            "image": (io.BytesIO(b"fake"), "photo.jpg"),
        }
        resp = client.post(
            "/api/questions/999/image",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404


# ============================================================
# Image Remove
# ============================================================


class TestImageRemove:
    def test_remove_success(self, client):
        # Question 3 has an image_ref
        resp = client.delete("/api/questions/3/image")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_remove_clears_data(self, client):
        client.delete("/api/questions/3/image")
        # Verify image_ref is gone
        resp = client.put("/api/questions/3", json={"points": 3})
        q_data = resp.get_json()["question"]["data"]
        assert "image_ref" not in q_data

    def test_remove_question_404(self, client):
        resp = client.delete("/api/questions/999/image")
        assert resp.status_code == 404


# ============================================================
# Question Regeneration
# ============================================================


class TestQuestionRegenerate:
    def test_regenerate_success(self, client):
        resp = client.post(
            "/api/questions/1/regenerate",
            json={"teacher_notes": ""},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "question" in data
        assert data["question"]["id"] == 1

    def test_regenerate_with_notes(self, client):
        resp = client.post(
            "/api/questions/1/regenerate",
            json={"teacher_notes": "Make it about cellular respiration"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        # The mock provider will return a question (text should exist)
        assert data["question"]["text"]

    def test_regenerate_preserves_quiz_id(self, client, app):
        client.post(
            "/api/questions/1/regenerate",
            json={"teacher_notes": ""},
        )
        with app.app_context():
            session = get_session(app.config["DB_ENGINE"])
            q = session.query(Question).filter_by(id=1).first()
            assert q is not None
            assert q.quiz_id == 1
            session.close()

    def test_regenerate_404(self, client):
        resp = client.post(
            "/api/questions/999/regenerate",
            json={"teacher_notes": ""},
        )
        assert resp.status_code == 404
