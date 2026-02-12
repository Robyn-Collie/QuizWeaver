"""Quiz listing, detail, export, editing API, generation, and costs routes."""

import json
import os
import re
from io import BytesIO

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

from src.classroom import get_class, list_classes
from src.cost_tracking import check_budget, get_cost_summary, get_monthly_total
from src.database import Question, Quiz, Rubric
from src.export import export_csv, export_docx, export_gift, export_pdf, export_qti
from src.llm_provider import get_provider_info
from src.quiz_generator import generate_quiz
from src.variant_generator import READING_LEVELS
from src.web.blueprints.helpers import ALLOWED_IMAGE_EXTENSIONS, _get_session, login_required
from src.web.config_utils import save_config

quizzes_bp = Blueprint("quizzes", __name__)


@quizzes_bp.route("/quizzes")
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


@quizzes_bp.route("/quizzes/<int:quiz_id>")
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

    # Parse generation metadata for Glass Box display
    generation_metadata = getattr(quiz, "generation_metadata", None)
    if isinstance(generation_metadata, str):
        try:
            generation_metadata = json.loads(generation_metadata)
        except (json.JSONDecodeError, ValueError):
            generation_metadata = None
    if not isinstance(generation_metadata, dict):
        generation_metadata = None

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
        generation_metadata=generation_metadata,
        parent_quiz=parent_quiz,
        variant_count=variant_count,
        rubrics=rubrics,
        reading_levels=READING_LEVELS,
    )


@quizzes_bp.route("/classes/<int:class_id>/quizzes")
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


@quizzes_bp.route("/quizzes/<int:quiz_id>/export/<format_name>")
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


@quizzes_bp.route("/api/quizzes/<int:quiz_id>/title", methods=["PUT"])
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


@quizzes_bp.route("/api/questions/<int:question_id>", methods=["PUT"])
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


@quizzes_bp.route("/api/questions/<int:question_id>", methods=["DELETE"])
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


@quizzes_bp.route("/api/quizzes/<int:quiz_id>/reorder", methods=["PUT"])
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


@quizzes_bp.route("/api/questions/<int:question_id>/image", methods=["POST"])
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


@quizzes_bp.route("/api/questions/<int:question_id>/image", methods=["DELETE"])
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


@quizzes_bp.route("/api/questions/<int:question_id>/regenerate", methods=["POST"])
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


@quizzes_bp.route("/generate")
@login_required
def generate_redirect():
    """Redirect /generate to the active class's generate page, or class list."""
    session = _get_session()
    classes = list_classes(session)
    if classes:
        return redirect(f"/classes/{classes[0]['id']}/generate")
    flash("Create a class first before generating a quiz.", "info")
    return redirect("/classes/new")


@quizzes_bp.route("/classes/<int:class_id>/generate", methods=["GET", "POST"])
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
            return redirect(url_for("quizzes.quiz_detail", quiz_id=quiz.id), code=303)
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


@quizzes_bp.route("/costs", methods=["GET", "POST"])
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
        return redirect(url_for("quizzes.costs"), code=303)

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
