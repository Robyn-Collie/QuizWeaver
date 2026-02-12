"""Backward-compatible wrapper — delegates to Flask blueprints."""

from src.web.blueprints import register_blueprints


def register_routes(app):
    """Register all route handlers on the Flask app via blueprints."""
    register_blueprints(app)
