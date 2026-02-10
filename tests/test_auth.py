"""
Tests for auth hardening (Session 6, Phase A).
"""

import os
import json
import tempfile
import pytest

from src.database import Base, Class, User, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with a temporary database (no users seeded)."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    # Seed a class for context
    cls = Class(name="Test Class", grade_level="8th Grade", subject="Math")
    session.add(cls)
    session.commit()
    session.close()
    engine.dispose()

    from src.web.app import create_app
    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "8th Grade"},
    }
    flask_app = create_app(test_config)
    flask_app.config["TESTING"] = True

    yield flask_app

    flask_app.config["DB_ENGINE"].dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def app_with_user(app):
    """App fixture with a pre-created user."""
    with app.app_context():
        from src.database import get_session as db_get_session
        session = db_get_session(app.config["DB_ENGINE"])
        from src.web.auth import create_user
        create_user(session, "admin", "secret123", display_name="Admin User", role="admin")
        session.close()
    return app


@pytest.fixture
def client(app):
    """Unauthenticated client (no users in DB)."""
    return app.test_client()


@pytest.fixture
def user_client(app_with_user):
    """Authenticated client (DB user exists)."""
    c = app_with_user.test_client()
    c.post("/login", data={"username": "admin", "password": "secret123"})
    return c


# ============================================================
# TestUserModel
# ============================================================

class TestUserModel:
    """Test the User database model."""

    def test_users_table_exists(self, app):
        """Users table is created by ORM."""
        engine = app.config["DB_ENGINE"]
        import sqlite3
        conn = sqlite3.connect(engine.url.database)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        result = cursor.fetchone()
        conn.close()
        assert result is not None

    def test_create_user(self, app):
        """Can create a user via ORM."""
        with app.app_context():
            session = get_session(app.config["DB_ENGINE"])
            user = User(username="teacher1", password_hash="fakehash", display_name="Teacher One")
            session.add(user)
            session.commit()
            assert user.id is not None
            assert user.role == "teacher"
            session.close()

    def test_unique_username(self, app):
        """Username must be unique."""
        with app.app_context():
            session = get_session(app.config["DB_ENGINE"])
            u1 = User(username="unique", password_hash="hash1")
            session.add(u1)
            session.commit()

            u2 = User(username="unique", password_hash="hash2")
            session.add(u2)
            with pytest.raises(Exception):
                session.commit()
            session.rollback()
            session.close()

    def test_default_role(self, app):
        """Default role is 'teacher'."""
        with app.app_context():
            session = get_session(app.config["DB_ENGINE"])
            user = User(username="newteacher", password_hash="hash")
            session.add(user)
            session.commit()
            assert user.role == "teacher"
            session.close()


# ============================================================
# TestAuthHelpers
# ============================================================

class TestAuthHelpers:
    """Test auth helper functions."""

    def test_create_user_hashes_password(self, app):
        """create_user stores a hashed password, not plaintext."""
        with app.app_context():
            session = get_session(app.config["DB_ENGINE"])
            from src.web.auth import create_user
            user = create_user(session, "testhash", "mypassword")
            assert user is not None
            assert user.password_hash != "mypassword"
            assert user.password_hash.startswith("scrypt:") or user.password_hash.startswith("pbkdf2:")
            session.close()

    def test_create_duplicate_returns_none(self, app):
        """create_user returns None for duplicate username."""
        with app.app_context():
            session = get_session(app.config["DB_ENGINE"])
            from src.web.auth import create_user
            create_user(session, "dup", "pass1")
            result = create_user(session, "dup", "pass2")
            assert result is None
            session.close()

    def test_authenticate_valid(self, app):
        """authenticate_user returns user for valid credentials."""
        with app.app_context():
            session = get_session(app.config["DB_ENGINE"])
            from src.web.auth import create_user, authenticate_user
            create_user(session, "auth_test", "correct_pass")
            user = authenticate_user(session, "auth_test", "correct_pass")
            assert user is not None
            assert user.username == "auth_test"
            session.close()

    def test_authenticate_invalid_password(self, app):
        """authenticate_user returns None for wrong password."""
        with app.app_context():
            session = get_session(app.config["DB_ENGINE"])
            from src.web.auth import create_user, authenticate_user
            create_user(session, "auth_inv", "correct")
            user = authenticate_user(session, "auth_inv", "wrong")
            assert user is None
            session.close()

    def test_authenticate_nonexistent(self, app):
        """authenticate_user returns None for nonexistent user."""
        with app.app_context():
            session = get_session(app.config["DB_ENGINE"])
            from src.web.auth import authenticate_user
            user = authenticate_user(session, "ghost", "pass")
            assert user is None
            session.close()

    def test_change_password(self, app):
        """change_password works with correct old password."""
        with app.app_context():
            session = get_session(app.config["DB_ENGINE"])
            from src.web.auth import create_user, change_password, authenticate_user
            user = create_user(session, "chpw", "oldpass")
            result = change_password(session, user.id, "oldpass", "newpass")
            assert result is True
            # Old password no longer works
            assert authenticate_user(session, "chpw", "oldpass") is None
            # New password works
            assert authenticate_user(session, "chpw", "newpass") is not None
            session.close()


# ============================================================
# TestLoginWithDB
# ============================================================

class TestLoginWithDB:
    """Test login when DB users exist."""

    def test_valid_login(self, app_with_user):
        """Valid DB credentials allow login."""
        c = app_with_user.test_client()
        resp = c.post("/login", data={"username": "admin", "password": "secret123"})
        assert resp.status_code == 303

    def test_invalid_login(self, app_with_user):
        """Invalid credentials return 401."""
        c = app_with_user.test_client()
        resp = c.post("/login", data={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_session_user_id(self, app_with_user):
        """Session stores user_id after login."""
        c = app_with_user.test_client()
        c.post("/login", data={"username": "admin", "password": "secret123"})
        with c.session_transaction() as sess:
            assert "user_id" in sess
            assert sess["user_id"] is not None

    def test_session_display_name(self, app_with_user):
        """Session stores display_name after login."""
        c = app_with_user.test_client()
        c.post("/login", data={"username": "admin", "password": "secret123"})
        with c.session_transaction() as sess:
            assert sess.get("display_name") == "Admin User"


# ============================================================
# TestBackwardCompat
# ============================================================

class TestBackwardCompat:
    """Test config-based login when no DB users exist."""

    def test_config_login_valid(self, client):
        """Config credentials work when no DB users."""
        resp = client.post("/login", data={"username": "teacher", "password": "quizweaver"})
        assert resp.status_code == 303

    def test_config_login_invalid(self, client):
        """Invalid config credentials return 401."""
        resp = client.post("/login", data={"username": "teacher", "password": "wrong"})
        assert resp.status_code == 401


# ============================================================
# TestSetupRoute
# ============================================================

class TestSetupRoute:
    """Test first-time setup route."""

    def test_setup_page_loads(self, client):
        """Setup page loads when no users exist."""
        resp = client.get("/setup")
        assert resp.status_code == 200
        assert b"Create your admin account" in resp.data

    def test_setup_creates_admin(self, client, app):
        """Setup creates admin user and logs in."""
        resp = client.post("/setup", data={
            "username": "newadmin",
            "password": "pass123",
            "confirm_password": "pass123",
            "display_name": "New Admin",
        })
        assert resp.status_code == 303

        with client.session_transaction() as sess:
            assert sess.get("logged_in") is True
            assert sess.get("username") == "newadmin"

    def test_setup_redirects_when_users_exist(self, app_with_user):
        """Setup redirects to login when users already exist."""
        c = app_with_user.test_client()
        resp = c.get("/setup")
        assert resp.status_code == 303

    def test_setup_password_mismatch(self, client):
        """Setup rejects mismatched passwords."""
        resp = client.post("/setup", data={
            "username": "admin",
            "password": "pass123",
            "confirm_password": "pass456",
        })
        assert resp.status_code == 400
        assert b"do not match" in resp.data

    def test_setup_short_password(self, client):
        """Setup rejects passwords shorter than 6 characters."""
        resp = client.post("/setup", data={
            "username": "admin",
            "password": "short",
            "confirm_password": "short",
        })
        assert resp.status_code == 400
        assert b"at least 6" in resp.data


# ============================================================
# TestChangePassword
# ============================================================

class TestChangePassword:
    """Test password change route."""

    def test_page_loads(self, user_client):
        """Password change page loads."""
        resp = user_client.get("/settings/password")
        assert resp.status_code == 200
        assert b"Change Password" in resp.data

    def test_change_success(self, user_client):
        """Password change succeeds with correct current password."""
        resp = user_client.post("/settings/password", data={
            "current_password": "secret123",
            "new_password": "newsecret456",
            "confirm_password": "newsecret456",
        })
        assert resp.status_code == 303

    def test_wrong_current_password(self, user_client):
        """Password change fails with wrong current password."""
        resp = user_client.post("/settings/password", data={
            "current_password": "wrongpass",
            "new_password": "newsecret",
            "confirm_password": "newsecret",
        })
        assert resp.status_code == 200
        assert b"incorrect" in resp.data


# ============================================================
# TestGetUserCount
# ============================================================

class TestGetUserCount:
    """Test user count helper."""

    def test_user_count(self, app):
        """get_user_count returns correct count."""
        with app.app_context():
            session = get_session(app.config["DB_ENGINE"])
            from src.web.auth import get_user_count, create_user
            assert get_user_count(session) == 0
            create_user(session, "u1", "p1")
            assert get_user_count(session) == 1
            session.close()
