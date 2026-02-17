"""Security tests for CRITICAL and HIGH audit findings."""

import os
import tempfile

import pytest

from src.database import get_session
from src.web.auth import create_user


@pytest.fixture
def secure_app():
    """Create a Flask app with security features enabled."""
    from src.web.app import create_app

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    config = {
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "7th Grade"},
        "paths": {"database_file": tmp.name},
    }
    app = create_app(config)
    app.config["TESTING"] = True
    # WTF_CSRF_ENABLED is True by default — tests that need to bypass
    # CSRF should use the csrf_client fixture instead

    yield app

    app.config["DB_ENGINE"].dispose()
    try:
        os.remove(tmp.name)
    except (PermissionError, FileNotFoundError):
        pass


@pytest.fixture
def secure_app_with_user(secure_app):
    """App with a pre-created user account."""
    engine = secure_app.config["DB_ENGINE"]
    session = get_session(engine)
    create_user(session, "testteacher", "securepass99", display_name="Test Teacher")
    session.commit()
    session.close()
    return secure_app


@pytest.fixture
def csrf_client(secure_app_with_user):
    """Client that bypasses CSRF for non-CSRF tests."""
    secure_app_with_user.config["WTF_CSRF_ENABLED"] = False
    c = secure_app_with_user.test_client()
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "testteacher"
        sess["user_id"] = 1
    return c


class TestCSRFProtection:
    """SEC-001: CSRF protection on all POST routes."""

    def test_post_without_csrf_token_rejected(self, secure_app_with_user):
        """POST to a protected route without CSRF token should fail."""
        client = secure_app_with_user.test_client()
        with client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "testteacher"
            sess["user_id"] = 1

        resp = client.post("/classes/new", data={"name": "Test", "grade_level": "7th"})
        assert resp.status_code == 400  # CSRF validation failure

    def test_login_csrf_exempt_or_works(self, secure_app_with_user):
        """Login form should work (CSRF token included in form or exempt)."""
        client = secure_app_with_user.test_client()
        # GET the login page first to get the CSRF token
        resp = client.get("/login")
        assert resp.status_code == 200
        # Check that csrf_token is in the page
        assert b"csrf_token" in resp.data


class TestOpenRedirect:
    """SEC-002: Open redirect via login next parameter."""

    def test_external_redirect_blocked(self, secure_app_with_user):
        """Login with next=https://evil.com should redirect to dashboard."""
        secure_app_with_user.config["WTF_CSRF_ENABLED"] = False
        client = secure_app_with_user.test_client()
        resp = client.post(
            "/login?next=https://evil.com",
            data={"username": "testteacher", "password": "securepass99"},
        )
        assert resp.status_code == 303
        location = resp.headers.get("Location", "")
        assert "evil.com" not in location
        assert "/dashboard" in location or location.endswith("/")

    def test_protocol_relative_redirect_blocked(self, secure_app_with_user):
        """Login with next=//evil.com should redirect to dashboard."""
        secure_app_with_user.config["WTF_CSRF_ENABLED"] = False
        client = secure_app_with_user.test_client()
        resp = client.post(
            "/login?next=//evil.com",
            data={"username": "testteacher", "password": "securepass99"},
        )
        assert resp.status_code == 303
        location = resp.headers.get("Location", "")
        assert "evil.com" not in location

    def test_safe_relative_redirect_works(self, secure_app_with_user):
        """Login with next=/quizzes should redirect there."""
        secure_app_with_user.config["WTF_CSRF_ENABLED"] = False
        client = secure_app_with_user.test_client()
        resp = client.post(
            "/login?next=/quizzes",
            data={"username": "testteacher", "password": "securepass99"},
        )
        assert resp.status_code == 303
        location = resp.headers.get("Location", "")
        assert "/quizzes" in location


class TestSecretKey:
    """SEC-003: SECRET_KEY should not be the static default."""

    def test_secret_key_not_default(self, secure_app):
        """App should not use the old hardcoded default key."""
        assert secure_app.config["SECRET_KEY"] != "dev-key-change-in-production"
        assert len(secure_app.config["SECRET_KEY"]) >= 32


class TestDefaultCredentials:
    """SEC-004: Default credentials should not work."""

    def test_default_creds_rejected_when_users_exist(self, secure_app_with_user):
        """teacher/quizweaver should not work when DB users exist."""
        secure_app_with_user.config["WTF_CSRF_ENABLED"] = False
        client = secure_app_with_user.test_client()
        resp = client.post(
            "/login",
            data={"username": "teacher", "password": "quizweaver"},
        )
        assert resp.status_code == 401

    def test_default_creds_redirect_to_setup_when_no_users(self, secure_app):
        """With no DB users, login POST should redirect to setup."""
        secure_app.config["WTF_CSRF_ENABLED"] = False
        client = secure_app.test_client()
        resp = client.post(
            "/login",
            data={"username": "teacher", "password": "quizweaver"},
        )
        assert resp.status_code == 303
        assert "/setup" in resp.headers.get("Location", "")


class TestSessionSecurity:
    """SEC-011/012: Session regeneration and invalidation."""

    def test_session_cleared_on_login(self, secure_app_with_user):
        """Old session data should not persist after login."""
        secure_app_with_user.config["WTF_CSRF_ENABLED"] = False
        client = secure_app_with_user.test_client()
        # Set some pre-login session data
        with client.session_transaction() as sess:
            sess["attacker_data"] = "should_be_gone"

        client.post(
            "/login",
            data={"username": "testteacher", "password": "securepass99"},
        )
        with client.session_transaction() as sess:
            assert "attacker_data" not in sess
            assert sess.get("logged_in") is True

    def test_session_cleared_on_password_change(self, secure_app_with_user):
        """After password change, user should be logged out."""
        secure_app_with_user.config["WTF_CSRF_ENABLED"] = False
        client = secure_app_with_user.test_client()
        with client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "testteacher"
            sess["user_id"] = 1

        resp = client.post(
            "/settings/password",
            data={
                "current_password": "securepass99",
                "new_password": "newsecurepass99",
                "confirm_password": "newsecurepass99",
            },
        )
        assert resp.status_code == 303
        assert "/login" in resp.headers.get("Location", "")

        # Session should be cleared
        with client.session_transaction() as sess:
            assert not sess.get("logged_in")


class TestImageServing:
    """SEC-007: Generated images require authentication."""

    def test_images_require_login(self, secure_app):
        """Unauthenticated access to generated images should redirect to login."""
        client = secure_app.test_client()
        resp = client.get("/generated_images/test.png")
        assert resp.status_code == 303
        assert "/login" in resp.headers.get("Location", "")


class TestLogoutMethod:
    """Logout should require POST method."""

    def test_logout_get_not_allowed(self, secure_app_with_user):
        """GET /logout should return 405."""
        client = secure_app_with_user.test_client()
        with client.session_transaction() as sess:
            sess["logged_in"] = True
        resp = client.get("/logout")
        assert resp.status_code == 405


class TestPasswordPolicy:
    """Password should require at least 8 characters."""

    def test_short_password_rejected_on_setup(self, secure_app):
        """Setup with 7-char password should fail."""
        secure_app.config["WTF_CSRF_ENABLED"] = False
        client = secure_app.test_client()
        resp = client.post(
            "/setup",
            data={
                "username": "teacher",
                "password": "short77",
                "confirm_password": "short77",
            },
        )
        assert resp.status_code == 400
        assert b"8 characters" in resp.data


class TestApiKeyNotInConfig:
    """SEC-005: API key should not be written to config.yaml."""

    def test_api_key_stripped_from_config(self, csrf_client, secure_app_with_user):
        """After saving settings with an API key, config.yaml should not contain it."""
        resp = csrf_client.post(
            "/settings",
            data={
                "provider": "mock",
                "api_key": "test-secret-key-12345",
            },
        )
        assert resp.status_code == 303

        config = secure_app_with_user.config["APP_CONFIG"]
        assert "api_key" not in config.get("llm", {})


class TestSessionCookieFlags:
    """SEC-010: Session cookie hardening."""

    def test_samesite_lax(self, secure_app):
        """Session cookie should have SameSite=Lax."""
        assert secure_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

    def test_httponly(self, secure_app):
        """Session cookie should have HttpOnly flag."""
        assert secure_app.config["SESSION_COOKIE_HTTPONLY"] is True


class TestErrorMessageSanitization:
    """SEC-013: Error messages should not leak internal details."""

    def test_flash_generation_error_hides_exception(self):
        """flash_generation_error should flash a generic message, not the raw exception."""
        from unittest.mock import patch

        # Create a fake Flask app context for flash() to work
        from flask import Flask

        from src.web.blueprints.helpers import flash_generation_error

        app = Flask(__name__)
        app.config["SECRET_KEY"] = "test"
        with app.test_request_context():
            with patch("src.web.blueprints.helpers.flash") as mock_flash:
                try:
                    raise RuntimeError("/home/user/.secret/internal_path: connection failed")
                except RuntimeError as e:
                    flash_generation_error("Quiz generation", e)

                mock_flash.assert_called_once()
                msg = mock_flash.call_args[0][0]
                # The generic message should NOT contain the internal path
                assert "/home/user" not in msg
                assert "internal_path" not in msg
                # It should contain the task label
                assert "Quiz generation" in msg

    def test_quiz_generate_invalid_num_questions(self, csrf_client):
        """Non-numeric num_questions should not crash the server."""
        from unittest.mock import patch

        with patch("src.web.blueprints.quizzes.generate_quiz") as mock_gen:
            mock_gen.return_value = None
            resp = csrf_client.post(
                "/classes/1/generate",
                data={
                    "num_questions": "not_a_number",
                    "grade_level": "7th Grade",
                },
            )
            # Should NOT return 500 (would indicate unhandled ValueError)
            assert resp.status_code != 500

    def test_quiz_generate_clamps_num_questions(self, csrf_client):
        """Extreme num_questions values should be clamped."""
        from unittest.mock import patch

        with (
            patch("src.web.blueprints.quizzes.generate_quiz") as mock_gen,
            patch("src.web.blueprints.quizzes.get_class") as mock_class,
        ):
            mock_class.return_value = type("C", (), {"name": "Test", "id": 1})()
            mock_gen.return_value = None
            # Submit absurdly large value
            resp = csrf_client.post(
                "/classes/1/generate",
                data={
                    "num_questions": "99999",
                    "grade_level": "7th Grade",
                },
            )
            assert resp.status_code != 500
            # Verify the clamped value was passed (max 100)
            if mock_gen.called:
                call_kwargs = mock_gen.call_args[1]
                assert call_kwargs.get("num_questions", 0) <= 100


class TestClozeXSSSanitization:
    """SEC-014: Cloze question display should escape LLM-generated text."""

    def test_cloze_text_html_escaped(self, csrf_client):
        """Cloze question text with HTML should be escaped before rendering."""
        # Get a session and create a quiz with a cloze question containing HTML

        from src.database import Question, Quiz, get_session

        with csrf_client.application.test_request_context():
            engine = csrf_client.application.config["DB_ENGINE"]
            session = get_session(engine)

            # Create a class first
            from src.classroom import create_class

            cls = create_class(session, "Test Class", "7th", "Science")

            quiz = Quiz(
                title="Test Cloze Quiz",
                class_id=cls.id,
                status="generated",
            )
            session.add(quiz)
            session.flush()

            import json

            malicious_text = '<script>alert("xss")</script> The answer is {{1}}.'
            q = Question(
                quiz_id=quiz.id,
                question_type="cloze",
                title="Cloze Q",
                text=malicious_text,
                points=1,
                sort_order=0,
                data=json.dumps(
                    {
                        "type": "cloze",
                        "blanks": [{"id": "1", "answer": "test"}],
                    }
                ),
            )
            session.add(q)
            session.commit()
            quiz_id = quiz.id
            session.close()

        resp = csrf_client.get(f"/quizzes/{quiz_id}")
        assert resp.status_code == 200
        # The injected script payload should NOT appear unescaped
        assert b'<script>alert("xss")</script>' not in resp.data
        # The escaped version should appear instead
        assert b"&lt;script&gt;" in resp.data or b"cloze-blank" in resp.data


class TestRouteAuthentication:
    """Verify all data-modifying routes require authentication."""

    def test_unauthenticated_post_redirects_to_login(self, secure_app_with_user):
        """POST to protected routes without login should redirect to login."""
        secure_app_with_user.config["WTF_CSRF_ENABLED"] = False
        client = secure_app_with_user.test_client()

        protected_post_routes = [
            "/classes/new",
            "/classes/1/edit",
            "/classes/1/delete",
            "/classes/1/lessons/new",
            "/settings",
            "/onboarding",
        ]
        for route in protected_post_routes:
            resp = client.post(route, data={"name": "test"})
            assert resp.status_code == 303, f"Route {route} should redirect, got {resp.status_code}"
            location = resp.headers.get("Location", "")
            assert "/login" in location, f"Route {route} should redirect to login, got {location}"

    def test_unauthenticated_api_redirects(self, secure_app_with_user):
        """API endpoints should also require authentication."""
        client = secure_app_with_user.test_client()
        api_routes = [
            "/api/stats",
            "/api/audit-log",
            "/api/estimate-cost",
        ]
        for route in api_routes:
            resp = client.get(route)
            assert resp.status_code == 303, f"API {route} should redirect, got {resp.status_code}"
