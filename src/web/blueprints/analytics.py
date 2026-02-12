"""Performance analytics routes: dashboard, import, manual entry, reteach, API."""

import json
from datetime import date
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

from src.classroom import get_class
from src.database import PerformanceData, Question, Quiz
from src.lesson_tracker import get_assumed_knowledge
from src.llm_provider import get_provider_info
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
from src.reteach_generator import generate_reteach_suggestions
from src.web.blueprints.helpers import _get_session, login_required

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/classes/<int:class_id>/analytics")
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


@analytics_bp.route("/classes/<int:class_id>/analytics/import", methods=["GET", "POST"])
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
            return redirect(url_for("analytics.analytics_dashboard", class_id=class_id), code=303)

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


@analytics_bp.route("/classes/<int:class_id>/analytics/manual", methods=["GET", "POST"])
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
        return redirect(url_for("analytics.analytics_dashboard", class_id=class_id), code=303)

    return render_template(
        "analytics/manual_entry.html",
        class_obj=class_obj,
        known_topics=known_topics,
        today=date.today().isoformat(),
    )


@analytics_bp.route("/classes/<int:class_id>/analytics/quiz-scores", methods=["GET", "POST"])
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
        return redirect(url_for("analytics.analytics_dashboard", class_id=class_id), code=303)

    return render_template(
        "analytics/quiz_scores.html",
        class_obj=class_obj,
        quizzes=quizzes,
        today=date.today().isoformat(),
    )


@analytics_bp.route("/api/quizzes/<int:quiz_id>/questions")
@login_required
def api_quiz_questions(quiz_id):
    """Return quiz questions as JSON (for quiz score entry form)."""
    session = _get_session()
    questions = session.query(Question).filter_by(quiz_id=quiz_id).order_by(Question.sort_order, Question.id).all()
    return jsonify(
        {"questions": [{"id": q.id, "text": q.text or f"Question #{q.id}", "type": q.question_type} for q in questions]}
    )


@analytics_bp.route("/classes/<int:class_id>/analytics/reteach", methods=["GET", "POST"])
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


@analytics_bp.route("/api/classes/<int:class_id>/analytics")
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


@analytics_bp.route("/api/classes/<int:class_id>/analytics/trends")
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


@analytics_bp.route("/api/performance/<int:perf_id>", methods=["DELETE"])
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


@analytics_bp.route("/classes/<int:class_id>/analytics/sample-csv")
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
