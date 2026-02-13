"""Study materials routes: list, generate, detail, export, card API."""

import json
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

from src.classroom import get_class, list_classes
from src.database import Quiz, StudyCard, StudySet
from src.exit_ticket_generator import generate_exit_ticket
from src.lesson_tracker import list_lessons
from src.llm_provider import get_provider_info
from src.study_export import (
    export_flashcards_csv,
    export_flashcards_tsv,
    export_study_docx,
    export_study_pdf,
)
from src.study_generator import generate_study_material
from src.web.blueprints.helpers import _get_session, login_required

study_bp = Blueprint("study", __name__)


@study_bp.route("/study")
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


@study_bp.route("/study/generate", methods=["GET", "POST"])
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
            return redirect(url_for("study.study_detail", study_set_id=study_set.id), code=303)
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


@study_bp.route("/study/<int:study_set_id>")
@login_required
def study_detail(study_set_id):
    """Show study set detail with all cards."""
    session = _get_session()
    study_set = session.query(StudySet).filter_by(id=study_set_id).first()
    if not study_set:
        abort(404)

    cards = (
        session.query(StudyCard).filter_by(study_set_id=study_set_id).order_by(StudyCard.sort_order, StudyCard.id).all()
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


@study_bp.route("/study/<int:study_set_id>/export/<format_name>")
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
        session.query(StudyCard).filter_by(study_set_id=study_set_id).order_by(StudyCard.sort_order, StudyCard.id).all()
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


@study_bp.route("/exit-ticket/generate", methods=["GET", "POST"])
@login_required
def exit_ticket_generate():
    """Generate an exit ticket (short formative assessment)."""
    session = _get_session()
    config = current_app.config["APP_CONFIG"]
    classes = list_classes(session)
    providers = get_provider_info(config)
    current_provider = config.get("llm", {}).get("provider", "mock")

    if request.method == "POST":
        class_id = request.form.get("class_id", type=int)
        lesson_log_id = request.form.get("lesson_log_id", type=int) or None
        topic = request.form.get("topic", "").strip() or None
        num_questions = request.form.get("num_questions", type=int) or 3
        title = request.form.get("title", "").strip() or None
        provider_override = request.form.get("provider", "").strip() or None

        if not class_id:
            return render_template(
                "exit_ticket/generate.html",
                classes=classes,
                providers=providers,
                current_provider=current_provider,
                error="Please select a class.",
            ), 400

        try:
            quiz = generate_exit_ticket(
                session,
                class_id=class_id,
                config=config,
                lesson_log_id=lesson_log_id,
                topic=topic,
                num_questions=num_questions,
                title=title,
                provider_name=provider_override,
            )
        except Exception as e:
            quiz = None
            flash(f"Exit ticket generation error: {e}", "error")

        if quiz:
            flash("Exit ticket generated successfully.", "success")
            return redirect(url_for("quizzes.quiz_detail", quiz_id=quiz.id), code=303)
        else:
            return render_template(
                "exit_ticket/generate.html",
                classes=classes,
                providers=providers,
                current_provider=current_provider,
                error="Generation failed. Check your provider settings and try again.",
            ), 500

    return render_template(
        "exit_ticket/generate.html",
        classes=classes,
        providers=providers,
        current_provider=current_provider,
    )


@study_bp.route("/api/classes/<int:class_id>/lessons")
@login_required
def api_class_lessons(class_id):
    """Return recent lessons for a class as JSON (for exit ticket form)."""
    session = _get_session()
    lessons = list_lessons(session, class_id, filters={"last_days": 30})
    result = []
    for lesson in lessons:
        result.append({
            "id": lesson.id,
            "topics": lesson.topics or "Untitled lesson",
            "date": lesson.date.strftime("%b %d") if lesson.date else "",
            "notes": (lesson.notes or "")[:100],
        })
    return jsonify(result)


@study_bp.route("/api/study-sets/<int:study_set_id>", methods=["DELETE"])
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


@study_bp.route("/api/study-cards/<int:card_id>", methods=["PUT"])
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


@study_bp.route("/api/study-cards/<int:card_id>", methods=["DELETE"])
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


@study_bp.route("/api/study-sets/<int:study_set_id>/reorder", methods=["POST"])
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


@study_bp.route("/api/classes/<int:class_id>/quizzes")
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
