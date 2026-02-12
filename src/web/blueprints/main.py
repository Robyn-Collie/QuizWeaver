"""Main routes: dashboard, stats, onboarding, help."""

import json

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from src.classroom import get_class, list_classes
from src.database import LessonLog, Quiz
from src.web.blueprints.helpers import _get_session, login_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def index():
    """Redirect root URL to the dashboard."""
    return redirect(url_for("main.dashboard"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Render dashboard with classes, tools, and recent activity."""
    session = _get_session()
    classes = list_classes(session)

    # Redirect first-time users to onboarding if they have no classes
    if len(classes) == 0 and request.args.get("skip_onboarding") != "1":
        return redirect(url_for("main.onboarding"))
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


@main_bp.route("/api/stats")
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


@main_bp.route("/onboarding", methods=["GET", "POST"])
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

        return redirect(url_for("main.dashboard", skip_onboarding="1"))

    return render_template("onboarding.html")


@main_bp.route("/help")
@login_required
def help_page():
    """Render the help and getting started guide."""
    return render_template("help.html")
