"""
Route handlers for QuizWeaver web frontend.
"""

import json
from flask import (
    render_template,
    redirect,
    url_for,
    request,
    abort,
    current_app,
    g,
)
from src.database import LessonLog, Quiz, Question, get_session
from src.classroom import create_class, get_class, list_classes
from src.lesson_tracker import log_lesson, list_lessons, get_assumed_knowledge
from src.cost_tracking import get_cost_summary


def _get_session():
    """Get a database session from the shared app engine."""
    if "db_session" not in g:
        engine = current_app.config["DB_ENGINE"]
        g.db_session = get_session(engine)
    return g.db_session


def register_routes(app):
    """Register all route handlers on the Flask app."""

    @app.route("/")
    def index():
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
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

    # --- Classes ---

    @app.route("/classes")
    def classes_list():
        session = _get_session()
        classes = list_classes(session)
        return render_template("classes/list.html", classes=classes)

    @app.route("/classes/new", methods=["GET", "POST"])
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

    # --- Lessons ---

    @app.route("/classes/<int:class_id>/lessons")
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

    # --- Quizzes ---

    @app.route("/quizzes")
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

    # --- Costs ---

    @app.route("/costs")
    def costs():
        config = current_app.config["APP_CONFIG"]
        provider = config.get("llm", {}).get("provider", "unknown")
        stats = get_cost_summary()
        return render_template("costs.html", stats=stats, provider=provider)
