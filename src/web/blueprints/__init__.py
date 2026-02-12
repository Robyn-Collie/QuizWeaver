"""Flask blueprints for QuizWeaver web frontend."""

from src.web.blueprints.analytics import analytics_bp
from src.web.blueprints.auth import auth_bp
from src.web.blueprints.classes import classes_bp
from src.web.blueprints.content import content_bp
from src.web.blueprints.main import main_bp
from src.web.blueprints.quizzes import quizzes_bp
from src.web.blueprints.settings import settings_bp
from src.web.blueprints.study import study_bp


def register_blueprints(app):
    """Register all blueprint modules on the Flask app."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(classes_bp)
    app.register_blueprint(quizzes_bp)
    app.register_blueprint(study_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(content_bp)
