"""
Flask application factory for QuizWeaver web frontend.
"""

import os
from flask import Flask, g, send_from_directory

from src.database import get_engine, init_db, get_session
from src.web.routes import register_routes


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
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)

    app.config["APP_CONFIG"] = config
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-in-production")

    # Create a single engine for the app lifetime
    db_path = config["paths"]["database_file"]
    engine = get_engine(db_path)
    init_db(engine)
    app.config["DB_ENGINE"] = engine

    @app.teardown_appcontext
    def close_db_session(exception):
        """Close the database session at the end of each request."""
        session = g.pop("db_session", None)
        if session is not None:
            session.close()

    register_routes(app)

    # Serve generated quiz images
    generated_images_dir = os.path.abspath(
        config.get("paths", {}).get("generated_images_dir", "generated_images")
    )

    @app.route("/generated_images/<path:filename>")
    def serve_generated_image(filename):
        return send_from_directory(generated_images_dir, filename)

    return app
