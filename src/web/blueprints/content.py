"""Content generation routes: question bank, variants, rubrics, topics, lesson plans, templates."""

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
from src.database import Question, Quiz, Rubric, RubricCriterion
from src.llm_provider import ProviderError, get_provider_info
from src.rubric_export import export_rubric_csv, export_rubric_docx, export_rubric_pdf
from src.rubric_generator import generate_rubric
from src.topic_generator import generate_from_topics, search_topics
from src.variant_generator import READING_LEVELS, generate_variant
from src.web.blueprints.helpers import _get_session, flash_generation_error, login_required

content_bp = Blueprint("content", __name__)


# --- Question Bank ---


@content_bp.route("/question-bank")
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


@content_bp.route("/api/question-bank/add", methods=["POST"])
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


@content_bp.route("/api/question-bank/remove", methods=["POST"])
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


@content_bp.route("/quizzes/<int:quiz_id>/generate-variant", methods=["GET", "POST"])
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
        except ProviderError as pe:
            variant = None
            flash(pe.user_message, "error")
        except Exception as e:
            variant = None
            flash_generation_error("Variant generation", e)

        if variant:
            # Remember last-used provider for quiz tasks (variants are quizzes)
            if provider_override:
                config.setdefault("last_provider", {})["quiz"] = provider_override
                from src.web.config_utils import save_config

                save_config(config)
            flash("Variant generated successfully.", "success")
            return redirect(url_for("quizzes.quiz_detail", quiz_id=variant.id), code=303)
        else:
            last_quiz_provider = config.get("last_provider", {}).get("quiz", "")
            return render_template(
                "quizzes/generate_variant.html",
                quiz=quiz,
                reading_levels=READING_LEVELS,
                providers=providers,
                current_provider=current_provider,
                last_provider=last_quiz_provider,
                error="Variant generation failed. Check your provider settings and try again.",
            ), 500

    last_quiz_provider = config.get("last_provider", {}).get("quiz", "")
    return render_template(
        "quizzes/generate_variant.html",
        quiz=quiz,
        reading_levels=READING_LEVELS,
        providers=providers,
        current_provider=current_provider,
        last_provider=last_quiz_provider,
    )


@content_bp.route("/quizzes/<int:quiz_id>/variants")
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


@content_bp.route("/quizzes/<int:quiz_id>/generate-rubric", methods=["GET", "POST"])
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
        except ProviderError as pe:
            rubric = None
            flash(pe.user_message, "error")
        except Exception as e:
            rubric = None
            flash_generation_error("Rubric generation", e)

        if rubric:
            # Remember last-used provider for rubric generation
            if provider_override:
                config.setdefault("last_provider", {})["rubric"] = provider_override
                from src.web.config_utils import save_config

                save_config(config)
            flash("Rubric generated successfully.", "success")
            return redirect(url_for("content.rubric_detail", rubric_id=rubric.id), code=303)
        else:
            last_rubric_provider = config.get("last_provider", {}).get("rubric", "")
            return render_template(
                "quizzes/generate_rubric.html",
                quiz=quiz,
                providers=providers,
                current_provider=current_provider,
                last_provider=last_rubric_provider,
                error="Rubric generation failed. Check your provider settings and try again.",
            ), 500

    last_rubric_provider = config.get("last_provider", {}).get("rubric", "")
    return render_template(
        "quizzes/generate_rubric.html",
        quiz=quiz,
        providers=providers,
        current_provider=current_provider,
        last_provider=last_rubric_provider,
    )


@content_bp.route("/rubrics/<int:rubric_id>")
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


@content_bp.route("/rubrics/<int:rubric_id>/export/<format_name>")
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


@content_bp.route("/api/rubrics/<int:rubric_id>", methods=["DELETE"])
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


# --- Topic-Based Generation ---


@content_bp.route("/generate/topics", methods=["GET", "POST"])
@login_required
def generate_from_topics_page():
    """Generate quizzes or study materials from topics."""
    session = _get_session()
    config = current_app.config["APP_CONFIG"]
    classes_data = list_classes(session)

    if not classes_data:
        flash("Create a class before generating content.", "warning")
        return redirect(url_for("classes.class_create"), code=303)

    selected_class_id = request.args.get("class_id", type=int) or classes_data[0]["id"]

    if request.method == "POST":
        class_id = request.form.get("class_id", type=int)
        topics_raw = request.form.get("topics", "").strip()
        output_type = request.form.get("output_type", "quiz")
        title = request.form.get("title", "").strip() or None

        if not topics_raw:
            return render_template(
                "generate_topics.html",
                classes=classes_data,
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
            except ProviderError as pe:
                result = None
                flash(pe.user_message, "error")
            except Exception as e:
                result = None
                flash_generation_error("Quiz generation", e)

            if result:
                flash("Quiz generated from topics!", "success")
                return redirect(url_for("quizzes.quiz_detail", quiz_id=result.id), code=303)
            else:
                return render_template(
                    "generate_topics.html",
                    classes=classes_data,
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
            except ProviderError as pe:
                result = None
                flash(pe.user_message, "error")
            except Exception as e:
                result = None
                flash_generation_error("Content generation", e)

            if result:
                flash(f"{output_type.replace('_', ' ').title()} generated from topics!", "success")
                return redirect(url_for("study.study_detail", study_set_id=result.id), code=303)
            else:
                return render_template(
                    "generate_topics.html",
                    classes=classes_data,
                    selected_class_id=class_id,
                    error="Generation failed. Check your provider settings and try again.",
                )

    return render_template(
        "generate_topics.html",
        classes=classes_data,
        selected_class_id=selected_class_id,
    )


@content_bp.route("/api/topics/search")
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


# --- Lesson Plan Routes ---


@content_bp.route("/lesson-plans")
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


@content_bp.route("/lesson-plans/generate", methods=["GET", "POST"])
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
        except ProviderError as pe:
            plan = None
            flash(pe.user_message, "error")
        except Exception as e:
            plan = None
            flash_generation_error("Lesson plan generation", e)

        if plan:
            # Remember last-used provider for lesson plans
            if provider_override:
                config.setdefault("last_provider", {})["lesson_plan"] = provider_override
                from src.web.config_utils import save_config

                save_config(config)
            flash("Lesson plan generated successfully.", "success")
            return redirect(url_for("content.lesson_plan_detail", plan_id=plan.id), code=303)
        else:
            last_lp_provider = config.get("last_provider", {}).get("lesson_plan", "")
            return render_template(
                "lesson_plans/generate.html",
                classes=classes,
                providers=providers,
                current_provider=current_provider,
                last_provider=last_lp_provider,
                prefill_topics=topics_str,
                prefill_standards=standards_str,
                error="Generation failed. Check your provider settings and try again.",
            ), 500

    last_lp_provider = config.get("last_provider", {}).get("lesson_plan", "")
    return render_template(
        "lesson_plans/generate.html",
        classes=classes,
        providers=providers,
        current_provider=current_provider,
        last_provider=last_lp_provider,
        prefill_topics=prefill_topics,
        prefill_standards=prefill_standards,
        selected_class_id=selected_class_id,
    )


@content_bp.route("/lesson-plans/<int:plan_id>")
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


@content_bp.route("/lesson-plans/<int:plan_id>/edit", methods=["POST"])
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
        return redirect(url_for("content.lesson_plan_detail", plan_id=plan_id), code=303)

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

    return redirect(url_for("content.lesson_plan_detail", plan_id=plan_id, saved="1"), code=303)


@content_bp.route("/lesson-plans/<int:plan_id>/export/<format_name>")
@login_required
def lesson_plan_export(plan_id, format_name):
    """Export a lesson plan as PDF or DOCX."""
    session = _get_session()
    from src.database import LessonPlan

    plan = session.query(LessonPlan).filter_by(id=plan_id).first()
    if not plan:
        abort(404)

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


@content_bp.route("/lesson-plans/<int:plan_id>/delete", methods=["POST"])
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
    return redirect(url_for("content.lesson_plan_list"), code=303)


@content_bp.route("/lesson-plans/<int:plan_id>/generate-quiz")
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
            "quizzes.quiz_generate",
            class_id=plan.class_id,
            topics=",".join(topics) if topics else "",
            standards=",".join(standards) if standards else "",
            lesson_plan_id=plan.id,
        ),
        code=303,
    )


# --- Quiz Template Routes ---


@content_bp.route("/quiz-templates")
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


@content_bp.route("/quizzes/<int:quiz_id>/export-template")
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


@content_bp.route("/quiz-templates/import", methods=["GET", "POST"])
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
    return redirect(url_for("quizzes.quiz_detail", quiz_id=quiz.id), code=303)


@content_bp.route("/api/quiz-templates/validate", methods=["POST"])
@login_required
def quiz_template_validate():
    """Validate an uploaded template JSON (AJAX)."""
    from src.template_manager import validate_template

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"valid": False, "errors": ["No JSON data provided"]}), 400

    is_valid, errors = validate_template(data)
    return jsonify({"valid": is_valid, "errors": errors})
