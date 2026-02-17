"""
Tests for the classes blueprint (src/web/blueprints/classes.py).

Covers all 8 routes:
  - GET  /classes                              (classes_list)
  - GET  /classes/new                          (class_create GET)
  - POST /classes/new                          (class_create POST)
  - GET  /classes/<id>                         (class_detail)
  - GET  /classes/<id>/edit                    (class_edit GET)
  - POST /classes/<id>/edit                    (class_edit POST)
  - POST /classes/<id>/delete                  (class_delete_route)
  - GET  /classes/<id>/lessons                 (lessons_list)
  - GET  /classes/<id>/lessons/new             (lesson_log GET)
  - POST /classes/<id>/lessons/new             (lesson_log POST)
  - POST /classes/<id>/lessons/<lid>/delete    (lesson_delete_route)
"""

from src.database import Class, LessonLog

# ============================================================
# Class List
# ============================================================


class TestClassesList:
    """Tests for GET /classes."""

    def test_classes_list_returns_200(self, flask_client):
        resp = flask_client.get("/classes")
        assert resp.status_code == 200

    def test_classes_list_shows_seeded_classes(self, flask_client):
        resp = flask_client.get("/classes")
        assert b"Test Class" in resp.data
        assert b"Empty Class" in resp.data

    def test_classes_list_requires_login(self, anon_flask_client):
        resp = anon_flask_client.get("/classes")
        assert resp.status_code == 303


# ============================================================
# Class Create
# ============================================================


class TestClassCreate:
    """Tests for GET/POST /classes/new."""

    def test_class_create_get_returns_200(self, flask_client):
        resp = flask_client.get("/classes/new")
        assert resp.status_code == 200

    def test_class_create_post_redirects(self, flask_client):
        resp = flask_client.post(
            "/classes/new",
            data={"name": "New Class", "grade_level": "9th Grade", "subject": "History"},
        )
        assert resp.status_code == 303
        assert "/classes" in resp.headers["Location"]

    def test_class_create_post_creates_class(self, flask_client, flask_app):
        flask_client.post(
            "/classes/new",
            data={"name": "Created Class", "grade_level": "10th", "subject": "English"},
        )
        with flask_app.app_context():
            from src.web.blueprints.helpers import _get_session

            session = _get_session()
            cls = session.query(Class).filter_by(name="Created Class").first()
            assert cls is not None
            assert cls.grade_level == "10th"
            assert cls.subject == "English"

    def test_class_create_post_with_standards(self, flask_client, flask_app):
        flask_client.post(
            "/classes/new",
            data={
                "name": "Standards Class",
                "grade_level": "8th",
                "subject": "Science",
                "standards": "SOL 8.1, SOL 8.2",
            },
        )
        with flask_app.app_context():
            from src.web.blueprints.helpers import _get_session

            session = _get_session()
            cls = session.query(Class).filter_by(name="Standards Class").first()
            assert cls is not None

    def test_class_create_post_empty_name_returns_400(self, flask_client):
        resp = flask_client.post(
            "/classes/new",
            data={"name": "", "grade_level": "8th", "subject": "Math"},
        )
        assert resp.status_code == 400
        assert b"Class name is required" in resp.data

    def test_class_create_requires_login(self, anon_flask_client):
        resp = anon_flask_client.get("/classes/new")
        assert resp.status_code == 303


# ============================================================
# Class Detail
# ============================================================


class TestClassDetail:
    """Tests for GET /classes/<id>."""

    def test_class_detail_returns_200(self, flask_client):
        resp = flask_client.get("/classes/1")
        assert resp.status_code == 200
        assert b"Test Class" in resp.data

    def test_class_detail_shows_action_links(self, flask_client):
        resp = flask_client.get("/classes/1")
        assert b"View Lessons" in resp.data
        assert b"Generate Quiz" in resp.data
        assert b"Edit Class" in resp.data

    def test_class_detail_nonexistent_returns_404(self, flask_client):
        resp = flask_client.get("/classes/9999")
        assert resp.status_code == 404

    def test_class_detail_requires_login(self, anon_flask_client):
        resp = anon_flask_client.get("/classes/1")
        assert resp.status_code == 303


# ============================================================
# Class Edit
# ============================================================


class TestClassEdit:
    """Tests for GET/POST /classes/<id>/edit."""

    def test_class_edit_get_returns_200(self, flask_client):
        resp = flask_client.get("/classes/1/edit")
        assert resp.status_code == 200

    def test_class_edit_post_redirects(self, flask_client):
        resp = flask_client.post(
            "/classes/1/edit",
            data={"name": "Updated Name", "grade_level": "9th", "subject": "English"},
        )
        assert resp.status_code == 303
        assert "/classes/1" in resp.headers["Location"]

    def test_class_edit_post_updates_class(self, flask_client, flask_app):
        flask_client.post(
            "/classes/1/edit",
            data={"name": "Renamed Class", "grade_level": "9th", "subject": "English"},
        )
        with flask_app.app_context():
            from src.web.blueprints.helpers import _get_session

            session = _get_session()
            cls = session.query(Class).filter_by(id=1).first()
            assert cls.name == "Renamed Class"

    def test_class_edit_post_with_standards(self, flask_client):
        resp = flask_client.post(
            "/classes/1/edit",
            data={
                "name": "Edited Class",
                "grade_level": "8th",
                "subject": "Science",
                "standards": "SOL 8.3, SOL 8.4",
            },
        )
        assert resp.status_code == 303

    def test_class_edit_nonexistent_returns_404(self, flask_client):
        resp = flask_client.get("/classes/9999/edit")
        assert resp.status_code == 404

    def test_class_edit_post_nonexistent_returns_404(self, flask_client):
        resp = flask_client.post(
            "/classes/9999/edit",
            data={"name": "Nope"},
        )
        assert resp.status_code == 404

    def test_class_edit_requires_login(self, anon_flask_client):
        resp = anon_flask_client.get("/classes/1/edit")
        assert resp.status_code == 303


# ============================================================
# Class Delete
# ============================================================


class TestClassDelete:
    """Tests for POST /classes/<id>/delete."""

    def test_class_delete_redirects(self, flask_client):
        resp = flask_client.post("/classes/2/delete")
        assert resp.status_code == 303
        assert "/classes" in resp.headers["Location"]

    def test_class_delete_nonexistent_returns_404(self, flask_client):
        resp = flask_client.post("/classes/9999/delete")
        assert resp.status_code == 404

    def test_class_delete_requires_login(self, anon_flask_client):
        resp = anon_flask_client.post("/classes/1/delete")
        assert resp.status_code == 303


# ============================================================
# Lessons List
# ============================================================


class TestLessonsList:
    """Tests for GET /classes/<id>/lessons."""

    def test_lessons_list_returns_200(self, flask_client):
        resp = flask_client.get("/classes/1/lessons")
        assert resp.status_code == 200

    def test_lessons_list_nonexistent_class_returns_404(self, flask_client):
        resp = flask_client.get("/classes/9999/lessons")
        assert resp.status_code == 404

    def test_lessons_list_requires_login(self, anon_flask_client):
        resp = anon_flask_client.get("/classes/1/lessons")
        assert resp.status_code == 303

    def test_lessons_list_shows_logged_lessons(self, flask_client):
        # Log a lesson first
        flask_client.post(
            "/classes/1/lessons/new",
            data={
                "content": "Photosynthesis overview",
                "topics": "photosynthesis, plants",
                "notes": "Good class",
            },
        )
        resp = flask_client.get("/classes/1/lessons")
        assert resp.status_code == 200
        assert b"Photosynthesis overview" in resp.data or b"photosynthesis" in resp.data


# ============================================================
# Lesson Log (Create)
# ============================================================


class TestLessonLog:
    """Tests for GET/POST /classes/<id>/lessons/new."""

    def test_lesson_log_get_returns_200(self, flask_client):
        resp = flask_client.get("/classes/1/lessons/new")
        assert resp.status_code == 200

    def test_lesson_log_post_redirects(self, flask_client):
        resp = flask_client.post(
            "/classes/1/lessons/new",
            data={
                "content": "Cell division lesson",
                "topics": "mitosis, meiosis",
                "notes": "Students engaged",
            },
        )
        assert resp.status_code == 303
        assert "/classes/1/lessons" in resp.headers["Location"]

    def test_lesson_log_post_creates_lesson(self, flask_client, flask_app):
        flask_client.post(
            "/classes/1/lessons/new",
            data={
                "content": "Unique lesson content for test",
                "topics": "gravity, motion",
                "notes": "",
            },
        )
        with flask_app.app_context():
            from src.web.blueprints.helpers import _get_session

            session = _get_session()
            lesson = session.query(LessonLog).filter(LessonLog.content == "Unique lesson content for test").first()
            assert lesson is not None
            assert lesson.class_id == 1

    def test_lesson_log_nonexistent_class_returns_404(self, flask_client):
        resp = flask_client.get("/classes/9999/lessons/new")
        assert resp.status_code == 404

    def test_lesson_log_post_nonexistent_class_returns_404(self, flask_client):
        resp = flask_client.post(
            "/classes/9999/lessons/new",
            data={"content": "Test", "topics": "t1"},
        )
        assert resp.status_code == 404

    def test_lesson_log_requires_login(self, anon_flask_client):
        resp = anon_flask_client.get("/classes/1/lessons/new")
        assert resp.status_code == 303


# ============================================================
# Lesson Delete
# ============================================================


class TestLessonDelete:
    """Tests for POST /classes/<id>/lessons/<lid>/delete."""

    def test_lesson_delete_redirects(self, flask_client, flask_app):
        # Create a lesson to delete
        flask_client.post(
            "/classes/1/lessons/new",
            data={"content": "Lesson to delete", "topics": "topic1"},
        )
        # Find the lesson ID
        with flask_app.app_context():
            from src.web.blueprints.helpers import _get_session

            session = _get_session()
            lesson = session.query(LessonLog).filter(LessonLog.content == "Lesson to delete").first()
            lesson_id = lesson.id

        resp = flask_client.post(f"/classes/1/lessons/{lesson_id}/delete")
        assert resp.status_code == 303
        assert "/classes/1/lessons" in resp.headers["Location"]

    def test_lesson_delete_nonexistent_class_returns_404(self, flask_client):
        resp = flask_client.post("/classes/9999/lessons/1/delete")
        assert resp.status_code == 404

    def test_lesson_delete_nonexistent_lesson_returns_404(self, flask_client):
        resp = flask_client.post("/classes/1/lessons/9999/delete")
        assert resp.status_code == 404

    def test_lesson_delete_requires_login(self, anon_flask_client):
        resp = anon_flask_client.post("/classes/1/lessons/1/delete")
        assert resp.status_code == 303
