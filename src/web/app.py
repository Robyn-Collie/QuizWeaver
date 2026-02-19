"""
Flask application factory for QuizWeaver web frontend.
"""

import functools
import json
import os
import secrets

from flask import Flask, g, redirect, send_from_directory, url_for
from flask import session as flask_session
from flask_wtf.csrf import CSRFProtect

from src.database import get_engine, init_db
from src.migrations import run_migrations
from src.web.routes import register_routes

csrf = CSRFProtect()


def _image_login_required(f):
    """Login check for the image serving route (avoids circular import with blueprints)."""

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not flask_session.get("logged_in"):
            return redirect(url_for("auth.login"), code=303)
        return f(*args, **kwargs)

    return wrapper


def _load_or_generate_secret_key(env_path):
    """Load SECRET_KEY from .env or generate and persist a new one.

    Ensures every installation gets a unique, cryptographically random key
    without requiring teachers to configure it manually.
    """
    # Try to read existing key from .env
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("SECRET_KEY="):
                    value = line.split("=", 1)[1].strip().strip("'\"")
                    if value:
                        return value

    # Generate a new key and append to .env
    new_key = secrets.token_hex(32)
    try:
        with open(env_path, "a") as f:
            f.write(f"\nSECRET_KEY={new_key}\n")
    except OSError:
        pass  # Can't persist — use the generated key for this session only
    return new_key


def create_app(config=None):
    """
    Create and configure the Flask application.

    Args:
        config: Application config dict (paths, llm settings, etc.)
                If None, loads from config.yaml.

    Returns:
        Configured Flask app instance
    """
    template_dir = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "static")

    app = Flask(
        __name__,
        template_folder=os.path.abspath(template_dir),
        static_folder=os.path.abspath(static_dir),
    )

    if config is None:
        import yaml

        with open("config.yaml") as f:
            config = yaml.safe_load(f)

    app.config["APP_CONFIG"] = config

    # SEC-003: Auto-generate SECRET_KEY if not set (never use a static default)
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        env_path = os.path.abspath(env_path)
        secret_key = _load_or_generate_secret_key(env_path)
    app.config["SECRET_KEY"] = secret_key

    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit

    # SEC-010: Session cookie hardening
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # SESSION_COOKIE_SECURE = True only makes sense over HTTPS;
    # local-first teachers typically use HTTP on localhost
    if os.environ.get("FLASK_HTTPS"):
        app.config["SESSION_COOKIE_SECURE"] = True

    # SEC-001: CSRF protection on all POST/PUT/DELETE routes
    # WTF_CSRF_ENABLED can be set to False by test fixtures that need to bypass CSRF.
    # In production this is always True (Flask-WTF default).
    csrf.init_app(app)

    # Environment variable overrides
    if os.environ.get("DATABASE_PATH"):
        config.setdefault("paths", {})["database_file"] = os.environ["DATABASE_PATH"]
    if os.environ.get("LLM_PROVIDER"):
        config.setdefault("llm", {})["provider"] = os.environ["LLM_PROVIDER"]

    # Create a single engine for the app lifetime.
    # DATABASE_URL (env var) takes precedence for PostgreSQL support;
    # falls back to the SQLite path in config.
    database_url = os.environ.get("DATABASE_URL")
    db_path = config.get("paths", {}).get("database_file", "quiz_warehouse.db")

    # Run migrations before ORM init (skipped automatically for non-SQLite)
    run_migrations(db_path, verbose=False)

    engine = get_engine(url=database_url) if database_url else get_engine(db_path)
    init_db(engine)
    app.config["DB_ENGINE"] = engine

    @app.teardown_appcontext
    def close_db_session(exception):
        """Close the database session at the end of each request."""
        session = g.pop("db_session", None)
        if session is not None:
            session.close()

    @app.context_processor
    def inject_user():
        """Make current_user available in all templates."""
        return {"current_user": getattr(g, "current_user", None)}

    @app.context_processor
    def inject_ai_tooltips():
        """Make AI literacy tooltips available in all templates."""
        from src.web.tooltip_data import AI_TOOLTIPS

        return {"ai_tips": AI_TOOLTIPS}

    @app.template_filter("ensure_list")
    def ensure_list_filter(value):
        """Ensure a value is a Python list.

        Handles JSON columns in SQLite that may return a raw JSON string
        instead of a parsed list. Used in templates before |join or |tojson.
        """
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            # Comma-separated string fallback
            return [s.strip() for s in value.split(",") if s.strip()]
        return []

    register_routes(app)

    # SEC-007: Serve generated quiz images (requires login)
    generated_images_dir = os.path.abspath(config.get("paths", {}).get("generated_images_dir", "generated_images"))

    @app.route("/generated_images/<filename>")
    @_image_login_required
    def serve_generated_image(filename):
        return send_from_directory(generated_images_dir, filename)

    # SEC-008: Serve uploaded images (requires login)
    @app.route("/uploads/images/<filename>")
    @_image_login_required
    def serve_uploaded_image(filename):
        cfg = app.config["APP_CONFIG"]
        upload_dir = os.path.abspath(cfg.get("paths", {}).get("upload_dir", "uploads/images"))
        return send_from_directory(upload_dir, filename)

    return app
