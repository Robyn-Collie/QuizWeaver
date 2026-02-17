"""
Tests for the main blueprint (src/web/blueprints/main.py).

Covers all 5 routes:
  - GET  /                   (index -- redirect to dashboard)
  - GET  /dashboard          (dashboard)
  - GET  /api/stats          (api_stats)
  - GET  /onboarding         (onboarding GET)
  - POST /onboarding         (onboarding POST)
  - GET  /help               (help_page)
"""

from src.database import Class

# ============================================================
# Index Redirect
# ============================================================


class TestIndex:
    """Tests for GET / -> redirect to /dashboard."""

    def test_index_redirects_to_dashboard(self, flask_client):
        resp = flask_client.get("/")
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]

    def test_index_requires_login(self, anon_flask_client):
        resp = anon_flask_client.get("/")
        assert resp.status_code == 303


# ============================================================
# Dashboard
# ============================================================


class TestDashboard:
    """Tests for GET /dashboard."""

    def test_dashboard_returns_200(self, flask_client):
        resp = flask_client.get("/dashboard?skip_onboarding=1")
        assert resp.status_code == 200

    def test_dashboard_shows_classes(self, flask_client):
        resp = flask_client.get("/dashboard?skip_onboarding=1")
        assert b"Test Class" in resp.data

    def test_dashboard_shows_recent_quizzes(self, flask_client):
        resp = flask_client.get("/dashboard?skip_onboarding=1")
        assert b"Test Quiz" in resp.data

    def test_dashboard_requires_login(self, anon_flask_client):
        resp = anon_flask_client.get("/dashboard")
        assert resp.status_code == 303

    def test_dashboard_redirects_to_onboarding_when_no_classes(self, make_flask_app):
        """First-time user with no classes gets redirected to onboarding."""
        app = make_flask_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["username"] = "teacher"
            resp = client.get("/dashboard")
            assert resp.status_code == 302
            assert "/onboarding" in resp.headers["Location"]

    def test_dashboard_skip_onboarding_param(self, make_flask_app):
        """skip_onboarding=1 prevents redirect even with no classes."""
        app = make_flask_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["username"] = "teacher"
            resp = client.get("/dashboard?skip_onboarding=1")
            assert resp.status_code == 200


# ============================================================
# API Stats
# ============================================================


class TestApiStats:
    """Tests for GET /api/stats."""

    def test_api_stats_returns_json(self, flask_client):
        resp = flask_client.get("/api/stats")
        assert resp.status_code == 200
        assert resp.content_type == "application/json"

    def test_api_stats_has_expected_keys(self, flask_client):
        resp = flask_client.get("/api/stats")
        data = resp.get_json()
        assert "lessons_by_date" in data
        assert "quizzes_by_class" in data

    def test_api_stats_quizzes_by_class_includes_classes(self, flask_client):
        resp = flask_client.get("/api/stats")
        data = resp.get_json()
        class_names = [entry["class_name"] for entry in data["quizzes_by_class"]]
        assert "Test Class" in class_names

    def test_api_stats_requires_login(self, anon_flask_client):
        resp = anon_flask_client.get("/api/stats")
        assert resp.status_code == 303


# ============================================================
# Onboarding
# ============================================================


class TestOnboarding:
    """Tests for GET/POST /onboarding."""

    def test_onboarding_get_returns_200(self, flask_client):
        resp = flask_client.get("/onboarding")
        assert resp.status_code == 200

    def test_onboarding_post_with_class_data_redirects(self, flask_client):
        resp = flask_client.post(
            "/onboarding",
            data={
                "class_name": "My First Class",
                "grade_level": "7th Grade",
                "subject": "Science",
            },
        )
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]

    def test_onboarding_post_creates_class(self, flask_client, flask_app):
        flask_client.post(
            "/onboarding",
            data={
                "class_name": "Onboard Class",
                "grade_level": "6th Grade",
                "subject": "Math",
            },
        )
        with flask_app.app_context():
            from src.web.blueprints.helpers import _get_session

            session = _get_session()
            cls = session.query(Class).filter_by(name="Onboard Class").first()
            assert cls is not None
            assert cls.grade_level == "6th Grade"

    def test_onboarding_post_without_data_still_redirects(self, flask_client):
        """Submitting onboarding with no class data still redirects to dashboard."""
        resp = flask_client.post(
            "/onboarding",
            data={"class_name": "", "grade_level": "", "subject": ""},
        )
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]

    def test_onboarding_requires_login(self, anon_flask_client):
        resp = anon_flask_client.get("/onboarding")
        assert resp.status_code == 303


# ============================================================
# Help Page
# ============================================================


class TestHelpPage:
    """Tests for GET /help."""

    def test_help_returns_200(self, flask_client):
        resp = flask_client.get("/help")
        assert resp.status_code == 200

    def test_help_requires_login(self, anon_flask_client):
        resp = anon_flask_client.get("/help")
        assert resp.status_code == 303
