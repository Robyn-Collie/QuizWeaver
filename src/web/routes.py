"""
Route handlers for QuizWeaver web frontend.
"""

import functools
import json
import os
import re
from datetime import date
from io import BytesIO

from flask import (
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask import (
    session as flask_session,
)
from werkzeug.utils import secure_filename

from src.classroom import create_class, delete_class, get_class, list_classes, update_class
from src.cost_tracking import check_budget, get_cost_summary, get_monthly_total
from src.database import (
    LessonLog,
    PerformanceData,
    Question,
    Quiz,
    Rubric,
    RubricCriterion,
    StudyCard,
    StudySet,
    get_session,
)
from src.export import export_csv, export_docx, export_gift, export_pdf, export_qti
from src.lesson_tracker import delete_lesson, get_assumed_knowledge, list_lessons, log_lesson
from src.llm_provider import get_provider, get_provider_info
from src.performance_analytics import (
    compute_gap_analysis,
    get_class_summary,
    get_standards_mastery,
    get_topic_trends,
)
from src.performance_import import (
    get_sample_csv,
    import_csv_data,
    import_quiz_scores,
)
from src.quiz_generator import generate_quiz
from src.reteach_generator import generate_reteach_suggestions
from src.rubric_export import export_rubric_csv, export_rubric_docx, export_rubric_pdf
from src.rubric_generator import generate_rubric
from src.standards import (
    STANDARD_SETS,
    ensure_standard_set_loaded,
    get_available_standard_sets,
    get_grade_bands,
    get_standard_sets_in_db,
    get_subjects,
    list_standards,
    search_standards,
    standards_count,
)
from src.study_export import (
    export_flashcards_csv,
    export_flashcards_tsv,
    export_study_docx,
    export_study_pdf,
)
from src.study_generator import generate_study_material
from src.topic_generator import (
    generate_from_topics,
    search_topics,
)
from src.variant_generator import READING_LEVELS, generate_variant
from src.web.auth import (
    authenticate_user,
    change_password,
    create_user,
    get_user_count,
)
from src.web.config_utils import save_config

# Default credentials for backward-compatible config-based auth
DEFAULT_USERNAME = "teacher"
DEFAULT_PASSWORD = "quizweaver"


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
            return redirect(url_for("login", next=request.url), code=303)
        # Populate g.current_user for templates
        g.current_user = {
            "id": flask_session.get("user_id"),
            "username": flask_session.get("username"),
            "display_name": flask_session.get("display_name"),
        }
        return f(*args, **kwargs)

    return decorated_function


def register_routes(app):
    """Register all route handlers on the Flask app."""

    # --- Authentication ---

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """Handle user login via form POST or render login page on GET."""
        # Redirect to setup if no users exist yet
        session = _get_session()
        user_count = get_user_count(session)
        if user_count > 0 and request.method == "GET":
            pass  # Normal login page
        elif user_count == 0 and request.method == "GET":
            return redirect(url_for("setup"), code=303)

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
                    next_url = request.args.get("next", url_for("dashboard"))
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
                    next_url = request.args.get("next", url_for("dashboard"))
                    return redirect(next_url, code=303)
                else:
                    return render_template("login.html", error="Invalid username or password."), 401

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        """Clear session and redirect to login page."""
        flask_session.clear()
        return redirect(url_for("login"), code=303)

    # --- First-time Setup ---

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        """First-time admin registration (only when no users in DB)."""
        session = _get_session()
        if get_user_count(session) > 0:
            return redirect(url_for("login"), code=303)

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
            return redirect(url_for("dashboard"), code=303)

        return render_template("setup.html")

    # --- Password Change ---

    @app.route("/settings/password", methods=["GET", "POST"])
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
                return redirect(url_for("settings"), code=303)

            if len(new_pw) < 6:
                return render_template("settings/password.html", error="New password must be at least 6 characters.")
            if new_pw != confirm_pw:
                return render_template("settings/password.html", error="New passwords do not match.")

            session = _get_session()
            if change_password(session, user_id, current_pw, new_pw):
                flash("Password changed successfully.", "success")
                return redirect(url_for("settings"), code=303)
            else:
                return render_template("settings/password.html", error="Current password is incorrect.")

        return render_template("settings/password.html")

    # --- Health Check (no auth) ---

    @app.route("/health")
    def health():
        """Health check endpoint for monitoring and Docker."""
        return jsonify({"status": "ok", "service": "quizweaver"})

    # --- Main Routes (protected) ---

    @app.route("/")
    @login_required
    def index():
        """Redirect root URL to the dashboard."""
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        """Render dashboard with classes, tools, and recent activity."""
        session = _get_session()
        classes = list_classes(session)

        # Redirect first-time users to onboarding if they have no classes
        if len(classes) == 0 and request.args.get("skip_onboarding") != "1":
            return redirect(url_for("onboarding"))
        total_lessons = session.query(LessonLog).count()

        # Recent activity: 5 most recent lessons and quizzes
        recent_lesson_rows = (
            session.query(LessonLog).order_by(LessonLog.date.desc(), LessonLog.id.desc()).limit(5).all()
        )
        recent_lessons = []
        for lesson_row in recent_lesson_rows:
            cls = get_class(session, lesson_row.class_id)
            topics = json.loads(lesson_row.topics) if lesson_row.topics else []
            recent_lessons.append(
                {
                    "id": lesson_row.id,
                    "date": str(lesson_row.date),
                    "class_id": lesson_row.class_id,
                    "class_name": cls.name if cls else "Unknown",
                    "topics": topics,
                    "preview": (lesson_row.content or "")[:80],
                }
            )

        recent_quiz_rows = session.query(Quiz).order_by(Quiz.id.desc()).limit(5).all()
        recent_quizzes = []
        for q in recent_quiz_rows:
            cls = get_class(session, q.class_id)
            recent_quizzes.append(
                {
                    "id": q.id,
                    "title": q.title,
                    "status": q.status,
                    "class_id": q.class_id,
                    "class_name": cls.name if cls else "Unknown",
                }
            )

        return render_template(
            "dashboard.html",
            classes=classes,
            total_classes=len(classes),
            total_lessons=total_lessons,
            recent_lessons=recent_lessons,
            recent_quizzes=recent_quizzes,
        )

    # --- Stats API ---

    @app.route("/api/stats")
    @login_required
    def api_stats():
        """Return JSON stats for dashboard charts (lessons by date, quizzes by class)."""
        session = _get_session()

        # Lessons by date
        all_lessons = session.query(LessonLog).order_by(LessonLog.date).all()
        date_counts = {}
        for lesson in all_lessons:
            d = str(lesson.date)
            date_counts[d] = date_counts.get(d, 0) + 1
        lessons_by_date = [{"date": d, "count": c} for d, c in sorted(date_counts.items())]

        # Quizzes by class
        classes = list_classes(session)
        quizzes_by_class = [{"class_name": cls["name"], "count": cls["quiz_count"]} for cls in classes]

        return jsonify(
            {
                "lessons_by_date": lessons_by_date,
                "quizzes_by_class": quizzes_by_class,
            }
        )

    # --- Onboarding ---

    @app.route("/onboarding", methods=["GET", "POST"])
    @login_required
    def onboarding():
        """First-time onboarding wizard for new teachers."""
        if request.method == "POST":
            session = _get_session()
            name = request.form.get("class_name", "").strip()
            grade = request.form.get("grade_level", "").strip()
            subject = request.form.get("subject", "").strip()

            if name and grade and subject:
                from src.classroom import create_class as cc

                cc(session, name, grade, subject)
                flash("Welcome to QuizWeaver! Your first class has been created.", "success")
            else:
                flash("Welcome to QuizWeaver!", "success")

            return redirect(url_for("dashboard", skip_onboarding="1"))

        return render_template("onboarding.html")

    # --- Classes ---

    @app.route("/classes")
    @login_required
    def classes_list():
        """List all classes with lesson and quiz counts."""
        session = _get_session()
        classes = list_classes(session)
        return render_template("classes/list.html", classes=classes)

    @app.route("/classes/new", methods=["GET", "POST"])
    @login_required
    def class_create():
        """Create a new class via form POST or render creation form on GET."""
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name:
                return render_template(
                    "classes/new.html",
                    error="Class name is required.",
                ), 400

            session = _get_session()
            grade_level = request.form.get("grade_level", "").strip() or None
            subject = request.form.get("subject", "").strip() or None
            standards_raw = request.form.get("standards", "").strip()
            standards = [s.strip() for s in standards_raw.split(",") if s.strip()] if standards_raw else None

            new_cls = create_class(
                session,
                name=name,
                grade_level=grade_level,
                subject=subject,
                standards=standards,
            )
            flash(f"Class '{new_cls.name}' created successfully.", "success")
            return redirect(url_for("classes_list"), code=303)

        return render_template("classes/new.html")

    @app.route("/classes/<int:class_id>")
    @login_required
    def class_detail(class_id):
        """Show class detail with knowledge depth, lessons, and quizzes."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        knowledge = get_assumed_knowledge(session, class_id)
        lessons = list_lessons(session, class_id)
        quizzes = session.query(Quiz).filter_by(class_id=class_id).all()

        return render_template(
            "classes/detail.html",
            class_obj=class_obj,
            knowledge=knowledge,
            lessons=lessons,
            quizzes=quizzes,
        )

    @app.route("/classes/<int:class_id>/edit", methods=["GET", "POST"])
    @login_required
    def class_edit(class_id):
        """Edit class details via form POST or render edit form on GET."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        if request.method == "POST":
            name = request.form.get("name", "").strip() or None
            grade_level = request.form.get("grade_level", "").strip() or None
            subject = request.form.get("subject", "").strip() or None
            standards_raw = request.form.get("standards", "").strip()
            standards = [s.strip() for s in standards_raw.split(",") if s.strip()] if standards_raw else None

            update_class(
                session,
                class_id=class_id,
                name=name,
                grade_level=grade_level,
                subject=subject,
                standards=standards,
            )
            flash("Class updated successfully.", "success")
            return redirect(url_for("class_detail", class_id=class_id), code=303)

        return render_template("classes/edit.html", class_obj=class_obj)

    @app.route("/classes/<int:class_id>/delete", methods=["POST"])
    @login_required
    def class_delete_route(class_id):
        """Delete a class and redirect to the class list."""
        session = _get_session()
        success = delete_class(session, class_id)
        if not success:
            abort(404)
        flash("Class deleted successfully.", "success")
        return redirect(url_for("classes_list"), code=303)

    # --- Lessons ---

    @app.route("/classes/<int:class_id>/lessons")
    @login_required
    def lessons_list(class_id):
        """List all lessons for a class with parsed topic lists."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        lessons = list_lessons(session, class_id)

        # Parse topics from JSON strings
        parsed_lessons = []
        for lesson in lessons:
            topics = lesson.topics
            if isinstance(topics, str):
                topics = json.loads(topics)
            parsed_lessons.append(
                {
                    "id": lesson.id,
                    "date": lesson.date,
                    "content": lesson.content,
                    "topics": topics or [],
                    "notes": lesson.notes,
                }
            )

        return render_template(
            "lessons/list.html",
            class_obj=class_obj,
            lessons=parsed_lessons,
        )

    @app.route("/classes/<int:class_id>/lessons/new", methods=["GET", "POST"])
    @login_required
    def lesson_log(class_id):
        """Log a new lesson via form POST or render the lesson form on GET."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        if request.method == "POST":
            content = request.form.get("content", "").strip()
            notes = request.form.get("notes", "").strip() or None
            topics_raw = request.form.get("topics", "").strip()
            topics = [t.strip() for t in topics_raw.split(",") if t.strip()] if topics_raw else None

            log_lesson(
                session,
                class_id=class_id,
                content=content,
                topics=topics,
                notes=notes,
            )
            flash("Lesson logged successfully.", "success")
            return redirect(url_for("lessons_list", class_id=class_id), code=303)

        return render_template(
            "lessons/new.html",
            class_obj=class_obj,
            today=date.today().isoformat(),
        )

    @app.route("/classes/<int:class_id>/lessons/<int:lesson_id>/delete", methods=["POST"])
    @login_required
    def lesson_delete_route(class_id, lesson_id):
        """Delete a lesson and redirect back to the lesson list."""
        session = _get_session()
        # Verify class exists
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        success = delete_lesson(session, lesson_id)
        if not success:
            abort(404)
        flash("Lesson deleted successfully.", "success")
        return redirect(url_for("lessons_list", class_id=class_id), code=303)

    # --- Quizzes ---

    @app.route("/quizzes")
    @login_required
    def quizzes_list():
        """List all quizzes with class names, question counts, search, and pagination."""
        session = _get_session()
        query = session.query(Quiz)

        # Apply optional filters
        search_q = request.args.get("q", "").strip()
        status_filter = request.args.get("status")
        class_id_filter = request.args.get("class_id", type=int)

        if search_q:
            query = query.filter(Quiz.title.ilike(f"%{search_q}%"))
        if status_filter:
            query = query.filter(Quiz.status == status_filter)
        if class_id_filter:
            query = query.filter(Quiz.class_id == class_id_filter)

        # Pagination
        page = max(1, request.args.get("page", 1, type=int))
        per_page = 20
        total = query.count()
        total_pages = max(1, (total + per_page - 1) // per_page)
        if page > total_pages:
            page = total_pages

        quizzes = query.order_by(Quiz.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        quiz_data = []
        for q in quizzes:
            class_obj = get_class(session, q.class_id) if q.class_id else None
            question_count = session.query(Question).filter_by(quiz_id=q.id).count()
            quiz_data.append(
                {
                    "id": q.id,
                    "title": q.title,
                    "status": q.status,
                    "class_name": class_obj.name if class_obj else "N/A",
                    "question_count": question_count,
                    "created_at": q.created_at,
                }
            )

        all_classes = list_classes(session)

        return render_template(
            "quizzes/list.html",
            quizzes=quiz_data,
            all_classes=all_classes,
            search_q=search_q,
            status_filter=status_filter,
            class_id_filter=class_id_filter,
            page=page,
            total_pages=total_pages,
            total=total,
        )

    @app.route("/quizzes/<int:quiz_id>")
    @login_required
    def quiz_detail(quiz_id):
        """Show quiz detail with all questions and parsed answer data."""
        session = _get_session()
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            abort(404)

        questions = session.query(Question).filter_by(quiz_id=quiz_id).order_by(Question.sort_order, Question.id).all()
        class_obj = get_class(session, quiz.class_id) if quiz.class_id else None

        parsed_questions = []
        for q in questions:
            data = q.data
            if isinstance(data, str):
                data = json.loads(data)
            parsed_questions.append(
                {
                    "id": q.id,
                    "type": q.question_type,
                    "title": q.title,
                    "text": q.text,
                    "points": q.points,
                    "data": data,
                    "saved_to_bank": bool(getattr(q, "saved_to_bank", 0)),
                }
            )

        # Parse style_profile for template use
        style_profile = quiz.style_profile
        if isinstance(style_profile, str):
            try:
                style_profile = json.loads(style_profile)
            except (json.JSONDecodeError, ValueError):
                style_profile = {}
        if not isinstance(style_profile, dict):
            style_profile = {}

        # Ensure sol_standards is a list, not a JSON string
        sol_val = style_profile.get("sol_standards")
        if isinstance(sol_val, str):
            try:
                parsed = json.loads(sol_val)
                if isinstance(parsed, list):
                    style_profile["sol_standards"] = parsed
                else:
                    style_profile["sol_standards"] = [sol_val] if sol_val.strip() else []
            except (json.JSONDecodeError, ValueError):
                # Comma-separated string fallback
                style_profile["sol_standards"] = [s.strip() for s in sol_val.split(",") if s.strip()]

        # Variant lineage info
        parent_quiz = None
        if quiz.parent_quiz_id:
            parent_quiz = session.query(Quiz).filter_by(id=quiz.parent_quiz_id).first()

        variant_count = session.query(Quiz).filter_by(parent_quiz_id=quiz_id).count()

        # Rubrics for this quiz
        rubrics = session.query(Rubric).filter_by(quiz_id=quiz_id).order_by(Rubric.created_at.desc()).all()

        return render_template(
            "quizzes/detail.html",
            quiz=quiz,
            questions=parsed_questions,
            class_obj=class_obj,
            style_profile=style_profile,
            parent_quiz=parent_quiz,
            variant_count=variant_count,
            rubrics=rubrics,
            reading_levels=READING_LEVELS,
        )

    @app.route("/classes/<int:class_id>/quizzes")
    @login_required
    def class_quizzes(class_id):
        """List quizzes filtered to a specific class."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        quizzes = session.query(Quiz).filter_by(class_id=class_id).order_by(Quiz.created_at.desc()).all()
        quiz_data = []
        for q in quizzes:
            question_count = session.query(Question).filter_by(quiz_id=q.id).count()
            quiz_data.append(
                {
                    "id": q.id,
                    "title": q.title,
                    "status": q.status,
                    "class_name": class_obj.name,
                    "question_count": question_count,
                    "created_at": q.created_at,
                }
            )
        return render_template(
            "quizzes/list.html",
            quizzes=quiz_data,
            class_obj=class_obj,
        )

    # --- Quiz Export ---

    @app.route("/quizzes/<int:quiz_id>/export/<format_name>")
    @login_required
    def quiz_export(quiz_id, format_name):
        """Download a quiz in the requested format (csv, docx, gift, pdf, qti)."""
        if format_name not in ("csv", "docx", "gift", "pdf", "qti"):
            abort(404)

        session = _get_session()
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            abort(404)

        questions = session.query(Question).filter_by(quiz_id=quiz_id).order_by(Question.sort_order, Question.id).all()

        # Parse style_profile
        style_profile = quiz.style_profile
        if isinstance(style_profile, str):
            try:
                style_profile = json.loads(style_profile)
            except (json.JSONDecodeError, ValueError):
                style_profile = {}
        if not isinstance(style_profile, dict):
            style_profile = {}

        # Ensure sol_standards is a list, not a JSON string
        sol_val = style_profile.get("sol_standards")
        if isinstance(sol_val, str):
            try:
                parsed = json.loads(sol_val)
                if isinstance(parsed, list):
                    style_profile["sol_standards"] = parsed
                else:
                    style_profile["sol_standards"] = [sol_val] if sol_val.strip() else []
            except (json.JSONDecodeError, ValueError):
                style_profile["sol_standards"] = [s.strip() for s in sol_val.split(",") if s.strip()]

        # Sanitize title for filename
        safe_title = re.sub(r"[^\w\s\-]", "", quiz.title or "quiz")
        safe_title = re.sub(r"\s+", "_", safe_title.strip())[:80] or "quiz"

        if format_name == "csv":
            csv_str = export_csv(quiz, questions, style_profile)
            buf = BytesIO(csv_str.encode("utf-8"))
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.csv",
                mimetype="text/csv",
            )
        elif format_name == "docx":
            buf = export_docx(quiz, questions, style_profile)
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.docx",
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        elif format_name == "gift":
            gift_str = export_gift(quiz, questions)
            buf = BytesIO(gift_str.encode("utf-8"))
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.gift.txt",
                mimetype="text/plain",
            )
        elif format_name == "pdf":
            buf = export_pdf(quiz, questions, style_profile)
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.pdf",
                mimetype="application/pdf",
            )
        elif format_name == "qti":
            buf = export_qti(quiz, questions)
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.qti.zip",
                mimetype="application/zip",
            )

    # --- Quiz Editing API ---

    ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

    @app.route("/api/quizzes/<int:quiz_id>/title", methods=["PUT"])
    @login_required
    def api_quiz_title(quiz_id):
        """Update quiz title."""
        session = _get_session()
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            return jsonify({"ok": False, "error": "Quiz not found"}), 404
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"ok": False, "error": "Title cannot be empty"}), 400
        quiz.title = title
        session.commit()
        return jsonify({"ok": True, "title": quiz.title})

    @app.route("/api/questions/<int:question_id>", methods=["PUT"])
    @login_required
    def api_question_edit(question_id):
        """Update question text, points, type, options, correct answer."""
        session = _get_session()
        question = session.query(Question).filter_by(id=question_id).first()
        if not question:
            return jsonify({"ok": False, "error": "Question not found"}), 404
        payload = request.get_json(silent=True) or {}

        # Update scalar fields
        if "text" in payload:
            text = (payload["text"] or "").strip()
            if not text:
                return jsonify({"ok": False, "error": "Question text cannot be empty"}), 400
            question.text = text
        if "points" in payload:
            question.points = float(payload["points"])
        if "question_type" in payload:
            question.question_type = payload["question_type"]

        # Merge into data JSON
        q_data = question.data
        if isinstance(q_data, str):
            q_data = json.loads(q_data)
        if not isinstance(q_data, dict):
            q_data = {}

        if "text" in payload:
            q_data["text"] = question.text
        if "question_type" in payload:
            q_data["type"] = payload["question_type"]
        if "options" in payload:
            q_data["options"] = payload["options"]
        if "correct_index" in payload:
            q_data["correct_index"] = payload["correct_index"]
        if "correct_answer" in payload:
            q_data["correct_answer"] = payload["correct_answer"]
        if "points" in payload:
            q_data["points"] = question.points

        question.data = q_data
        # Force SQLAlchemy to detect the JSON change
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(question, "data")
        session.commit()

        return jsonify(
            {
                "ok": True,
                "question": {
                    "id": question.id,
                    "text": question.text,
                    "points": question.points,
                    "question_type": question.question_type,
                    "data": question.data,
                },
            }
        )

    @app.route("/api/questions/<int:question_id>", methods=["DELETE"])
    @login_required
    def api_question_delete(question_id):
        """Delete a question from its quiz."""
        session = _get_session()
        question = session.query(Question).filter_by(id=question_id).first()
        if not question:
            return jsonify({"ok": False, "error": "Question not found"}), 404
        session.delete(question)
        session.commit()
        return jsonify({"ok": True})

    @app.route("/api/quizzes/<int:quiz_id>/reorder", methods=["PUT"])
    @login_required
    def api_quiz_reorder(quiz_id):
        """Reorder questions within a quiz."""
        session = _get_session()
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            return jsonify({"ok": False, "error": "Quiz not found"}), 404
        payload = request.get_json(silent=True) or {}
        question_ids = payload.get("question_ids", [])

        # Validate: the IDs must exactly match the quiz's question IDs
        actual_ids = set(row[0] for row in session.query(Question.id).filter_by(quiz_id=quiz_id).all())
        if set(question_ids) != actual_ids:
            return jsonify({"ok": False, "error": "Question IDs do not match quiz"}), 400

        for idx, qid in enumerate(question_ids):
            session.query(Question).filter_by(id=qid).update({"sort_order": idx})
        session.commit()
        return jsonify({"ok": True})

    @app.route("/api/questions/<int:question_id>/image", methods=["POST"])
    @login_required
    def api_question_image_upload(question_id):
        """Upload an image for a question."""
        session = _get_session()
        question = session.query(Question).filter_by(id=question_id).first()
        if not question:
            return jsonify({"ok": False, "error": "Question not found"}), 404

        if "image" not in request.files:
            return jsonify({"ok": False, "error": "No image file provided"}), 400
        file = request.files["image"]
        if not file.filename:
            return jsonify({"ok": False, "error": "No image file provided"}), 400

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify(
                {"ok": False, "error": f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"}
            ), 400

        safe_name = secure_filename(file.filename)
        # Add question_id prefix to avoid collisions
        filename = f"upload_{question_id}_{safe_name}"

        config = current_app.config["APP_CONFIG"]
        images_dir = os.path.abspath(config.get("paths", {}).get("generated_images_dir", "generated_images"))
        os.makedirs(images_dir, exist_ok=True)
        file.save(os.path.join(images_dir, filename))

        # Update question data
        q_data = question.data
        if isinstance(q_data, str):
            q_data = json.loads(q_data)
        if not isinstance(q_data, dict):
            q_data = {}
        q_data["image_ref"] = filename
        q_data.pop("image_description", None)

        question.data = q_data
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(question, "data")
        session.commit()

        return jsonify({"ok": True, "image_ref": filename})

    @app.route("/api/questions/<int:question_id>/image", methods=["DELETE"])
    @login_required
    def api_question_image_remove(question_id):
        """Remove image reference from a question (does not delete file)."""
        session = _get_session()
        question = session.query(Question).filter_by(id=question_id).first()
        if not question:
            return jsonify({"ok": False, "error": "Question not found"}), 404

        q_data = question.data
        if isinstance(q_data, str):
            q_data = json.loads(q_data)
        if not isinstance(q_data, dict):
            q_data = {}
        q_data.pop("image_ref", None)

        question.data = q_data
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(question, "data")
        session.commit()

        return jsonify({"ok": True})

    @app.route("/api/questions/<int:question_id>/regenerate", methods=["POST"])
    @login_required
    def api_question_regenerate(question_id):
        """Regenerate a single question using the LLM."""
        session = _get_session()
        question = session.query(Question).filter_by(id=question_id).first()
        if not question:
            return jsonify({"ok": False, "error": "Question not found"}), 404

        payload = request.get_json(silent=True) or {}
        teacher_notes = (payload.get("teacher_notes") or "").strip()

        config = current_app.config["APP_CONFIG"]
        from src.question_regenerator import regenerate_question

        result = regenerate_question(session, question_id, teacher_notes, config)
        if result is None:
            return jsonify({"ok": False, "error": "Regeneration failed"}), 500

        return jsonify(
            {
                "ok": True,
                "question": {
                    "id": result.id,
                    "text": result.text,
                    "points": result.points,
                    "question_type": result.question_type,
                    "data": result.data
                    if isinstance(result.data, dict)
                    else json.loads(result.data)
                    if isinstance(result.data, str)
                    else {},
                },
            }
        )

    # --- Quiz Generation ---

    @app.route("/generate")
    @login_required
    def generate_redirect():
        """Redirect /generate to the active class's generate page, or class list."""
        session = _get_session()
        classes = list_classes(session)
        if classes:
            return redirect(f"/classes/{classes[0]['id']}/generate")
        flash("Create a class first before generating a quiz.", "info")
        return redirect("/classes/new")

    @app.route("/classes/<int:class_id>/generate", methods=["GET", "POST"])
    @login_required
    def quiz_generate(class_id):
        """Generate a quiz for a class via form POST or render the form on GET."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        config = current_app.config["APP_CONFIG"]

        if request.method == "POST":
            num_questions = int(request.form.get("num_questions", 20))
            grade_level = request.form.get("grade_level", "").strip() or None
            sol_raw = request.form.get("sol_standards", "").strip()
            sol_standards = [s.strip() for s in sol_raw.split(",") if s.strip()] if sol_raw else None

            # Parse cognitive framework fields
            cognitive_framework = request.form.get("cognitive_framework", "").strip() or None
            cognitive_distribution = None
            dist_raw = request.form.get("cognitive_distribution", "").strip()
            if dist_raw:
                try:
                    cognitive_distribution = json.loads(dist_raw)
                except (json.JSONDecodeError, ValueError):
                    cognitive_distribution = None
            difficulty = int(request.form.get("difficulty", 3))

            # Per-quiz provider override
            provider_override = request.form.get("provider", "").strip() or None

            try:
                quiz = generate_quiz(
                    session,
                    class_id=class_id,
                    config=config,
                    num_questions=num_questions,
                    grade_level=grade_level,
                    sol_standards=sol_standards,
                    cognitive_framework=cognitive_framework,
                    cognitive_distribution=cognitive_distribution,
                    difficulty=difficulty,
                    provider_name=provider_override,
                )
            except Exception as e:
                quiz = None
                flash(f"Quiz generation error: {e}", "error")

            if quiz:
                flash("Quiz generated successfully.", "success")
                return redirect(url_for("quiz_detail", quiz_id=quiz.id), code=303)
            else:
                providers = get_provider_info(config)
                current_provider = config.get("llm", {}).get("provider", "mock")
                return render_template(
                    "quizzes/generate.html",
                    class_obj=class_obj,
                    providers=providers,
                    current_provider=current_provider,
                    error="Quiz generation failed. Check your provider settings and try again.",
                )

        providers = get_provider_info(config)
        current_provider = config.get("llm", {}).get("provider", "mock")
        return render_template(
            "quizzes/generate.html",
            class_obj=class_obj,
            providers=providers,
            current_provider=current_provider,
        )

    # --- Costs ---

    @app.route("/costs", methods=["GET", "POST"])
    @login_required
    def costs():
        """Show API cost tracking dashboard with provider info and budget."""
        config = current_app.config["APP_CONFIG"]

        if request.method == "POST":
            budget_raw = request.form.get("monthly_budget", "").strip()
            try:
                budget_val = float(budget_raw) if budget_raw else 0
            except ValueError:
                budget_val = 0
            config.setdefault("llm", {})["monthly_budget"] = budget_val
            save_config(config)
            flash("Monthly budget updated.", "success")
            return redirect(url_for("costs"), code=303)

        provider = config.get("llm", {}).get("provider", "unknown")
        stats = get_cost_summary()
        budget = check_budget(config)
        monthly = get_monthly_total()
        return render_template(
            "costs.html",
            stats=stats,
            provider=provider,
            budget=budget,
            monthly=monthly,
        )

    # --- Settings ---

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        """Manage LLM provider settings."""
        config = current_app.config["APP_CONFIG"]

        if request.method == "POST":
            provider = request.form.get("provider", "mock").strip()
            model_name = request.form.get("model_name", "").strip()
            api_key = request.form.get("api_key", "").strip()
            base_url = request.form.get("base_url", "").strip()
            vertex_project_id = request.form.get("vertex_project_id", "").strip()
            vertex_location = request.form.get("vertex_location", "").strip()

            # Update config in-memory
            if "llm" not in config:
                config["llm"] = {}
            config["llm"]["provider"] = provider

            if model_name:
                config["llm"]["model_name"] = model_name
            if api_key:
                config["llm"]["api_key"] = api_key
            if base_url:
                config["llm"]["base_url"] = base_url
            elif provider not in ("openai-compatible",):
                # Clear base_url if not needed
                config["llm"].pop("base_url", None)
            if vertex_project_id:
                config["llm"]["vertex_project_id"] = vertex_project_id
            if vertex_location:
                config["llm"]["vertex_location"] = vertex_location

            # Persist to config.yaml
            save_config(config)

            flash("Settings saved successfully.", "success")
            return redirect(url_for("settings"), code=303)

        # GET: render settings page
        llm_config = config.get("llm", {})
        providers = get_provider_info(config)
        current_provider = llm_config.get("provider", "mock")

        return render_template(
            "settings.html",
            providers=providers,
            current_provider=current_provider,
            llm_config=llm_config,
            standard_sets=get_available_standard_sets(),
            current_standard_set=config.get("standard_set", "sol"),
        )

    # --- API Audit Log (E2E testing/transparency) ---

    @app.route("/api/audit-log")
    @login_required
    def api_audit_log():
        """Return the API call audit log for transparency reporting."""
        from src.llm_provider import get_api_audit_log

        return jsonify(get_api_audit_log())

    @app.route("/api/audit-log/clear", methods=["POST"])
    @login_required
    def clear_audit_log():
        """Clear the API call audit log."""
        from src.llm_provider import clear_api_audit_log

        clear_api_audit_log()
        return jsonify({"status": "cleared"})

    # --- Provider Setup Wizard ---

    @app.route("/settings/wizard")
    @login_required
    def provider_wizard():
        """Guided step-by-step provider setup wizard."""
        return render_template("provider_wizard.html")

    # --- Test Provider API ---

    @app.route("/api/settings/test-provider", methods=["POST"])
    @login_required
    def test_provider():
        """Test an LLM provider connection without saving settings."""
        import time

        data = request.get_json(silent=True) or {}
        provider_name = data.get("provider", "mock").strip()
        model_name = data.get("model_name", "").strip()
        api_key = data.get("api_key", "").strip()
        base_url = data.get("base_url", "").strip()
        vertex_project_id = data.get("vertex_project_id", "").strip()
        vertex_location = data.get("vertex_location", "").strip()

        # Mock provider: instant success
        if provider_name == "mock":
            return jsonify(
                {
                    "success": True,
                    "message": "Mock provider always available",
                    "latency_ms": 0,
                }
            )

        # Build temporary config (do NOT save)
        temp_config = {
            "llm": {
                "provider": provider_name,
                "mode": "production",  # skip interactive approval
            }
        }
        if model_name:
            temp_config["llm"]["model_name"] = model_name
        if api_key:
            temp_config["llm"]["api_key"] = api_key
        if base_url:
            temp_config["llm"]["base_url"] = base_url
        if vertex_project_id:
            temp_config["llm"]["vertex_project_id"] = vertex_project_id
        if vertex_location:
            temp_config["llm"]["vertex_location"] = vertex_location

        # Temporarily set env var for providers that need it
        old_env = {}
        try:
            if provider_name in ("gemini", "gemini-pro", "gemini-3-pro") and api_key:
                old_env["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY")
                os.environ["GEMINI_API_KEY"] = api_key
            elif provider_name == "openai" and api_key:
                old_env["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY")
                os.environ["OPENAI_API_KEY"] = api_key
            elif provider_name == "anthropic" and api_key:
                old_env["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY")
                os.environ["ANTHROPIC_API_KEY"] = api_key

            start = time.time()
            provider = get_provider(temp_config, web_mode=True)
            provider.generate(["Say hello in one sentence."])
            elapsed_ms = int((time.time() - start) * 1000)

            return jsonify(
                {
                    "success": True,
                    "message": f"Connected successfully ({elapsed_ms}ms)",
                    "latency_ms": elapsed_ms,
                }
            )
        except Exception as e:
            error_msg = str(e)
            # Add helpful context for common errors
            lower_msg = error_msg.lower()
            if "401" in error_msg or "unauthorized" in lower_msg or "invalid" in lower_msg and "key" in lower_msg:
                error_msg += " -- Check that your API key is correct and has not expired."
            elif "403" in error_msg or "forbidden" in lower_msg:
                error_msg += " -- Your API key may not have permission for this model. Check your account settings."
            elif "404" in error_msg or "not found" in lower_msg:
                error_msg += (
                    " -- The model name may be incorrect. Check the model name in your provider's documentation."
                )
            elif "429" in error_msg or "rate" in lower_msg or "quota" in lower_msg:
                error_msg += " -- You've hit a rate limit or quota. Wait a moment and try again, or check your billing."
            elif "timeout" in lower_msg or "timed out" in lower_msg:
                error_msg += " -- The provider took too long to respond. Check your internet connection."
            elif "connection" in lower_msg or "refused" in lower_msg:
                error_msg += (
                    " -- Could not reach the provider. Check your internet connection and the API endpoint URL."
                )
            return jsonify(
                {
                    "success": False,
                    "message": error_msg,
                    "latency_ms": 0,
                }
            )
        finally:
            # Restore env vars
            for key, val in old_env.items():
                if val is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = val

    # --- Study Materials ---

    @app.route("/study")
    @login_required
    def study_list():
        """List study sets, optionally filtered by class, type, or search."""
        session = _get_session()
        query = session.query(StudySet)

        class_id_filter = request.args.get("class_id", type=int)
        type_filter = request.args.get("type")
        search_q = request.args.get("q", "").strip()
        if class_id_filter:
            query = query.filter(StudySet.class_id == class_id_filter)
        if type_filter:
            query = query.filter(StudySet.material_type == type_filter)
        if search_q:
            query = query.filter(StudySet.title.ilike(f"%{search_q}%"))

        study_sets = query.order_by(StudySet.created_at.desc()).all()

        set_data = []
        for ss in study_sets:
            class_obj = get_class(session, ss.class_id) if ss.class_id else None
            card_count = session.query(StudyCard).filter_by(study_set_id=ss.id).count()
            set_data.append(
                {
                    "id": ss.id,
                    "title": ss.title,
                    "material_type": ss.material_type,
                    "status": ss.status,
                    "class_name": class_obj.name if class_obj else "N/A",
                    "card_count": card_count,
                    "created_at": ss.created_at,
                }
            )

        classes = list_classes(session)
        return render_template(
            "study/list.html",
            study_sets=set_data,
            classes=classes,
            current_class_id=class_id_filter,
            current_type=type_filter,
            search_q=search_q,
        )

    @app.route("/study/generate", methods=["GET", "POST"])
    @login_required
    def study_generate():
        """Generate study material via form POST or render form on GET."""
        session = _get_session()
        config = current_app.config["APP_CONFIG"]
        classes = list_classes(session)
        providers = get_provider_info(config)
        current_provider = config.get("llm", {}).get("provider", "mock")

        if request.method == "POST":
            class_id = request.form.get("class_id", type=int)
            material_type = request.form.get("material_type", "flashcard").strip()
            quiz_id = request.form.get("quiz_id", type=int) or None
            topic = request.form.get("topic", "").strip() or None
            title = request.form.get("title", "").strip() or None
            provider_override = request.form.get("provider", "").strip() or None

            if not class_id:
                return render_template(
                    "study/generate.html",
                    classes=classes,
                    providers=providers,
                    current_provider=current_provider,
                    error="Please select a class.",
                ), 400

            try:
                study_set = generate_study_material(
                    session,
                    class_id=class_id,
                    material_type=material_type,
                    config=config,
                    quiz_id=quiz_id,
                    topic=topic,
                    title=title,
                    provider_name=provider_override,
                )
            except Exception as e:
                study_set = None
                flash(f"Study material generation error: {e}", "error")

            if study_set:
                flash("Study material generated successfully.", "success")
                return redirect(url_for("study_detail", study_set_id=study_set.id), code=303)
            else:
                return render_template(
                    "study/generate.html",
                    classes=classes,
                    providers=providers,
                    current_provider=current_provider,
                    error="Generation failed. Check your provider settings and try again.",
                ), 500

        return render_template(
            "study/generate.html",
            classes=classes,
            providers=providers,
            current_provider=current_provider,
        )

    @app.route("/study/<int:study_set_id>")
    @login_required
    def study_detail(study_set_id):
        """Show study set detail with all cards."""
        session = _get_session()
        study_set = session.query(StudySet).filter_by(id=study_set_id).first()
        if not study_set:
            abort(404)

        cards = (
            session.query(StudyCard)
            .filter_by(study_set_id=study_set_id)
            .order_by(StudyCard.sort_order, StudyCard.id)
            .all()
        )
        class_obj = get_class(session, study_set.class_id) if study_set.class_id else None

        # Parse card data for template
        parsed_cards = []
        for card in cards:
            card_data = card.data
            if isinstance(card_data, str):
                try:
                    card_data = json.loads(card_data)
                except (json.JSONDecodeError, ValueError):
                    card_data = {}
            if not isinstance(card_data, dict):
                card_data = {}
            parsed_cards.append(
                {
                    "id": card.id,
                    "card_type": card.card_type,
                    "sort_order": card.sort_order,
                    "front": card.front,
                    "back": card.back,
                    "data": card_data,
                }
            )

        return render_template(
            "study/detail.html",
            study_set=study_set,
            cards=parsed_cards,
            class_obj=class_obj,
        )

    @app.route("/study/<int:study_set_id>/export/<format_name>")
    @login_required
    def study_export(study_set_id, format_name):
        """Download study material in the requested format."""
        if format_name not in ("tsv", "csv", "pdf", "docx"):
            abort(404)

        session = _get_session()
        study_set = session.query(StudySet).filter_by(id=study_set_id).first()
        if not study_set:
            abort(404)

        cards = (
            session.query(StudyCard)
            .filter_by(study_set_id=study_set_id)
            .order_by(StudyCard.sort_order, StudyCard.id)
            .all()
        )

        # Sanitize title for filename
        safe_title = re.sub(r"[^\w\s\-]", "", study_set.title or "study")
        safe_title = re.sub(r"\s+", "_", safe_title.strip())[:80] or "study"

        if format_name == "tsv":
            tsv_str = export_flashcards_tsv(study_set, cards)
            buf = BytesIO(tsv_str.encode("utf-8"))
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.tsv",
                mimetype="text/tab-separated-values",
            )
        elif format_name == "csv":
            csv_str = export_flashcards_csv(study_set, cards)
            buf = BytesIO(csv_str.encode("utf-8"))
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.csv",
                mimetype="text/csv",
            )
        elif format_name == "pdf":
            buf = export_study_pdf(study_set, cards)
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.pdf",
                mimetype="application/pdf",
            )
        elif format_name == "docx":
            buf = export_study_docx(study_set, cards)
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.docx",
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

    @app.route("/api/study-sets/<int:study_set_id>", methods=["DELETE"])
    @login_required
    def api_study_set_delete(study_set_id):
        """Delete a study set and all its cards."""
        session = _get_session()
        study_set = session.query(StudySet).filter_by(id=study_set_id).first()
        if not study_set:
            return jsonify({"ok": False, "error": "Study set not found"}), 404

        # Cards are cascade-deleted via relationship
        session.delete(study_set)
        session.commit()
        return jsonify({"ok": True})

    @app.route("/api/study-cards/<int:card_id>", methods=["PUT"])
    @login_required
    def api_study_card_update(card_id):
        """Update a study card's front, back, or data fields."""
        session = _get_session()
        card = session.query(StudyCard).filter_by(id=card_id).first()
        if not card:
            return jsonify({"ok": False, "error": "Card not found"}), 404

        payload = request.get_json(silent=True) or {}
        if "front" in payload:
            card.front = payload["front"]
        if "back" in payload:
            card.back = payload["back"]
        if "data" in payload:
            card.data = json.dumps(payload["data"]) if isinstance(payload["data"], dict) else payload["data"]
        session.commit()
        return jsonify(
            {
                "ok": True,
                "card": {
                    "id": card.id,
                    "front": card.front,
                    "back": card.back,
                },
            }
        )

    @app.route("/api/study-cards/<int:card_id>", methods=["DELETE"])
    @login_required
    def api_study_card_delete(card_id):
        """Delete a single study card."""
        session = _get_session()
        card = session.query(StudyCard).filter_by(id=card_id).first()
        if not card:
            return jsonify({"ok": False, "error": "Card not found"}), 404
        session.delete(card)
        session.commit()
        return jsonify({"ok": True})

    @app.route("/api/study-sets/<int:study_set_id>/reorder", methods=["POST"])
    @login_required
    def api_study_set_reorder(study_set_id):
        """Reorder cards within a study set."""
        session = _get_session()
        study_set = session.query(StudySet).filter_by(id=study_set_id).first()
        if not study_set:
            return jsonify({"ok": False, "error": "Study set not found"}), 404

        payload = request.get_json(silent=True) or {}
        card_ids = payload.get("card_ids", [])
        if not card_ids:
            return jsonify({"ok": False, "error": "No card_ids provided"}), 400

        cards = (
            session.query(StudyCard)
            .filter(
                StudyCard.study_set_id == study_set_id,
                StudyCard.id.in_(card_ids),
            )
            .all()
        )
        card_map = {c.id: c for c in cards}
        for i, cid in enumerate(card_ids):
            if cid in card_map:
                card_map[cid].sort_order = i
        session.commit()
        return jsonify({"ok": True})

    @app.route("/api/classes/<int:class_id>/quizzes")
    @login_required
    def api_class_quizzes(class_id):
        """Return quizzes for a class as JSON (used by study generate form)."""
        session = _get_session()
        quizzes = session.query(Quiz).filter_by(class_id=class_id).order_by(Quiz.created_at.desc()).all()
        result = []
        for q in quizzes:
            q_count = len(q.questions) if q.questions else 0
            date_str = q.created_at.strftime("%b %d") if q.created_at else ""
            # Extract standards from style_profile if available
            standards = []
            if q.style_profile:
                sp = q.style_profile if isinstance(q.style_profile, dict) else {}
                if isinstance(q.style_profile, str):
                    try:
                        sp = json.loads(q.style_profile)
                    except (json.JSONDecodeError, TypeError):
                        sp = {}
                standards = sp.get("sol_standards", []) or []
            result.append(
                {
                    "id": q.id,
                    "title": q.title or f"Quiz #{q.id}",
                    "question_count": q_count,
                    "date": date_str,
                    "standards": standards[:3],
                    "reading_level": q.reading_level or "",
                }
            )
        return jsonify(result)

    # --- Question Bank ---

    @app.route("/question-bank")
    @login_required
    def question_bank():
        """Show saved questions from the question bank."""
        session = _get_session()
        query = session.query(Question).filter(Question.saved_to_bank == 1)

        # Filters
        q_type = request.args.get("type", "")
        search = request.args.get("search", "")

        if q_type:
            query = query.filter(Question.question_type == q_type)
        if search:
            query = query.filter(Question.text.ilike(f"%{search}%"))

        questions = query.order_by(Question.id.desc()).all()

        parsed = []
        for q in questions:
            data = q.data
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, ValueError):
                    data = {}
            if not isinstance(data, dict):
                data = {}
            quiz = session.query(Quiz).filter_by(id=q.quiz_id).first() if q.quiz_id else None
            parsed.append(
                {
                    "id": q.id,
                    "type": q.question_type,
                    "text": q.text,
                    "points": q.points,
                    "data": data,
                    "quiz_title": quiz.title if quiz else "N/A",
                    "quiz_id": q.quiz_id,
                }
            )

        return render_template(
            "question_bank.html",
            questions=parsed,
            search=search,
            q_type=q_type,
        )

    @app.route("/api/question-bank/add", methods=["POST"])
    @login_required
    def api_question_bank_add():
        """Save a question to the question bank."""
        payload = request.get_json(silent=True) or {}
        question_id = payload.get("question_id")
        if not question_id:
            return jsonify({"ok": False, "error": "question_id required"}), 400

        session = _get_session()
        q = session.query(Question).filter_by(id=question_id).first()
        if not q:
            return jsonify({"ok": False, "error": "Question not found"}), 404

        q.saved_to_bank = 1
        session.commit()
        return jsonify({"ok": True})

    @app.route("/api/question-bank/remove", methods=["POST"])
    @login_required
    def api_question_bank_remove():
        """Remove a question from the question bank."""
        payload = request.get_json(silent=True) or {}
        question_id = payload.get("question_id")
        if not question_id:
            return jsonify({"ok": False, "error": "question_id required"}), 400

        session = _get_session()
        q = session.query(Question).filter_by(id=question_id).first()
        if not q:
            return jsonify({"ok": False, "error": "Question not found"}), 404

        q.saved_to_bank = 0
        session.commit()
        return jsonify({"ok": True})

    # --- Variants ---

    @app.route("/quizzes/<int:quiz_id>/generate-variant", methods=["GET", "POST"])
    @login_required
    def quiz_generate_variant(quiz_id):
        """Generate a reading-level variant of a quiz."""
        session = _get_session()
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            abort(404)

        config = current_app.config["APP_CONFIG"]
        providers = get_provider_info(config)
        current_provider = config.get("llm", {}).get("provider", "mock")

        if request.method == "POST":
            reading_level = request.form.get("reading_level", "").strip()
            title = request.form.get("title", "").strip() or None
            provider_override = request.form.get("provider", "").strip() or None

            if reading_level not in READING_LEVELS:
                return render_template(
                    "quizzes/generate_variant.html",
                    quiz=quiz,
                    reading_levels=READING_LEVELS,
                    providers=providers,
                    current_provider=current_provider,
                    error="Please select a valid reading level.",
                ), 400

            try:
                variant = generate_variant(
                    session,
                    quiz_id=quiz_id,
                    reading_level=reading_level,
                    config=config,
                    title=title,
                    provider_name=provider_override,
                )
            except Exception as e:
                variant = None
                flash(f"Variant generation error: {e}", "error")

            if variant:
                flash("Variant generated successfully.", "success")
                return redirect(url_for("quiz_detail", quiz_id=variant.id), code=303)
            else:
                return render_template(
                    "quizzes/generate_variant.html",
                    quiz=quiz,
                    reading_levels=READING_LEVELS,
                    providers=providers,
                    current_provider=current_provider,
                    error="Variant generation failed. Check your provider settings and try again.",
                ), 500

        return render_template(
            "quizzes/generate_variant.html",
            quiz=quiz,
            reading_levels=READING_LEVELS,
            providers=providers,
            current_provider=current_provider,
        )

    @app.route("/quizzes/<int:quiz_id>/variants")
    @login_required
    def quiz_variants(quiz_id):
        """List all variants of a quiz."""
        session = _get_session()
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            abort(404)

        variants = session.query(Quiz).filter_by(parent_quiz_id=quiz_id).order_by(Quiz.created_at.desc()).all()
        variant_data = []
        for v in variants:
            question_count = session.query(Question).filter_by(quiz_id=v.id).count()
            variant_data.append(
                {
                    "id": v.id,
                    "title": v.title,
                    "reading_level": v.reading_level,
                    "status": v.status,
                    "question_count": question_count,
                    "created_at": v.created_at,
                }
            )

        return render_template(
            "quizzes/variants.html",
            quiz=quiz,
            variants=variant_data,
        )

    # --- Rubrics ---

    @app.route("/quizzes/<int:quiz_id>/generate-rubric", methods=["GET", "POST"])
    @login_required
    def quiz_generate_rubric(quiz_id):
        """Generate a scoring rubric for a quiz."""
        session = _get_session()
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            abort(404)

        config = current_app.config["APP_CONFIG"]
        providers = get_provider_info(config)
        current_provider = config.get("llm", {}).get("provider", "mock")

        if request.method == "POST":
            title = request.form.get("title", "").strip() or None
            provider_override = request.form.get("provider", "").strip() or None

            try:
                rubric = generate_rubric(
                    session,
                    quiz_id=quiz_id,
                    config=config,
                    title=title,
                    provider_name=provider_override,
                )
            except Exception as e:
                rubric = None
                flash(f"Rubric generation error: {e}", "error")

            if rubric:
                flash("Rubric generated successfully.", "success")
                return redirect(url_for("rubric_detail", rubric_id=rubric.id), code=303)
            else:
                return render_template(
                    "quizzes/generate_rubric.html",
                    quiz=quiz,
                    providers=providers,
                    current_provider=current_provider,
                    error="Rubric generation failed. Check your provider settings and try again.",
                ), 500

        return render_template(
            "quizzes/generate_rubric.html",
            quiz=quiz,
            providers=providers,
            current_provider=current_provider,
        )

    @app.route("/rubrics/<int:rubric_id>")
    @login_required
    def rubric_detail(rubric_id):
        """View rubric detail with all criteria and proficiency levels."""
        session = _get_session()
        rubric = session.query(Rubric).filter_by(id=rubric_id).first()
        if not rubric:
            abort(404)

        criteria = (
            session.query(RubricCriterion)
            .filter_by(rubric_id=rubric_id)
            .order_by(RubricCriterion.sort_order, RubricCriterion.id)
            .all()
        )

        quiz = session.query(Quiz).filter_by(id=rubric.quiz_id).first()

        # Parse levels JSON for template
        parsed_criteria = []
        for c in criteria:
            levels = c.levels
            if isinstance(levels, str):
                try:
                    levels = json.loads(levels)
                except (json.JSONDecodeError, ValueError):
                    levels = []
            if not isinstance(levels, list):
                levels = []
            parsed_criteria.append(
                {
                    "id": c.id,
                    "criterion": c.criterion,
                    "description": c.description,
                    "max_points": c.max_points,
                    "levels": levels,
                }
            )

        total_points = sum(c.max_points or 0 for c in criteria)

        return render_template(
            "rubrics/detail.html",
            rubric=rubric,
            criteria=parsed_criteria,
            quiz=quiz,
            total_points=total_points,
        )

    @app.route("/rubrics/<int:rubric_id>/export/<format_name>")
    @login_required
    def rubric_export(rubric_id, format_name):
        """Download a rubric in the requested format (pdf, docx, csv)."""
        if format_name not in ("pdf", "docx", "csv"):
            abort(404)

        session = _get_session()
        rubric = session.query(Rubric).filter_by(id=rubric_id).first()
        if not rubric:
            abort(404)

        criteria = (
            session.query(RubricCriterion)
            .filter_by(rubric_id=rubric_id)
            .order_by(RubricCriterion.sort_order, RubricCriterion.id)
            .all()
        )

        # Sanitize title for filename
        safe_title = re.sub(r"[^\w\s\-]", "", rubric.title or "rubric")
        safe_title = re.sub(r"\s+", "_", safe_title.strip())[:80] or "rubric"

        if format_name == "csv":
            csv_str = export_rubric_csv(rubric, criteria)
            buf = BytesIO(csv_str.encode("utf-8"))
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.csv",
                mimetype="text/csv",
            )
        elif format_name == "docx":
            buf = export_rubric_docx(rubric, criteria)
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.docx",
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        elif format_name == "pdf":
            buf = export_rubric_pdf(rubric, criteria)
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{safe_title}.pdf",
                mimetype="application/pdf",
            )

    @app.route("/api/rubrics/<int:rubric_id>", methods=["DELETE"])
    @login_required
    def api_rubric_delete(rubric_id):
        """Delete a rubric and all its criteria."""
        session = _get_session()
        rubric = session.query(Rubric).filter_by(id=rubric_id).first()
        if not rubric:
            return jsonify({"ok": False, "error": "Rubric not found"}), 404

        # Criteria are cascade-deleted via relationship
        session.delete(rubric)
        session.commit()
        return jsonify({"ok": True})

    # --- Performance Analytics ---

    @app.route("/classes/<int:class_id>/analytics")
    @login_required
    def analytics_dashboard(class_id):
        """Analytics dashboard with gap analysis, charts, and data table."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        gap_data = compute_gap_analysis(session, class_id)
        summary = get_class_summary(session, class_id)
        standards_mastery = get_standards_mastery(session, class_id)

        recent_data = (
            session.query(PerformanceData)
            .filter_by(class_id=class_id)
            .order_by(PerformanceData.date.desc())
            .limit(50)
            .all()
        )

        return render_template(
            "analytics/dashboard.html",
            class_obj=class_obj,
            gap_data=gap_data,
            summary=summary,
            standards_mastery=standards_mastery,
            recent_data=recent_data,
        )

    @app.route("/classes/<int:class_id>/analytics/import", methods=["GET", "POST"])
    @login_required
    def analytics_import(class_id):
        """CSV upload form and processing."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        quizzes = session.query(Quiz).filter_by(class_id=class_id).order_by(Quiz.created_at.desc()).all()

        if request.method == "POST":
            csv_file = request.files.get("csv_file")
            if not csv_file or not csv_file.filename:
                return render_template(
                    "analytics/import.html",
                    class_obj=class_obj,
                    quizzes=quizzes,
                    error="Please select a CSV file.",
                ), 400

            # Validate extension
            if not csv_file.filename.lower().endswith(".csv"):
                return render_template(
                    "analytics/import.html",
                    class_obj=class_obj,
                    quizzes=quizzes,
                    error="File must be a .csv file.",
                ), 400

            csv_text = csv_file.read().decode("utf-8", errors="replace")
            quiz_id = request.form.get("quiz_id", type=int) or None

            count, errors = import_csv_data(session, class_id, csv_text, quiz_id)

            if count > 0:
                flash(f"Imported {count} performance record(s).", "success")
            if errors:
                return render_template(
                    "analytics/import.html",
                    class_obj=class_obj,
                    quizzes=quizzes,
                    errors=errors,
                )
            if count > 0:
                return redirect(url_for("analytics_dashboard", class_id=class_id), code=303)

            return render_template(
                "analytics/import.html",
                class_obj=class_obj,
                quizzes=quizzes,
                error="No valid rows found in CSV.",
            ), 400

        return render_template(
            "analytics/import.html",
            class_obj=class_obj,
            quizzes=quizzes,
        )

    @app.route("/classes/<int:class_id>/analytics/manual", methods=["GET", "POST"])
    @login_required
    def analytics_manual(class_id):
        """Manual score entry form."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        knowledge = get_assumed_knowledge(session, class_id)
        known_topics = sorted(knowledge.keys()) if knowledge else []

        if request.method == "POST":
            topic = request.form.get("topic", "").strip()
            score_raw = request.form.get("score", "").strip()
            standard = request.form.get("standard", "").strip() or None
            date_raw = request.form.get("date", "").strip()
            sample_size_raw = request.form.get("sample_size", "0").strip()
            weak_areas_raw = request.form.get("weak_areas", "").strip()

            if not topic or not score_raw:
                return render_template(
                    "analytics/manual_entry.html",
                    class_obj=class_obj,
                    known_topics=known_topics,
                    today=date.today().isoformat(),
                    error="Topic and score are required.",
                ), 400

            try:
                score = float(score_raw)
                if score < 0 or score > 100:
                    raise ValueError("out of range")
            except ValueError:
                return render_template(
                    "analytics/manual_entry.html",
                    class_obj=class_obj,
                    known_topics=known_topics,
                    today=date.today().isoformat(),
                    error="Score must be a number between 0 and 100.",
                ), 400

            from datetime import datetime as dt

            parsed_date = date.today()
            if date_raw:
                try:
                    parsed_date = dt.strptime(date_raw, "%Y-%m-%d").date()
                except ValueError:
                    parsed_date = date.today()

            sample_size = int(sample_size_raw) if sample_size_raw.isdigit() else 0

            weak_areas = [w.strip() for w in weak_areas_raw.split(";") if w.strip()] if weak_areas_raw else []

            record = PerformanceData(
                class_id=class_id,
                topic=topic,
                avg_score=score / 100.0,
                standard=standard,
                source="manual_entry",
                sample_size=sample_size,
                date=parsed_date,
                weak_areas=json.dumps(weak_areas) if weak_areas else None,
            )
            session.add(record)
            session.commit()

            flash("Score saved successfully.", "success")
            return redirect(url_for("analytics_dashboard", class_id=class_id), code=303)

        return render_template(
            "analytics/manual_entry.html",
            class_obj=class_obj,
            known_topics=known_topics,
            today=date.today().isoformat(),
        )

    @app.route("/classes/<int:class_id>/analytics/quiz-scores", methods=["GET", "POST"])
    @login_required
    def analytics_quiz_scores(class_id):
        """Per-question quiz score entry form."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        quizzes = session.query(Quiz).filter_by(class_id=class_id).order_by(Quiz.created_at.desc()).all()

        if request.method == "POST":
            quiz_id = request.form.get("quiz_id", type=int)
            sample_size_raw = request.form.get("sample_size", "0").strip()
            date_raw = request.form.get("date", "").strip()

            if not quiz_id:
                return render_template(
                    "analytics/quiz_scores.html",
                    class_obj=class_obj,
                    quizzes=quizzes,
                    today=date.today().isoformat(),
                    error="Please select a quiz.",
                ), 400

            sample_size = int(sample_size_raw) if sample_size_raw.isdigit() else 0

            from datetime import datetime as dt

            score_date = date.today()
            if date_raw:
                try:
                    score_date = dt.strptime(date_raw, "%Y-%m-%d").date()
                except ValueError:
                    pass

            # Collect question scores from form (q_<id> fields)
            question_scores = {}
            for key, value in request.form.items():
                if key.startswith("q_") and value.strip():
                    try:
                        qid = int(key[2:])
                        score = float(value.strip())
                        if 0 <= score <= 100:
                            question_scores[qid] = score
                    except (ValueError, IndexError):
                        continue

            if not question_scores:
                return render_template(
                    "analytics/quiz_scores.html",
                    class_obj=class_obj,
                    quizzes=quizzes,
                    today=date.today().isoformat(),
                    error="Please enter at least one question score.",
                ), 400

            count = import_quiz_scores(session, class_id, quiz_id, question_scores, sample_size, score_date)

            flash(f"Imported {count} performance record(s) from quiz scores.", "success")
            return redirect(url_for("analytics_dashboard", class_id=class_id), code=303)

        return render_template(
            "analytics/quiz_scores.html",
            class_obj=class_obj,
            quizzes=quizzes,
            today=date.today().isoformat(),
        )

    @app.route("/api/quizzes/<int:quiz_id>/questions")
    @login_required
    def api_quiz_questions(quiz_id):
        """Return quiz questions as JSON (for quiz score entry form)."""
        session = _get_session()
        questions = session.query(Question).filter_by(quiz_id=quiz_id).order_by(Question.sort_order, Question.id).all()
        return jsonify(
            {
                "questions": [
                    {"id": q.id, "text": q.text or f"Question #{q.id}", "type": q.question_type} for q in questions
                ]
            }
        )

    @app.route("/classes/<int:class_id>/analytics/reteach", methods=["GET", "POST"])
    @login_required
    def analytics_reteach(class_id):
        """Re-teach suggestions page."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        config = current_app.config["APP_CONFIG"]
        providers = get_provider_info(config)
        current_provider = config.get("llm", {}).get("provider", "mock")
        gap_summary = get_class_summary(session, class_id)
        suggestions = None

        if request.method == "POST":
            focus_raw = request.form.get("focus_topics", "").strip()
            focus_topics = [t.strip() for t in focus_raw.split(",") if t.strip()] if focus_raw else None
            max_suggestions = int(request.form.get("max_suggestions", 5))
            provider_override = request.form.get("provider", "").strip() or None

            suggestions = generate_reteach_suggestions(
                session,
                class_id,
                config,
                focus_topics=focus_topics,
                max_suggestions=max_suggestions,
                provider_name=provider_override,
            )
            if suggestions is None:
                return render_template(
                    "analytics/reteach.html",
                    class_obj=class_obj,
                    gap_summary=gap_summary,
                    providers=providers,
                    current_provider=current_provider,
                    error="Failed to generate suggestions. Please try again.",
                ), 500

        return render_template(
            "analytics/reteach.html",
            class_obj=class_obj,
            gap_summary=gap_summary,
            suggestions=suggestions,
            providers=providers,
            current_provider=current_provider,
        )

    @app.route("/api/classes/<int:class_id>/analytics")
    @login_required
    def api_analytics(class_id):
        """JSON endpoint for gap analysis data (Chart.js)."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            return jsonify({"error": "Class not found"}), 404

        gap_data = compute_gap_analysis(session, class_id)
        summary = get_class_summary(session, class_id)

        return jsonify(
            {
                "gap_data": gap_data,
                "summary": summary,
            }
        )

    @app.route("/api/classes/<int:class_id>/analytics/trends")
    @login_required
    def api_analytics_trends(class_id):
        """JSON endpoint for trend data (Chart.js)."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            return jsonify({"error": "Class not found"}), 404

        topic = request.args.get("topic")
        days = request.args.get("days", 90, type=int)

        trends = get_topic_trends(session, class_id, topic=topic, days=days)

        return jsonify({"trends": trends})

    @app.route("/api/performance/<int:perf_id>", methods=["DELETE"])
    @login_required
    def api_performance_delete(perf_id):
        """Delete a performance data record."""
        session = _get_session()
        record = session.query(PerformanceData).filter_by(id=perf_id).first()
        if not record:
            return jsonify({"ok": False, "error": "Record not found"}), 404

        session.delete(record)
        session.commit()
        return jsonify({"ok": True})

    @app.route("/classes/<int:class_id>/analytics/sample-csv")
    @login_required
    def analytics_sample_csv(class_id):
        """Download sample CSV template."""
        csv_str = get_sample_csv()
        buf = BytesIO(csv_str.encode("utf-8"))
        return send_file(
            buf,
            as_attachment=True,
            download_name="performance_data_template.csv",
            mimetype="text/csv",
        )

    # --- Topic-Based Generation ---

    @app.route("/generate/topics", methods=["GET", "POST"])
    @login_required
    def generate_from_topics_page():
        """Generate quizzes or study materials from topics."""
        session = _get_session()
        config = current_app.config["APP_CONFIG"]
        classes_list = list_classes(session)

        if not classes_list:
            flash("Create a class before generating content.", "warning")
            return redirect(url_for("classes_new"), code=303)

        selected_class_id = request.args.get("class_id", type=int) or classes_list[0]["id"]

        if request.method == "POST":
            class_id = request.form.get("class_id", type=int)
            topics_raw = request.form.get("topics", "").strip()
            output_type = request.form.get("output_type", "quiz")
            title = request.form.get("title", "").strip() or None

            if not topics_raw:
                return render_template(
                    "generate_topics.html",
                    classes=classes_list,
                    selected_class_id=class_id,
                    error="Please enter at least one topic.",
                )

            topics = [t.strip() for t in topics_raw.split(",") if t.strip()]

            if output_type == "quiz":
                num_questions = request.form.get("num_questions", 20, type=int)
                sol_raw = request.form.get("sol_standards", "")
                sol_standards = [s.strip() for s in sol_raw.split(",") if s.strip()] if sol_raw else None
                difficulty = request.form.get("difficulty", 3, type=int)

                try:
                    result = generate_from_topics(
                        session=session,
                        class_id=class_id,
                        topics=topics,
                        output_type="quiz",
                        config=config,
                        num_questions=num_questions,
                        sol_standards=sol_standards,
                        difficulty=difficulty,
                        title=title,
                    )
                except Exception as e:
                    result = None
                    flash(f"Quiz generation error: {e}", "error")

                if result:
                    flash("Quiz generated from topics!", "success")
                    return redirect(url_for("quiz_detail", quiz_id=result.id), code=303)
                else:
                    return render_template(
                        "generate_topics.html",
                        classes=classes_list,
                        selected_class_id=class_id,
                        error="Quiz generation failed. Check your provider settings and try again.",
                    )
            else:
                try:
                    result = generate_from_topics(
                        session=session,
                        class_id=class_id,
                        topics=topics,
                        output_type=output_type,
                        config=config,
                        title=title,
                    )
                except Exception as e:
                    result = None
                    flash(f"Generation error: {e}", "error")

                if result:
                    flash(f"{output_type.replace('_', ' ').title()} generated from topics!", "success")
                    return redirect(url_for("study_detail", study_id=result.id), code=303)
                else:
                    return render_template(
                        "generate_topics.html",
                        classes=classes_list,
                        selected_class_id=class_id,
                        error="Generation failed. Check your provider settings and try again.",
                    )

        return render_template(
            "generate_topics.html",
            classes=classes_list,
            selected_class_id=selected_class_id,
        )

    @app.route("/api/topics/search")
    @login_required
    def api_topics_search():
        """JSON API for topic autocomplete from lesson history."""
        session = _get_session()
        class_id = request.args.get("class_id", type=int)
        q = request.args.get("q", "").strip()

        if not class_id:
            return jsonify({"topics": []})

        topics = search_topics(session, class_id, q)
        return jsonify({"topics": topics[:20]})

    # --- Standards ---

    @app.route("/standards")
    @login_required
    def standards_page():
        """Browse and search educational standards."""
        config = current_app.config["APP_CONFIG"]
        session = _get_session()

        # Auto-load the configured standard set if table is empty
        total = standards_count(session)
        if total == 0:
            configured_set = config.get("standard_set", "sol")
            ensure_standard_set_loaded(session, configured_set)
            total = standards_count(session)

        q = request.args.get("q", "").strip()
        subject = request.args.get("subject", "").strip()
        grade_band = request.args.get("grade_band", "").strip()
        standard_set = request.args.get("standard_set", "").strip()

        # Resolve label for the selected set
        standard_set_label = ""
        if standard_set:
            ss_info = STANDARD_SETS.get(standard_set)
            standard_set_label = ss_info["label"] if ss_info else standard_set

        if q:
            results = search_standards(
                session,
                q,
                subject=subject or None,
                grade_band=grade_band or None,
                standard_set=standard_set or None,
            )
        else:
            results = list_standards(
                session,
                subject=subject or None,
                grade_band=grade_band or None,
                standard_set=standard_set or None,
            )

        loaded_sets = get_standard_sets_in_db(session)

        return render_template(
            "standards.html",
            standards=results,
            total_count=total,
            subjects=get_subjects(session, standard_set=standard_set or None),
            grade_bands=get_grade_bands(session, standard_set=standard_set or None),
            available_sets=get_available_standard_sets(),
            loaded_sets=loaded_sets,
            q=q,
            subject=subject,
            grade_band=grade_band,
            standard_set=standard_set,
            standard_set_label=standard_set_label,
        )

    @app.route("/api/standards/search")
    @login_required
    def api_standards_search():
        """JSON API for standards autocomplete search."""
        config = current_app.config["APP_CONFIG"]
        session = _get_session()

        # Auto-load the configured standard set if table is empty
        total = standards_count(session)
        if total == 0:
            configured_set = config.get("standard_set", "sol")
            ensure_standard_set_loaded(session, configured_set)

        q = request.args.get("q", "").strip()
        subject = request.args.get("subject", "").strip()
        grade_band = request.args.get("grade_band", "").strip()
        standard_set = request.args.get("standard_set", "").strip()

        if not q:
            return jsonify({"results": []})

        results = search_standards(
            session,
            q,
            subject=subject or None,
            grade_band=grade_band or None,
            standard_set=standard_set or None,
        )
        return jsonify(
            {
                "results": [
                    {
                        "id": std.id,
                        "code": std.code,
                        "description": std.description,
                        "subject": std.subject,
                        "grade_band": std.grade_band,
                        "strand": std.strand,
                        "standard_set": std.standard_set or "sol",
                    }
                    for std in results[:20]  # Limit autocomplete results
                ]
            }
        )

    @app.route("/settings/standards", methods=["POST"])
    @login_required
    def settings_standards():
        """Save the selected standard set and auto-load it."""
        config = current_app.config["APP_CONFIG"]
        selected_set = request.form.get("standard_set", "sol")
        config["standard_set"] = selected_set
        save_config(config)

        # Auto-load the selected set
        session = _get_session()
        loaded = ensure_standard_set_loaded(session, selected_set)
        set_label = STANDARD_SETS.get(selected_set, {}).get("label", selected_set)

        if loaded > 0:
            flash(f"Loaded {loaded} standards from {set_label}.", "success")
        else:
            flash(f"Standards set updated to {set_label}.", "success")

        return redirect(url_for("settings"))

    # --- Lesson Plan Routes ---

    @app.route("/lesson-plans")
    @login_required
    def lesson_plan_list():
        """List lesson plans, optionally filtered by class or search."""
        session = _get_session()
        from src.database import LessonPlan

        query = session.query(LessonPlan)

        class_id_filter = request.args.get("class_id", type=int)
        search_q = request.args.get("q", "").strip()
        if class_id_filter:
            query = query.filter(LessonPlan.class_id == class_id_filter)
        if search_q:
            query = query.filter(LessonPlan.title.ilike(f"%{search_q}%"))

        plans = query.order_by(LessonPlan.created_at.desc()).all()

        plan_data = []
        for lp in plans:
            class_obj = get_class(session, lp.class_id) if lp.class_id else None
            topics_list = []
            if lp.topics:
                try:
                    topics_list = json.loads(lp.topics) if isinstance(lp.topics, str) else lp.topics
                except (json.JSONDecodeError, ValueError):
                    topics_list = []
            plan_data.append(
                {
                    "id": lp.id,
                    "title": lp.title,
                    "status": lp.status,
                    "class_name": class_obj.name if class_obj else "N/A",
                    "topics": ", ".join(topics_list) if topics_list else "",
                    "duration_minutes": lp.duration_minutes,
                    "created_at": lp.created_at,
                }
            )

        classes = list_classes(session)
        return render_template(
            "lesson_plans/list.html",
            lesson_plans=plan_data,
            classes=classes,
            current_class_id=class_id_filter,
            search_q=search_q,
        )

    @app.route("/lesson-plans/generate", methods=["GET", "POST"])
    @login_required
    def lesson_plan_generate():
        """Generate a lesson plan via form POST or render form on GET."""
        session = _get_session()
        config = current_app.config["APP_CONFIG"]
        classes = list_classes(session)
        providers = get_provider_info(config)
        current_provider = config.get("llm", {}).get("provider", "mock")

        # Pre-fill from query params (e.g., from quiz or lesson context)
        prefill_topics = request.args.get("topics", "")
        prefill_standards = request.args.get("standards", "")
        selected_class_id = request.args.get("class_id", type=int)

        if request.method == "POST":
            class_id = request.form.get("class_id", type=int)
            topics_str = request.form.get("topics", "").strip()
            standards_str = request.form.get("standards", "").strip()
            duration = request.form.get("duration_minutes", type=int) or 50
            grade_level = request.form.get("grade_level", "").strip() or None
            provider_override = request.form.get("provider", "").strip() or None

            if not class_id:
                return render_template(
                    "lesson_plans/generate.html",
                    classes=classes,
                    providers=providers,
                    current_provider=current_provider,
                    prefill_topics=topics_str,
                    prefill_standards=standards_str,
                    error="Please select a class.",
                ), 400

            topics = [t.strip() for t in topics_str.split(",") if t.strip()] if topics_str else None
            standards = [s.strip() for s in standards_str.split(",") if s.strip()] if standards_str else None

            from src.lesson_plan_generator import generate_lesson_plan

            try:
                plan = generate_lesson_plan(
                    session,
                    class_id=class_id,
                    config=config,
                    topics=topics,
                    standards=standards,
                    duration_minutes=duration,
                    grade_level=grade_level,
                    provider_name=provider_override,
                )
            except Exception as e:
                plan = None
                flash(f"Lesson plan generation error: {e}", "error")

            if plan:
                flash("Lesson plan generated successfully.", "success")
                return redirect(url_for("lesson_plan_detail", plan_id=plan.id), code=303)
            else:
                return render_template(
                    "lesson_plans/generate.html",
                    classes=classes,
                    providers=providers,
                    current_provider=current_provider,
                    prefill_topics=topics_str,
                    prefill_standards=standards_str,
                    error="Generation failed. Check your provider settings and try again.",
                ), 500

        return render_template(
            "lesson_plans/generate.html",
            classes=classes,
            providers=providers,
            current_provider=current_provider,
            prefill_topics=prefill_topics,
            prefill_standards=prefill_standards,
            selected_class_id=selected_class_id,
        )

    @app.route("/lesson-plans/<int:plan_id>")
    @login_required
    def lesson_plan_detail(plan_id):
        """Show lesson plan detail with all sections."""
        session = _get_session()
        from src.database import LessonPlan

        plan = session.query(LessonPlan).filter_by(id=plan_id).first()
        if not plan:
            abort(404)

        class_obj = get_class(session, plan.class_id) if plan.class_id else None

        # Parse plan data
        plan_data = {}
        if plan.plan_data:
            try:
                plan_data = json.loads(plan.plan_data) if isinstance(plan.plan_data, str) else plan.plan_data
            except (json.JSONDecodeError, ValueError):
                plan_data = {}

        # Parse topics and standards
        topics = []
        if plan.topics:
            try:
                topics = json.loads(plan.topics) if isinstance(plan.topics, str) else plan.topics
            except (json.JSONDecodeError, ValueError):
                topics = []

        standards = []
        if plan.standards:
            try:
                standards = json.loads(plan.standards) if isinstance(plan.standards, str) else plan.standards
            except (json.JSONDecodeError, ValueError):
                standards = []

        from src.lesson_plan_generator import SECTION_LABELS

        success_msg = request.args.get("saved")

        return render_template(
            "lesson_plans/detail.html",
            lesson_plan=plan,
            plan_data=plan_data,
            class_obj=class_obj,
            topics=topics,
            standards=standards,
            section_labels=SECTION_LABELS,
            success_msg="Section saved successfully." if success_msg else None,
        )

    @app.route("/lesson-plans/<int:plan_id>/edit", methods=["POST"])
    @login_required
    def lesson_plan_edit(plan_id):
        """Save edits to a single plan section."""
        session = _get_session()
        from src.database import LessonPlan

        plan = session.query(LessonPlan).filter_by(id=plan_id).first()
        if not plan:
            abort(404)

        section_key = request.form.get("section_key", "").strip()
        section_content = request.form.get("section_content", "").strip()

        if not section_key:
            flash("Invalid section.", "error")
            return redirect(url_for("lesson_plan_detail", plan_id=plan_id), code=303)

        # Update the plan data
        plan_data = {}
        if plan.plan_data:
            try:
                plan_data = json.loads(plan.plan_data) if isinstance(plan.plan_data, str) else plan.plan_data
            except (json.JSONDecodeError, ValueError):
                plan_data = {}

        plan_data[section_key] = section_content
        plan.plan_data = json.dumps(plan_data)
        session.commit()

        return redirect(url_for("lesson_plan_detail", plan_id=plan_id, saved="1"), code=303)

    @app.route("/lesson-plans/<int:plan_id>/export/<format_name>")
    @login_required
    def lesson_plan_export(plan_id, format_name):
        """Export a lesson plan as PDF or DOCX."""
        session = _get_session()
        from src.database import LessonPlan

        plan = session.query(LessonPlan).filter_by(id=plan_id).first()
        if not plan:
            abort(404)

        import re

        safe_title = re.sub(r"[^\w\s\-]", "", plan.title or "lesson_plan")
        safe_title = re.sub(r"\s+", "_", safe_title.strip())[:80] or "lesson_plan"

        if format_name == "pdf":
            from src.lesson_plan_export import export_lesson_plan_pdf

            buf = export_lesson_plan_pdf(plan)
            return send_file(
                buf,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f"{safe_title}.pdf",
            )
        elif format_name == "docx":
            from src.lesson_plan_export import export_lesson_plan_docx

            buf = export_lesson_plan_docx(plan)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=True,
                download_name=f"{safe_title}.docx",
            )
        else:
            abort(400)

    @app.route("/lesson-plans/<int:plan_id>/delete", methods=["POST"])
    @login_required
    def lesson_plan_delete(plan_id):
        """Delete a lesson plan."""
        session = _get_session()
        from src.database import LessonPlan

        plan = session.query(LessonPlan).filter_by(id=plan_id).first()
        if not plan:
            abort(404)

        session.delete(plan)
        session.commit()
        flash("Lesson plan deleted.", "success")
        return redirect(url_for("lesson_plan_list"), code=303)

    @app.route("/lesson-plans/<int:plan_id>/generate-quiz")
    @login_required
    def lesson_plan_generate_quiz(plan_id):
        """Redirect to quiz generation with pre-filled topics/standards from plan."""
        session = _get_session()
        from src.database import LessonPlan

        plan = session.query(LessonPlan).filter_by(id=plan_id).first()
        if not plan:
            abort(404)

        topics = []
        if plan.topics:
            try:
                topics = json.loads(plan.topics) if isinstance(plan.topics, str) else plan.topics
            except (json.JSONDecodeError, ValueError):
                pass

        standards = []
        if plan.standards:
            try:
                standards = json.loads(plan.standards) if isinstance(plan.standards, str) else plan.standards
            except (json.JSONDecodeError, ValueError):
                pass

        return redirect(
            url_for(
                "generate_quiz",
                class_id=plan.class_id,
                topics=",".join(topics) if topics else "",
                standards=",".join(standards) if standards else "",
                lesson_plan_id=plan.id,
            ),
            code=303,
        )

    # --- Quiz Template Routes ---

    @app.route("/quiz-templates")
    @login_required
    def quiz_template_list():
        """Browse imported quiz templates."""
        session = _get_session()
        imported_quizzes = session.query(Quiz).filter_by(status="imported").order_by(Quiz.created_at.desc()).all()

        templates = []
        for q in imported_quizzes:
            question_count = session.query(Question).filter_by(quiz_id=q.id).count()
            class_name = ""
            if q.class_id:
                class_obj = get_class(session, q.class_id)
                if class_obj:
                    class_name = class_obj.name
            templates.append(
                {
                    "id": q.id,
                    "title": q.title,
                    "status": q.status,
                    "class_name": class_name,
                    "question_count": question_count,
                    "created_at": q.created_at,
                }
            )

        return render_template("quiz_templates/list.html", templates=templates)

    @app.route("/quizzes/<int:quiz_id>/export-template")
    @login_required
    def quiz_export_template(quiz_id):
        """Export a quiz as a shareable JSON template (triggers download)."""
        from src.template_manager import export_quiz_template

        session = _get_session()
        template_data = export_quiz_template(session, quiz_id)
        if template_data is None:
            abort(404)

        # Sanitize filename
        safe_title = re.sub(r"[^\w\s\-]", "", template_data.get("title", "template"))
        safe_title = re.sub(r"\s+", "_", safe_title.strip())[:60] or "template"

        json_bytes = json.dumps(template_data, indent=2).encode("utf-8")
        buf = BytesIO(json_bytes)
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"{safe_title}_template.json",
            mimetype="application/json",
        )

    @app.route("/quiz-templates/import", methods=["GET", "POST"])
    @login_required
    def quiz_template_import():
        """Upload and import a JSON quiz template."""
        session = _get_session()
        classes = list_classes(session)

        if request.method == "GET":
            return render_template("quiz_templates/import.html", classes=classes)

        # POST: handle file upload
        file = request.files.get("template_file")
        if not file or not file.filename:
            flash("Please select a template file to upload.", "error")
            return render_template("quiz_templates/import.html", classes=classes)

        class_id = request.form.get("class_id", type=int)
        if not class_id:
            flash("Please select a class.", "error")
            return render_template("quiz_templates/import.html", classes=classes)

        title_override = request.form.get("title", "").strip() or None

        try:
            raw = file.read().decode("utf-8")
            template_data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            flash(f"Invalid JSON file: {e}", "error")
            return render_template("quiz_templates/import.html", classes=classes)

        from src.template_manager import import_quiz_template, validate_template

        is_valid, errors = validate_template(template_data)
        if not is_valid:
            flash(f"Template validation failed: {'; '.join(errors)}", "error")
            return render_template("quiz_templates/import.html", classes=classes)

        quiz = import_quiz_template(session, template_data, class_id, title=title_override)
        if quiz is None:
            flash("Failed to import template.", "error")
            return render_template("quiz_templates/import.html", classes=classes)

        flash(f"Template imported successfully as '{quiz.title}'.", "success")
        return redirect(url_for("quiz_detail", quiz_id=quiz.id), code=303)

    @app.route("/api/quiz-templates/validate", methods=["POST"])
    @login_required
    def quiz_template_validate():
        """Validate an uploaded template JSON (AJAX)."""
        from src.template_manager import validate_template

        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"valid": False, "errors": ["No JSON data provided"]}), 400

        is_valid, errors = validate_template(data)
        return jsonify({"valid": is_valid, "errors": errors})

    # --- Help ---

    @app.route("/help")
    @login_required
    def help_page():
        """Render the help and getting started guide."""
        return render_template("help.html")
