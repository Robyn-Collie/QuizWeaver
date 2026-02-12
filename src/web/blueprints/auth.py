"""Authentication routes: login, logout, setup, password change, health check."""

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask import session as flask_session

from src.web.auth import authenticate_user, change_password, create_user, get_user_count
from src.web.blueprints.helpers import (
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    _get_session,
    login_required,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login via form POST or render login page on GET."""
    session = _get_session()
    user_count = get_user_count(session)
    if user_count > 0 and request.method == "GET":
        pass  # Normal login page
    elif user_count == 0 and request.method == "GET":
        return redirect(url_for("auth.setup"), code=303)

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # Try DB-based auth first (if users exist)
        if user_count > 0:
            user = authenticate_user(session, username, password)
            if user:
                flask_session["logged_in"] = True
                flask_session["user_id"] = user.id
                flask_session["username"] = user.username
                flask_session["display_name"] = user.display_name
                next_url = request.args.get("next", url_for("main.dashboard"))
                return redirect(next_url, code=303)
            else:
                return render_template("login.html", error="Invalid username or password."), 401
        else:
            # Backward compatible: config-based credentials when no DB users
            config = current_app.config["APP_CONFIG"]
            valid_user = config.get("auth", {}).get("username", DEFAULT_USERNAME)
            valid_pass = config.get("auth", {}).get("password", DEFAULT_PASSWORD)

            if username == valid_user and password == valid_pass:
                flask_session["logged_in"] = True
                flask_session["username"] = username
                flask_session["display_name"] = username
                next_url = request.args.get("next", url_for("main.dashboard"))
                return redirect(next_url, code=303)
            else:
                return render_template("login.html", error="Invalid username or password."), 401

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Clear session and redirect to login page."""
    flask_session.clear()
    return redirect(url_for("auth.login"), code=303)


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First-time admin registration (only when no users in DB)."""
    session = _get_session()
    if get_user_count(session) > 0:
        return redirect(url_for("auth.login"), code=303)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        display_name = request.form.get("display_name", "").strip() or None

        if not username:
            return render_template("setup.html", error="Username is required."), 400
        if len(password) < 6:
            return render_template("setup.html", error="Password must be at least 6 characters."), 400
        if password != confirm:
            return render_template("setup.html", error="Passwords do not match."), 400

        user = create_user(session, username, password, display_name=display_name, role="admin")
        if not user:
            return render_template("setup.html", error="Could not create user."), 400

        flask_session["logged_in"] = True
        flask_session["user_id"] = user.id
        flask_session["username"] = user.username
        flask_session["display_name"] = user.display_name
        flash("Account created successfully. Welcome to QuizWeaver!", "success")
        return redirect(url_for("main.dashboard"), code=303)

    return render_template("setup.html")


@auth_bp.route("/settings/password", methods=["GET", "POST"])
@login_required
def settings_password():
    """Change password form."""
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        user_id = flask_session.get("user_id")
        if not user_id:
            flash("Password change is only available for database-authenticated users.", "error")
            return redirect(url_for("settings.settings"), code=303)

        if len(new_pw) < 6:
            return render_template("settings/password.html", error="New password must be at least 6 characters.")
        if new_pw != confirm_pw:
            return render_template("settings/password.html", error="New passwords do not match.")

        session = _get_session()
        if change_password(session, user_id, current_pw, new_pw):
            flash("Password changed successfully.", "success")
            return redirect(url_for("settings.settings"), code=303)
        else:
            return render_template("settings/password.html", error="Current password is incorrect.")

    return render_template("settings/password.html")


@auth_bp.route("/health")
def health():
    """Health check endpoint for monitoring and Docker."""
    return jsonify({"status": "ok", "service": "quizweaver"})
