"""Class and lesson management routes."""

import json
from datetime import date

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from src.classroom import create_class, delete_class, get_class, list_classes, update_class
from src.database import Quiz
from src.lesson_tracker import delete_lesson, get_assumed_knowledge, list_lessons, log_lesson
from src.web.blueprints.helpers import _get_session, login_required

classes_bp = Blueprint("classes", __name__)


@classes_bp.route("/classes")
@login_required
def classes_list():
    """List all classes with lesson and quiz counts."""
    session = _get_session()
    classes = list_classes(session)
    return render_template("classes/list.html", classes=classes)


@classes_bp.route("/classes/new", methods=["GET", "POST"])
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

        new_cls = create_class(
            session,
            name=name,
            grade_level=grade_level,
            subject=subject,
        )
        flash(f"Class '{new_cls.name}' created successfully.", "success")
        return redirect(url_for("classes.classes_list"), code=303)

    return render_template("classes/new.html")


@classes_bp.route("/classes/<int:class_id>")
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


@classes_bp.route("/classes/<int:class_id>/edit", methods=["GET", "POST"])
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

        update_class(
            session,
            class_id=class_id,
            name=name,
            grade_level=grade_level,
            subject=subject,
        )
        flash("Class updated successfully.", "success")
        return redirect(url_for("classes.class_detail", class_id=class_id), code=303)

    return render_template("classes/edit.html", class_obj=class_obj)


@classes_bp.route("/classes/<int:class_id>/delete", methods=["POST"])
@login_required
def class_delete_route(class_id):
    """Delete a class and redirect to the class list."""
    session = _get_session()
    success = delete_class(session, class_id)
    if not success:
        abort(404)
    flash("Class deleted successfully.", "success")
    return redirect(url_for("classes.classes_list"), code=303)


# --- Lessons ---


@classes_bp.route("/classes/<int:class_id>/lessons")
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


@classes_bp.route("/classes/<int:class_id>/lessons/new", methods=["GET", "POST"])
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
        return redirect(url_for("classes.lessons_list", class_id=class_id), code=303)

    return render_template(
        "lessons/new.html",
        class_obj=class_obj,
        today=date.today().isoformat(),
    )


@classes_bp.route("/classes/<int:class_id>/lessons/<int:lesson_id>/delete", methods=["POST"])
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
    return redirect(url_for("classes.lessons_list", class_id=class_id), code=303)
