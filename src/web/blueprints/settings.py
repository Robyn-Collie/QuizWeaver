"""Settings, provider wizard, audit log, and standards routes."""

import os

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from src.llm_provider import get_provider, get_provider_info
from src.standards import (
    STANDARD_SETS,
    ensure_standard_set_loaded,
    get_available_standard_sets,
    get_grade_bands,
    get_standard_sets_in_db,
    get_subjects,
    list_standards,
    search_standards,
    standards_count,
)
from src.web.blueprints.helpers import _get_session, login_required
from src.web.config_utils import save_config

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """Manage LLM provider settings."""
    config = current_app.config["APP_CONFIG"]

    if request.method == "POST":
        provider = request.form.get("provider", "mock").strip()
        model_name = request.form.get("model_name", "").strip()
        api_key = request.form.get("api_key", "").strip()
        base_url = request.form.get("base_url", "").strip()
        vertex_project_id = request.form.get("vertex_project_id", "").strip()
        vertex_location = request.form.get("vertex_location", "").strip()

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
        if vertex_project_id:
            config["llm"]["vertex_project_id"] = vertex_project_id
        if vertex_location:
            config["llm"]["vertex_location"] = vertex_location

        # Persist to config.yaml
        save_config(config)

        flash("Settings saved successfully.", "success")
        return redirect(url_for("settings.settings"), code=303)

    # GET: render settings page
    llm_config = config.get("llm", {})
    providers = get_provider_info(config)
    current_provider = llm_config.get("provider", "mock")

    return render_template(
        "settings.html",
        providers=providers,
        current_provider=current_provider,
        llm_config=llm_config,
        standard_sets=get_available_standard_sets(),
        current_standard_set=config.get("standard_set", "sol"),
    )


# --- API Audit Log (E2E testing/transparency) ---


@settings_bp.route("/api/audit-log")
@login_required
def api_audit_log():
    """Return the API call audit log for transparency reporting."""
    from src.llm_provider import get_api_audit_log

    return jsonify(get_api_audit_log())


@settings_bp.route("/api/audit-log/clear", methods=["POST"])
@login_required
def clear_audit_log():
    """Clear the API call audit log."""
    from src.llm_provider import clear_api_audit_log

    clear_api_audit_log()
    return jsonify({"status": "cleared"})


# --- Provider Setup Wizard ---


@settings_bp.route("/settings/wizard")
@login_required
def provider_wizard():
    """Guided step-by-step provider setup wizard."""
    return render_template("provider_wizard.html")


# --- Test Provider API ---


@settings_bp.route("/api/settings/test-provider", methods=["POST"])
@login_required
def test_provider():
    """Test an LLM provider connection without saving settings."""
    import time

    data = request.get_json(silent=True) or {}
    provider_name = data.get("provider", "mock").strip()
    model_name = data.get("model_name", "").strip()
    api_key = data.get("api_key", "").strip()
    base_url = data.get("base_url", "").strip()
    vertex_project_id = data.get("vertex_project_id", "").strip()
    vertex_location = data.get("vertex_location", "").strip()

    # Mock provider: instant success
    if provider_name == "mock":
        return jsonify(
            {
                "success": True,
                "message": "Mock provider always available",
                "latency_ms": 0,
            }
        )

    # Build temporary config (do NOT save)
    temp_config = {
        "llm": {
            "provider": provider_name,
            "mode": "production",  # skip interactive approval
        }
    }
    if model_name:
        temp_config["llm"]["model_name"] = model_name
    if api_key:
        temp_config["llm"]["api_key"] = api_key
    if base_url:
        temp_config["llm"]["base_url"] = base_url
    if vertex_project_id:
        temp_config["llm"]["vertex_project_id"] = vertex_project_id
    if vertex_location:
        temp_config["llm"]["vertex_location"] = vertex_location

    # Temporarily set env var for providers that need it
    old_env = {}
    try:
        if provider_name in ("gemini", "gemini-pro", "gemini-3-pro") and api_key:
            old_env["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY")
            os.environ["GEMINI_API_KEY"] = api_key
        elif provider_name == "openai" and api_key:
            old_env["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY")
            os.environ["OPENAI_API_KEY"] = api_key
        elif provider_name == "anthropic" and api_key:
            old_env["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY")
            os.environ["ANTHROPIC_API_KEY"] = api_key

        start = time.time()
        provider = get_provider(temp_config, web_mode=True)
        provider.generate(["Say hello in one sentence."])
        elapsed_ms = int((time.time() - start) * 1000)

        return jsonify(
            {
                "success": True,
                "message": f"Connected successfully ({elapsed_ms}ms)",
                "latency_ms": elapsed_ms,
            }
        )
    except Exception as e:
        error_msg = str(e)
        # Add helpful context for common errors
        lower_msg = error_msg.lower()
        if "401" in error_msg or "unauthorized" in lower_msg or "invalid" in lower_msg and "key" in lower_msg:
            error_msg += " -- Check that your API key is correct and has not expired."
        elif "403" in error_msg or "forbidden" in lower_msg:
            error_msg += " -- Your API key may not have permission for this model. Check your account settings."
        elif "404" in error_msg or "not found" in lower_msg:
            error_msg += " -- The model name may be incorrect. Check the model name in your provider's documentation."
        elif "429" in error_msg or "rate" in lower_msg or "quota" in lower_msg:
            error_msg += " -- You've hit a rate limit or quota. Wait a moment and try again, or check your billing."
        elif "timeout" in lower_msg or "timed out" in lower_msg:
            error_msg += " -- The provider took too long to respond. Check your internet connection."
        elif "connection" in lower_msg or "refused" in lower_msg:
            error_msg += " -- Could not reach the provider. Check your internet connection and the API endpoint URL."
        return jsonify(
            {
                "success": False,
                "message": error_msg,
                "latency_ms": 0,
            }
        )
    finally:
        # Restore env vars
        for key, val in old_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


# --- Standards ---


@settings_bp.route("/standards")
@login_required
def standards_page():
    """Browse and search educational standards."""
    config = current_app.config["APP_CONFIG"]
    session = _get_session()

    # Auto-load the configured standard set if table is empty
    total = standards_count(session)
    if total == 0:
        configured_set = config.get("standard_set", "sol")
        ensure_standard_set_loaded(session, configured_set)
        total = standards_count(session)

    q = request.args.get("q", "").strip()
    subject = request.args.get("subject", "").strip()
    grade_band = request.args.get("grade_band", "").strip()
    standard_set = request.args.get("standard_set", "").strip()

    # Resolve label for the selected set
    standard_set_label = ""
    if standard_set:
        ss_info = STANDARD_SETS.get(standard_set)
        standard_set_label = ss_info["label"] if ss_info else standard_set

    if q:
        results = search_standards(
            session,
            q,
            subject=subject or None,
            grade_band=grade_band or None,
            standard_set=standard_set or None,
        )
    else:
        results = list_standards(
            session,
            subject=subject or None,
            grade_band=grade_band or None,
            standard_set=standard_set or None,
        )

    loaded_sets = get_standard_sets_in_db(session)

    return render_template(
        "standards.html",
        standards=results,
        total_count=total,
        subjects=get_subjects(session, standard_set=standard_set or None),
        grade_bands=get_grade_bands(session, standard_set=standard_set or None),
        available_sets=get_available_standard_sets(),
        loaded_sets=loaded_sets,
        q=q,
        subject=subject,
        grade_band=grade_band,
        standard_set=standard_set,
        standard_set_label=standard_set_label,
    )


@settings_bp.route("/api/standards/search")
@login_required
def api_standards_search():
    """JSON API for standards autocomplete search."""
    config = current_app.config["APP_CONFIG"]
    session = _get_session()

    # Auto-load the configured standard set if table is empty
    total = standards_count(session)
    if total == 0:
        configured_set = config.get("standard_set", "sol")
        ensure_standard_set_loaded(session, configured_set)

    q = request.args.get("q", "").strip()
    subject = request.args.get("subject", "").strip()
    grade_band = request.args.get("grade_band", "").strip()
    standard_set = request.args.get("standard_set", "").strip()

    if not q:
        return jsonify({"results": []})

    results = search_standards(
        session,
        q,
        subject=subject or None,
        grade_band=grade_band or None,
        standard_set=standard_set or None,
    )
    return jsonify(
        {
            "results": [
                {
                    "id": std.id,
                    "code": std.code,
                    "description": std.description,
                    "subject": std.subject,
                    "grade_band": std.grade_band,
                    "strand": std.strand,
                    "standard_set": std.standard_set or "sol",
                }
                for std in results[:20]  # Limit autocomplete results
            ]
        }
    )


@settings_bp.route("/settings/standards", methods=["POST"])
@login_required
def settings_standards():
    """Save the selected standard set and auto-load it."""
    config = current_app.config["APP_CONFIG"]
    selected_set = request.form.get("standard_set", "sol")
    config["standard_set"] = selected_set
    save_config(config)

    # Auto-load the selected set
    session = _get_session()
    loaded = ensure_standard_set_loaded(session, selected_set)
    set_label = STANDARD_SETS.get(selected_set, {}).get("label", selected_set)

    if loaded > 0:
        flash(f"Loaded {loaded} standards from {set_label}.", "success")
    else:
        flash(f"Standards set updated to {set_label}.", "success")

    return redirect(url_for("settings.settings"))
