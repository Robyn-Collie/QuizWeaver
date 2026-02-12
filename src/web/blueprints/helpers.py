"""Shared utilities for QuizWeaver blueprint modules."""

import functools

from flask import current_app, g, redirect, request, url_for
from flask import session as flask_session

from src.database import get_session

# Default credentials for backward-compatible config-based auth
DEFAULT_USERNAME = "teacher"
DEFAULT_PASSWORD = "quizweaver"

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _get_session():
    """Get a database session from the shared app engine."""
    if "db_session" not in g:
        engine = current_app.config["DB_ENGINE"]
        g.db_session = get_session(engine)
    return g.db_session


def login_required(f):
    """Decorator to require login for a route."""

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not flask_session.get("logged_in"):
            return redirect(url_for("auth.login", next=request.url), code=303)
        # Populate g.current_user for templates
        g.current_user = {
            "id": flask_session.get("user_id"),
            "username": flask_session.get("username"),
            "display_name": flask_session.get("display_name"),
        }
        return f(*args, **kwargs)

    return decorated_function
