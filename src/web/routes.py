"""
Route handlers for QuizWeaver web frontend.
"""

import json
import functools
from flask import (
    render_template,
    redirect,
    url_for,
    request,
    abort,
    current_app,
    g,
    session as flask_session,
    jsonify,
)
from src.database import LessonLog, Quiz, Question, get_session
from src.classroom import create_class, get_class, list_classes, update_class, delete_class
from src.lesson_tracker import log_lesson, list_lessons, get_assumed_knowledge, delete_lesson
from src.cost_tracking import get_cost_summary
from src.quiz_generator import generate_quiz


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
        flask_session.clear()
        return redirect(url_for("login"), code=303)

    # --- Main Routes (protected) ---

    @app.route("/")
    @login_required
    def index():
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
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
        session = _get_session()
        classes = list_classes(session)
        return render_template("classes/list.html", classes=classes)

    @app.route("/classes/new", methods=["GET", "POST"])
    @login_required
    def class_create():
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

            create_class(
                session,
                name=name,
                grade_level=grade_level,
                subject=subject,
                standards=standards,
            )
            return redirect(url_for("classes_list"), code=303)

        return render_template("classes/new.html")

    @app.route("/classes/<int:class_id>")
    @login_required
    def class_detail(class_id):
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
            return redirect(url_for("class_detail", class_id=class_id), code=303)

        return render_template("classes/edit.html", class_obj=class_obj)

    @app.route("/classes/<int:class_id>/delete", methods=["POST"])
    @login_required
    def class_delete_route(class_id):
        session = _get_session()
        success = delete_class(session, class_id)
        if not success:
            abort(404)
        return redirect(url_for("classes_list"), code=303)

    # --- Lessons ---

    @app.route("/classes/<int:class_id>/lessons")
    @login_required
    def lessons_list(class_id):
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
            return redirect(
                url_for("lessons_list", class_id=class_id), code=303
            )

        return render_template("lessons/new.html", class_obj=class_obj)

    @app.route("/classes/<int:class_id>/lessons/<int:lesson_id>/delete", methods=["POST"])
    @login_required
    def lesson_delete_route(class_id, lesson_id):
        session = _get_session()
        # Verify class exists
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        success = delete_lesson(session, lesson_id)
        if not success:
            abort(404)
        return redirect(url_for("lessons_list", class_id=class_id), code=303)

    # --- Quizzes ---

    @app.route("/quizzes")
    @login_required
    def quizzes_list():
        session = _get_session()
        quizzes = session.query(Quiz).order_by(Quiz.created_at.desc()).all()
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
        session = _get_session()
        quiz = session.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            abort(404)

        questions = session.query(Question).filter_by(quiz_id=quiz_id).all()
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

        return render_template(
            "quizzes/detail.html",
            quiz=quiz,
            questions=parsed_questions,
            class_obj=class_obj,
        )

    @app.route("/classes/<int:class_id>/quizzes")
    @login_required
    def class_quizzes(class_id):
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

    # --- Quiz Generation ---

    @app.route("/classes/<int:class_id>/generate", methods=["GET", "POST"])
    @login_required
    def quiz_generate(class_id):
        session = _get_session()
        class_obj = get_class(session, class_id)
        if not class_obj:
            abort(404)

        if request.method == "POST":
            config = current_app.config["APP_CONFIG"]
            num_questions = int(request.form.get("num_questions", 20))
            grade_level = request.form.get("grade_level", "").strip() or None
            sol_raw = request.form.get("sol_standards", "").strip()
            sol_standards = (
                [s.strip() for s in sol_raw.split(",") if s.strip()]
                if sol_raw
                else None
            )

            quiz = generate_quiz(
                session,
                class_id=class_id,
                config=config,
                num_questions=num_questions,
                grade_level=grade_level,
                sol_standards=sol_standards,
            )

            if quiz:
                return redirect(url_for("quiz_detail", quiz_id=quiz.id), code=303)
            else:
                return render_template(
                    "quizzes/generate.html",
                    class_obj=class_obj,
                    error="Quiz generation failed. Please try again.",
                )

        return render_template("quizzes/generate.html", class_obj=class_obj)

    # --- Costs ---

    @app.route("/costs")
    @login_required
    def costs():
        config = current_app.config["APP_CONFIG"]
        provider = config.get("llm", {}).get("provider", "unknown")
        stats = get_cost_summary()
        return render_template("costs.html", stats=stats, provider=provider)
