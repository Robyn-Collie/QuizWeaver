"""Settings, provider wizard, audit log, standards, and source document routes."""

import logging
import os

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

from src.llm_provider import ProviderError, get_provider, get_provider_info
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
from src.web.auth import create_user
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
            # SEC-005: Never write API keys to config.yaml — use .env only
            from src.web.config_utils import save_api_key_to_env

            env_key_map = {
                "gemini": "GEMINI_API_KEY",
                "gemini-pro": "GEMINI_API_KEY",
                "gemini-3-flash": "GEMINI_API_KEY",
                "gemini-3-pro": "GEMINI_API_KEY",
                "gemini-flash": "GEMINI_API_KEY",
                "openai": "OPENAI_API_KEY",
                "openai-compatible": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
            }
            env_key = env_key_map.get(provider, "LLM_API_KEY")
            save_api_key_to_env(env_key, api_key)
            os.environ[env_key] = api_key  # Also set for current session
            # Do NOT write api_key to config dict
        if base_url:
            config["llm"]["base_url"] = base_url
        elif provider not in ("openai-compatible",):
            # Clear base_url if not needed
            config["llm"].pop("base_url", None)
        if vertex_project_id:
            config["llm"]["vertex_project_id"] = vertex_project_id
        if vertex_location:
            config["llm"]["vertex_location"] = vertex_location

        # Strip api_key from config before persisting (SEC-005)
        config.get("llm", {}).pop("api_key", None)

        # Persist to config.yaml
        save_config(config)

        flash("Settings saved successfully.", "success")
        return redirect(url_for("settings.settings"), code=303)

    # GET: render settings page
    llm_config = config.get("llm", {})
    providers = get_provider_info(config)
    current_provider = llm_config.get("provider", "mock")

    pixabay_configured = bool(os.getenv("PIXABAY_API_KEY", "").strip())

    return render_template(
        "settings.html",
        providers=providers,
        current_provider=current_provider,
        llm_config=llm_config,
        standard_sets=get_available_standard_sets(),
        current_standard_set=config.get("standard_set", "sol"),
        pixabay_configured=pixabay_configured,
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
        if provider_name in ("gemini", "gemini-pro", "gemini-3-flash", "gemini-3-pro") and api_key:
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
    except ProviderError as pe:
        return jsonify(
            {
                "success": False,
                "message": pe.user_message,
                "error_code": pe.error_code,
                "latency_ms": 0,
            }
        )
    except Exception as e:
        error_msg = str(e)
        # Add helpful context for common errors
        lower_msg = error_msg.lower()
        if "401" in error_msg or "unauthorized" in lower_msg or ("invalid" in lower_msg and "key" in lower_msg):
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


# --- Pixabay Settings (form-based) ---


@settings_bp.route("/settings/pixabay", methods=["POST"])
@login_required
def settings_pixabay():
    """Save or clear Pixabay API key from the settings page form."""
    from src.web.config_utils import save_api_key_to_env

    api_key = request.form.get("pixabay_api_key", "").strip()
    if api_key:
        save_api_key_to_env("PIXABAY_API_KEY", api_key)
        os.environ["PIXABAY_API_KEY"] = api_key
        flash("Pixabay API key saved.", "success")
    else:
        save_api_key_to_env("PIXABAY_API_KEY", "")
        os.environ.pop("PIXABAY_API_KEY", None)
        flash("Pixabay API key cleared.", "success")

    return redirect(url_for("settings.settings"), code=303)


# --- Pixabay Setup Wizard ---


@settings_bp.route("/settings/pixabay-wizard")
@login_required
def pixabay_wizard():
    """Guided step-by-step Pixabay API key setup wizard."""
    return render_template("pixabay_wizard.html")


@settings_bp.route("/api/settings/test-pixabay", methods=["POST"])
@login_required
def test_pixabay():
    """Test a Pixabay API key without saving it."""
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()

    if not api_key:
        return jsonify({"success": False, "message": "API key is required."})

    import requests as http_requests

    try:
        resp = http_requests.get(
            "https://pixabay.com/api/",
            params={"key": api_key, "q": "test", "per_page": 3},
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()
        if "hits" in result:
            return jsonify({"success": True, "message": "Pixabay API key is valid."})
        else:
            return jsonify({"success": False, "message": "Unexpected response from Pixabay API."})
    except Exception:
        logger.exception("Pixabay API test failed")
        return jsonify({"success": False, "message": "Could not connect to Pixabay. Check your API key."})


@settings_bp.route("/api/settings/save-pixabay", methods=["POST"])
@login_required
def save_pixabay():
    """Save a Pixabay API key to .env."""
    from src.web.config_utils import save_api_key_to_env

    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()

    if not api_key:
        return jsonify({"success": False, "message": "API key is required."})

    save_api_key_to_env("PIXABAY_API_KEY", api_key)
    os.environ["PIXABAY_API_KEY"] = api_key

    return jsonify({"success": True, "message": "Pixabay API key saved."})


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

    # Build set of verified standard IDs:
    # 1. Standards with source document excerpts (uploaded PDFs)
    # 2. Standards with curriculum framework content (enrichment data)
    from src.database import Standard, StandardExcerpt

    verified_rows = (
        session.query(StandardExcerpt.standard_id)
        .distinct()
        .all()
    )
    verified_ids = {row[0] for row in verified_rows}

    # Also mark standards with enrichment data as verified
    enriched_rows = (
        session.query(Standard.id)
        .filter(
            (Standard.essential_knowledge.isnot(None) & (Standard.essential_knowledge != '[]') & (Standard.essential_knowledge != '')) |
            (Standard.essential_understandings.isnot(None) & (Standard.essential_understandings != '[]') & (Standard.essential_understandings != ''))
        )
        .all()
    )
    verified_ids.update(row[0] for row in enriched_rows)

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
        verified_ids=verified_ids,
    )


@settings_bp.route("/standards/<int:standard_id>")
@login_required
def standard_detail(standard_id):
    """Show full curriculum framework content for a single standard."""
    import json as _json

    from src.database import Standard

    session = _get_session()
    standard = session.get(Standard, standard_id)
    if not standard:
        from flask import abort

        abort(404)

    # Parse JSON arrays for template
    ek = _json.loads(standard.essential_knowledge) if standard.essential_knowledge else []
    eu = _json.loads(standard.essential_understandings) if standard.essential_understandings else []
    es = _json.loads(standard.essential_skills) if standard.essential_skills else []

    # Find sub-standards (standards whose code starts with this one + letter)
    sub_standards = []
    if standard.code:
        prefix = standard.code
        sub_standards = (
            session.query(Standard)
            .filter(Standard.code.like(prefix + "%"), Standard.code != prefix)
            .order_by(Standard.code)
            .all()
        )

    # Load provenance data (excerpts grouped by content_type)
    from src.database import StandardExcerpt
    from src.source_documents import get_excerpts_for_standard, list_source_documents

    provenance = get_excerpts_for_standard(session, standard_id)

    # Verification: source document excerpts OR enrichment data
    excerpt_count = session.query(StandardExcerpt).filter_by(standard_id=standard_id).count()
    has_enrichment = bool(ek or eu)
    is_verified = excerpt_count > 0 or has_enrichment

    # Load source metadata (official URL, related uploaded documents)
    from src.standards import STANDARD_SET_METADATA, STANDARD_SETS

    set_key = standard.standard_set or "sol"
    set_meta = STANDARD_SET_METADATA.get(set_key, {})
    set_info = STANDARD_SETS.get(set_key, {})
    source_meta = {
        "label": set_info.get("label", standard.source or ""),
        "url": set_meta.get("url", ""),
        "state": set_meta.get("state", ""),
        "adopted_year": set_meta.get("adopted_year"),
    }

    # Find uploaded source documents for this standard set
    related_docs = list_source_documents(session, standard_set=set_key)

    return render_template(
        "standards/detail.html",
        standard=standard,
        essential_knowledge=ek,
        essential_understandings=eu,
        essential_skills=es,
        sub_standards=sub_standards,
        provenance=provenance,
        source_meta=source_meta,
        related_docs=related_docs,
        is_verified=is_verified,
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
    total_results = len(results)
    limited = results[:50]
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
                for std in limited
            ],
            "total": total_results,
            "truncated": total_results > 50,
        }
    )


@settings_bp.route("/api/standards/<int:standard_id>/preview")
@login_required
def api_standard_preview(standard_id):
    """Return full standard content + provenance for inline preview."""
    import json as _json

    from src.database import Standard
    from src.source_documents import get_excerpts_for_standard

    session = _get_session()
    standard = session.get(Standard, standard_id)
    if not standard:
        from flask import abort

        abort(404)

    ek = _json.loads(standard.essential_knowledge) if standard.essential_knowledge else []
    eu = (
        _json.loads(standard.essential_understandings)
        if standard.essential_understandings
        else []
    )
    es = _json.loads(standard.essential_skills) if standard.essential_skills else []
    provenance = get_excerpts_for_standard(session, standard_id)

    return jsonify(
        {
            "id": standard.id,
            "code": standard.code,
            "description": standard.description,
            "essential_knowledge": ek,
            "essential_understandings": eu,
            "essential_skills": es,
            "provenance": provenance,
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


# --- User Management (admin only) ---


def _require_admin():
    """Check if the current user is an admin. Returns None if OK, or a redirect response."""
    from flask import session as flask_session

    role = flask_session.get("role", "teacher")
    if role != "admin":
        flash("Admin access required.", "error")
        return redirect(url_for("main.dashboard"), code=303)
    return None


@settings_bp.route("/settings/users")
@login_required
def users():
    """List all users (admin only)."""
    denied = _require_admin()
    if denied:
        return denied

    from src.database import User

    session = _get_session()
    all_users = session.query(User).order_by(User.id).all()
    return render_template("settings/users.html", users=all_users)


@settings_bp.route("/settings/users/add", methods=["POST"])
@login_required
def add_user():
    """Create a new user (admin only)."""
    denied = _require_admin()
    if denied:
        return denied

    session = _get_session()
    username = request.form.get("username", "").strip()
    display_name = request.form.get("display_name", "").strip() or None
    password = request.form.get("password", "")
    password_confirm = request.form.get("password_confirm", "")
    role = request.form.get("role", "teacher")

    if not username:
        flash("Username is required.", "error")
        return redirect(url_for("settings.users"), code=303)
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("settings.users"), code=303)
    if password != password_confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for("settings.users"), code=303)
    if role not in ("teacher", "admin"):
        role = "teacher"

    user = create_user(session, username, password, display_name=display_name, role=role)
    if user:
        flash(f"User '{user.username}' created.", "success")
    else:
        flash(f"Username '{username}' already exists.", "error")

    return redirect(url_for("settings.users"), code=303)


# --- Source Documents ---


@settings_bp.route("/standards/source-documents")
@login_required
def source_documents():
    """List all registered source documents."""
    from src.source_documents import list_source_documents

    session = _get_session()
    docs = list_source_documents(session)
    return render_template("standards/source_documents.html", documents=docs)


@settings_bp.route("/standards/source-documents/upload", methods=["POST"])
@login_required
def upload_source_document():
    """Upload a PDF source document, register it, and run extraction."""
    from src.source_documents import (
        SOURCE_DOCUMENTS_DIR,
        extract_columns_by_page,
        import_from_source_document,
        parse_sol_curriculum_framework,
        register_source_document,
    )

    session = _get_session()

    file = request.files.get("file")
    if not file or not file.filename:
        flash("No file selected.", "error")
        return redirect(url_for("settings.source_documents"), code=303)

    filename = secure_filename(file.filename)

    # Validate .pdf extension only
    if not filename.lower().endswith(".pdf"):
        flash("Only PDF files are allowed.", "error")
        return redirect(url_for("settings.source_documents"), code=303)

    title = request.form.get("title", "").strip() or filename
    standard_set = request.form.get("standard_set", "").strip() or None
    version = request.form.get("version", "").strip() or None

    # Save uploaded file to a temp location first, then register
    # (register_source_document copies it into data/source_documents/)
    os.makedirs(SOURCE_DOCUMENTS_DIR, exist_ok=True)
    temp_path = os.path.join(SOURCE_DOCUMENTS_DIR, filename)
    file.save(temp_path)

    try:
        doc = register_source_document(
            session,
            filepath=temp_path,
            title=title,
            standard_set=standard_set,
            version=version,
        )

        # Extract text using column-aware extraction for two-column PDFs
        pages_text = extract_columns_by_page(temp_path)
        parsed_data = parse_sol_curriculum_framework(pages_text)
        updated_count = import_from_source_document(
            session, doc.id, parsed_data
        )

        flash(
            f"Uploaded '{title}' ({doc.page_count or '?'} pages). "
            f"{updated_count} standard(s) updated with provenance data.",
            "success",
        )
    except Exception:
        logger.exception("Source document upload failed")
        flash("Upload failed. Check the file and try again.", "error")

    return redirect(url_for("settings.source_documents"), code=303)


@settings_bp.route("/standards/source-document/<int:doc_id>")
@login_required
def serve_source_document(doc_id):
    """Serve a source document PDF file for browser viewing."""
    from src.source_documents import SOURCE_DOCUMENTS_DIR, get_source_document

    session = _get_session()
    doc = get_source_document(session, doc_id)
    if not doc:
        from flask import abort

        abort(404)

    abs_dir = os.path.abspath(SOURCE_DOCUMENTS_DIR)

    # Support ?page=N by redirecting to the file URL with #page=N fragment
    page = request.args.get("page", type=int)
    if page:
        base_url = url_for("settings.serve_source_document", doc_id=doc_id)
        return redirect(f"{base_url}#page={page}")

    return send_from_directory(abs_dir, doc.filename, mimetype="application/pdf")


@settings_bp.route("/api/standards/<int:standard_id>/provenance")
@login_required
def api_standard_provenance(standard_id):
    """Return provenance excerpts for a standard as JSON."""
    from src.source_documents import get_excerpts_for_standard

    session = _get_session()
    grouped = get_excerpts_for_standard(session, standard_id)
    return jsonify(grouped)
