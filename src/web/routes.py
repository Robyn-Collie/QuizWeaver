"""
Route handlers for QuizWeaver web frontend.
"""

import json
import os
import re
import functools
from io import BytesIO
from datetime import date
from werkzeug.utils import secure_filename
from flask import (
    render_template,
    redirect,
    url_for,
    request,
    abort,
    current_app,
    flash,
    g,
    session as flask_session,
    jsonify,
    send_file,
)
from src.database import LessonLog, Quiz, Question, StudySet, StudyCard, Rubric, RubricCriterion, PerformanceData, get_session
from src.classroom import create_class, get_class, list_classes, update_class, delete_class
from src.lesson_tracker import log_lesson, list_lessons, get_assumed_knowledge, delete_lesson
from src.cost_tracking import get_cost_summary
from src.quiz_generator import generate_quiz
from src.llm_provider import get_provider_info, PROVIDER_REGISTRY
from src.web.config_utils import save_config
from src.export import export_csv, export_docx, export_gift, export_pdf, export_qti
from src.study_generator import generate_study_material, VALID_MATERIAL_TYPES
from src.study_export import (
    export_flashcards_tsv,
    export_flashcards_csv,
    export_study_pdf,
    export_study_docx,
)
from src.variant_generator import generate_variant, READING_LEVELS
from src.rubric_generator import generate_rubric
from src.rubric_export import export_rubric_csv, export_rubric_docx, export_rubric_pdf
from src.performance_import import (
    parse_performance_csv,
    import_csv_data,
    import_quiz_scores,
    get_sample_csv,
)
from src.performance_analytics import (
    compute_gap_analysis,
    get_topic_trends,
    get_class_summary,
    get_standards_mastery,
)
from src.reteach_generator import generate_reteach_suggestions
from src.web.auth import (
    create_user,
    authenticate_user,
    change_password,
    get_user_count,
    get_user_by_id,
)


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
        """Render dashboard with class, lesson, and quiz counts."""
        session = _get_session()
        config = current_app.config["APP_CONFIG"]
        classes = list_classes(session)
        total_lessons = session.query(LessonLog).count()
        total_quizzes = session.query(Quiz).count()
        provider = config.get("llm", {}).get("provider", "unknown")

        return render_template(
            "dashboard.html",
            classes=classes,
            total_classes=len(classes),
            total_lessons=total_lessons,
            total_quizzes=total_quizzes,
            provider=provider,
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
        quizzes_by_class = [
            {"class_name": cls["name"], "count": cls["quiz_count"]}
            for cls in classes
        ]

        return jsonify({
            "lessons_by_date": lessons_by_date,
            "quizzes_by_class": quizzes_by_class,
        })

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
            standards = (
                [s.strip() for s in standards_raw.split(",") if s.strip()]
                if standards_raw
                else None
            )

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
            standards = (
                [s.strip() for s in standards_raw.split(",") if s.strip()]
                if standards_raw
                else None
            )

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
            parsed_lessons.append({
                "id": lesson.id,
                "date": lesson.date,
                "content": lesson.content,
                "topics": topics or [],
                "notes": lesson.notes,
            })

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
            topics = (
                [t.strip() for t in topics_raw.split(",") if t.strip()]
                if topics_raw
                else None
            )

            log_lesson(
                session,
                class_id=class_id,
                content=content,
                topics=topics,
                notes=notes,
            )
            flash("Lesson logged successfully.", "success")
            return redirect(
                url_for("lessons_list", class_id=class_id), code=303
            )

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
            quiz_data.append({
                "id": q.id,
                "title": q.title,
                "status": q.status,
                "class_name": class_obj.name if class_obj else "N/A",
                "question_count": question_count,
                "created_at": q.created_at,
            })

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
            parsed_questions.append({
                "id": q.id,
                "type": q.question_type,
                "title": q.title,
                "text": q.text,
                "points": q.points,
                "data": data,
            })

        # Parse style_profile for template use
        style_profile = quiz.style_profile
        if isinstance(style_profile, str):
            try:
                style_profile = json.loads(style_profile)
            except (json.JSONDecodeError, ValueError):
                style_profile = {}
        if not isinstance(style_profile, dict):
            style_profile = {}

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
            quiz_data.append({
                "id": q.id,
                "title": q.title,
                "status": q.status,
                "class_name": class_obj.name,
                "question_count": question_count,
                "created_at": q.created_at,
            })
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

        return jsonify({"ok": True, "question": {
            "id": question.id,
            "text": question.text,
            "points": question.points,
            "question_type": question.question_type,
            "data": question.data,
        }})

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
        actual_ids = set(
            row[0] for row in session.query(Question.id).filter_by(quiz_id=quiz_id).all()
        )
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
            return jsonify({"ok": False, "error": f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"}), 400

        safe_name = secure_filename(file.filename)
        # Add question_id prefix to avoid collisions
        filename = f"upload_{question_id}_{safe_name}"

        config = current_app.config["APP_CONFIG"]
        images_dir = os.path.abspath(
            config.get("paths", {}).get("generated_images_dir", "generated_images")
        )
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

        return jsonify({"ok": True, "question": {
            "id": result.id,
            "text": result.text,
            "points": result.points,
            "question_type": result.question_type,
            "data": result.data if isinstance(result.data, dict) else json.loads(result.data) if isinstance(result.data, str) else {},
        }})

    # --- Quiz Generation ---

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
            sol_standards = (
                [s.strip() for s in sol_raw.split(",") if s.strip()]
                if sol_raw
                else None
            )

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
                    error="Quiz generation failed. Please try again.",
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

    @app.route("/costs")
    @login_required
    def costs():
        """Show API cost tracking dashboard with provider info."""
        config = current_app.config["APP_CONFIG"]
        provider = config.get("llm", {}).get("provider", "unknown")
        stats = get_cost_summary()
        return render_template("costs.html", stats=stats, provider=provider)

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
        )

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
            set_data.append({
                "id": ss.id,
                "title": ss.title,
                "material_type": ss.material_type,
                "status": ss.status,
                "class_name": class_obj.name if class_obj else "N/A",
                "card_count": card_count,
                "created_at": ss.created_at,
            })

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

        if request.method == "POST":
            class_id = request.form.get("class_id", type=int)
            material_type = request.form.get("material_type", "flashcard").strip()
            quiz_id = request.form.get("quiz_id", type=int) or None
            topic = request.form.get("topic", "").strip() or None
            title = request.form.get("title", "").strip() or None

            if not class_id:
                return render_template(
                    "study/generate.html",
                    classes=classes,
                    error="Please select a class.",
                ), 400

            study_set = generate_study_material(
                session,
                class_id=class_id,
                material_type=material_type,
                config=config,
                quiz_id=quiz_id,
                topic=topic,
                title=title,
            )

            if study_set:
                flash("Study material generated successfully.", "success")
                return redirect(url_for("study_detail", study_set_id=study_set.id), code=303)
            else:
                return render_template(
                    "study/generate.html",
                    classes=classes,
                    error="Generation failed. Please try again.",
                ), 500

        return render_template("study/generate.html", classes=classes)

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
            parsed_cards.append({
                "id": card.id,
                "card_type": card.card_type,
                "sort_order": card.sort_order,
                "front": card.front,
                "back": card.back,
                "data": card_data,
            })

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

    @app.route("/api/classes/<int:class_id>/quizzes")
    @login_required
    def api_class_quizzes(class_id):
        """Return quizzes for a class as JSON (used by study generate form)."""
        session = _get_session()
        quizzes = (
            session.query(Quiz)
            .filter_by(class_id=class_id)
            .order_by(Quiz.created_at.desc())
            .all()
        )
        return jsonify([
            {"id": q.id, "title": q.title or f"Quiz #{q.id}"}
            for q in quizzes
        ])

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

        if request.method == "POST":
            reading_level = request.form.get("reading_level", "").strip()
            title = request.form.get("title", "").strip() or None

            if reading_level not in READING_LEVELS:
                return render_template(
                    "quizzes/generate_variant.html",
                    quiz=quiz,
                    reading_levels=READING_LEVELS,
                    error="Please select a valid reading level.",
                ), 400

            variant = generate_variant(
                session,
                quiz_id=quiz_id,
                reading_level=reading_level,
                config=config,
                title=title,
            )
            if variant:
                flash("Variant generated successfully.", "success")
                return redirect(url_for("quiz_detail", quiz_id=variant.id), code=303)
            else:
                return render_template(
                    "quizzes/generate_variant.html",
                    quiz=quiz,
                    reading_levels=READING_LEVELS,
                    error="Variant generation failed. Please try again.",
                ), 500

        return render_template(
            "quizzes/generate_variant.html",
            quiz=quiz,
            reading_levels=READING_LEVELS,
        )

    @app.route("/quizzes/<int:quiz_id>/variants")
    @login_required
    def quiz_variants(quiz_id):
        """List all variants of a quiz."""
        session = _get_session()
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            abort(404)

        variants = (
            session.query(Quiz)
            .filter_by(parent_quiz_id=quiz_id)
            .order_by(Quiz.created_at.desc())
            .all()
        )
        variant_data = []
        for v in variants:
            question_count = session.query(Question).filter_by(quiz_id=v.id).count()
            variant_data.append({
                "id": v.id,
                "title": v.title,
                "reading_level": v.reading_level,
                "status": v.status,
                "question_count": question_count,
                "created_at": v.created_at,
            })

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

        if request.method == "POST":
            title = request.form.get("title", "").strip() or None

            rubric = generate_rubric(
                session,
                quiz_id=quiz_id,
                config=config,
                title=title,
            )
            if rubric:
                flash("Rubric generated successfully.", "success")
                return redirect(url_for("rubric_detail", rubric_id=rubric.id), code=303)
            else:
                return render_template(
                    "quizzes/generate_rubric.html",
                    quiz=quiz,
                    error="Rubric generation failed. Please try again.",
                ), 500

        return render_template("quizzes/generate_rubric.html", quiz=quiz)

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
            parsed_criteria.append({
                "id": c.id,
                "criterion": c.criterion,
                "description": c.description,
                "max_points": c.max_points,
                "levels": levels,
            })

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

        quizzes = (
            session.query(Quiz)
            .filter_by(class_id=class_id)
            .order_by(Quiz.created_at.desc())
            .all()
        )

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
                return redirect(
                    url_for("analytics_dashboard", class_id=class_id), code=303
                )

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

            weak_areas = (
                [w.strip() for w in weak_areas_raw.split(";") if w.strip()]
                if weak_areas_raw
                else []
            )

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
            return redirect(
                url_for("analytics_dashboard", class_id=class_id), code=303
            )

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

        quizzes = (
            session.query(Quiz)
            .filter_by(class_id=class_id)
            .order_by(Quiz.created_at.desc())
            .all()
        )

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

            count = import_quiz_scores(
                session, class_id, quiz_id, question_scores, sample_size, score_date
            )

            flash(f"Imported {count} performance record(s) from quiz scores.", "success")
            return redirect(
                url_for("analytics_dashboard", class_id=class_id), code=303
            )

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
        questions = (
            session.query(Question)
            .filter_by(quiz_id=quiz_id)
            .order_by(Question.sort_order, Question.id)
            .all()
        )
        return jsonify({
            "questions": [
                {"id": q.id, "text": q.text or f"Question #{q.id}", "type": q.question_type}
                for q in questions
            ]
        })

    @app.route("/classes/<int:class_id>/analytics/reteach", methods=["GET", "POST"])
    @login_required
    def analytics_reteach(class_id):
        """Re-teach suggestions page."""
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        config = current_app.config["APP_CONFIG"]
        gap_summary = get_class_summary(session, class_id)
        suggestions = None

        if request.method == "POST":
            focus_raw = request.form.get("focus_topics", "").strip()
            focus_topics = (
                [t.strip() for t in focus_raw.split(",") if t.strip()]
                if focus_raw
                else None
            )
            max_suggestions = int(request.form.get("max_suggestions", 5))

            suggestions = generate_reteach_suggestions(
                session, class_id, config,
                focus_topics=focus_topics,
                max_suggestions=max_suggestions,
            )
            if suggestions is None:
                return render_template(
                    "analytics/reteach.html",
                    class_obj=class_obj,
                    gap_summary=gap_summary,
                    error="Failed to generate suggestions. Please try again.",
                ), 500

        return render_template(
            "analytics/reteach.html",
            class_obj=class_obj,
            gap_summary=gap_summary,
            suggestions=suggestions,
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

        return jsonify({
            "gap_data": gap_data,
            "summary": summary,
        })

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

    # --- Help ---

    @app.route("/help")
    @login_required
    def help_page():
        """Render the help and getting started guide."""
        return render_template("help.html")
