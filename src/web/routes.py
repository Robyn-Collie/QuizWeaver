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
from src.database import LessonLog, Quiz, Question, get_session
from src.classroom import create_class, get_class, list_classes, update_class, delete_class
from src.lesson_tracker import log_lesson, list_lessons, get_assumed_knowledge, delete_lesson
from src.cost_tracking import get_cost_summary
from src.quiz_generator import generate_quiz
from src.llm_provider import get_provider_info, PROVIDER_REGISTRY
from src.web.config_utils import save_config
from src.export import export_csv, export_docx, export_gift, export_pdf, export_qti


# Default credentials for Phase 1.5 basic auth
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
        return f(*args, **kwargs)
    return decorated_function


def register_routes(app):
    """Register all route handlers on the Flask app."""

    # --- Authentication ---

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """Handle user login via form POST or render login page on GET."""
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")

            config = current_app.config["APP_CONFIG"]
            valid_user = config.get("auth", {}).get("username", DEFAULT_USERNAME)
            valid_pass = config.get("auth", {}).get("password", DEFAULT_PASSWORD)

            if username == valid_user and password == valid_pass:
                flask_session["logged_in"] = True
                flask_session["username"] = username
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
        """List all quizzes with class names and question counts."""
        session = _get_session()
        query = session.query(Quiz)

        # Apply optional filters
        status_filter = request.args.get("status")
        class_id_filter = request.args.get("class_id", type=int)
        if status_filter:
            query = query.filter(Quiz.status == status_filter)
        if class_id_filter:
            query = query.filter(Quiz.class_id == class_id_filter)

        quizzes = query.order_by(Quiz.created_at.desc()).all()
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
        return render_template("quizzes/list.html", quizzes=quiz_data)

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

        return render_template(
            "quizzes/detail.html",
            quiz=quiz,
            questions=parsed_questions,
            class_obj=class_obj,
            style_profile=style_profile,
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

    # --- Help ---

    @app.route("/help")
    @login_required
    def help_page():
        """Render the help and getting started guide."""
        return render_template("help.html")
