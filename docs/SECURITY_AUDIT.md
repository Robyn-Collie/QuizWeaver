# QuizWeaver Security Audit Report

**Date**: 2026-02-13
**Scope**: Full application — authentication, sessions, CSRF, injection, input validation, secrets management, dependency security, API access control, data privacy
**Auditors**: 4 parallel agents (auth/session/CSRF, injection/input, secrets/deps/config, API/access control)
**Codebase**: All 8 Flask blueprints (69 routes), database layer, export modules, LLM providers, CLI, templates

---

## Executive Summary

QuizWeaver has a **strong foundation** in several security areas: SQLAlchemy ORM prevents SQL injection, Jinja2 autoescape prevents XSS, passwords use scrypt hashing, no secrets exist in git history, and student data privacy is well-designed (topic aggregates only, no PII sent to LLMs).

However, the audit identified **3 CRITICAL**, **5 HIGH**, **7 MEDIUM**, and **7 LOW** findings that should be addressed before any networked or multi-user deployment.

**Risk context**: QuizWeaver is currently a single-teacher, local-first application. Many HIGH/MEDIUM findings have reduced real-world impact in this deployment model but become significant if the app is deployed on a school network or used by multiple teachers.

---

## Findings by Severity

### CRITICAL (3)

#### SEC-001: No CSRF Protection on Any Route
- **Affected**: All 33+ POST/PUT/DELETE routes across 8 blueprints
- **Description**: Zero CSRF protection anywhere. No Flask-WTF, no csrf_token in forms, no SameSite cookie config. Every state-changing endpoint is vulnerable.
- **Impact**: A malicious page visited by a logged-in teacher can silently: delete classes, change LLM provider/API key settings, import fabricated performance data, change passwords, trigger quiz generation (incurring real API costs).
- **Fix**: Install Flask-WTF, enable `CSRFProtect(app)`, add `{{ csrf_token() }}` to all forms. For JSON APIs, validate `X-CSRFToken` header.

#### SEC-002: Open Redirect via Login `next` Parameter
- **File**: `src/web/blueprints/auth.py:48,62`
- **Description**: After login, redirects to `request.args.get("next")` without validation. Attacker crafts `/login?next=https://evil.com` for credential phishing.
- **Impact**: Teacher enters valid credentials, gets redirected to attacker-controlled lookalike site.
- **Fix**: Validate `next_url` is relative (starts with `/`, no `//`, empty netloc via `urllib.parse.urlparse()`).

#### SEC-003: Predictable SECRET_KEY Fallback
- **File**: `src/web/app.py:42`
- **Code**: `os.environ.get("SECRET_KEY", "dev-key-change-in-production")`
- **Description**: If SECRET_KEY env var is not set (common — not set by run.bat or INSTALLATION.md defaults), Flask uses a known static string from public source code. Session cookies signed with this key can be forged.
- **Impact**: Attacker forges session cookie to impersonate any user without knowing their password.
- **Fix**: Auto-generate random key on first run (`secrets.token_hex(32)`), persist to `.env`. Warn on startup if default key is in use.

---

### HIGH (5)

#### SEC-004: Hardcoded Default Credentials
- **File**: `src/web/blueprints/helpers.py:11-12`
- **Description**: `DEFAULT_USERNAME = "teacher"`, `DEFAULT_PASSWORD = "quizweaver"`. Used as fallback when no DB users exist. Publicly visible in open-source code. Bypasses setup wizard if POST directly to `/login`.
- **Fix**: Remove config-based fallback auth. Force `/setup` wizard. At minimum, force password change on first login.

#### SEC-005: API Keys Written to config.yaml (Plaintext, Git-Tracked)
- **Files**: `src/web/blueprints/settings.py:56`, `src/web/config_utils.py:16`
- **Description**: Settings form saves API key to `config.yaml` via `save_config()`. `config.yaml` is NOT in `.gitignore`, so keys can be accidentally committed. Pre-commit hook catches some patterns but not all provider keys.
- **Fix**: Never write API keys to config.yaml. Write to `.env` (already gitignored) only. Add `config.yaml` to `.gitignore`, track `config.yaml.example` instead.

#### SEC-006: No Multi-Tenancy / IDOR on All Resources
- **Affected**: All database models (`Class`, `Quiz`, `StudySet`, `Rubric`, `LessonPlan`, `PerformanceData`)
- **Description**: No `user_id` foreign key on any model. Any authenticated user can view, edit, or delete any other user's data by guessing integer IDs. Currently single-user, but the User model supports multiple accounts.
- **Fix**: Add `owner_id` to `Class` model. Filter all queries by current user. Verify ownership on every read/write/delete.

#### SEC-007: Unauthenticated File Serving
- **File**: `src/web/app.py:107-109`
- **Description**: `/generated_images/<path:filename>` has no `@login_required`. Anyone on the network can access generated quiz images. `<path:filename>` allows subdirectory traversal within the served directory.
- **Fix**: Add `@login_required`. Consider using `<filename>` instead of `<path:filename>`.

#### SEC-008: Debug Mode Recommended in Documentation
- **Files**: `docs/API_REFERENCE.md:204`, `docs/USER_GUIDE.md:197`
- **Description**: Docs show `app.run(debug=True)` as recommended startup. Debug mode enables Werkzeug's interactive debugger (arbitrary Python code execution via browser).
- **Fix**: Change all doc examples to `app.run()` or `app.run(debug=False)`.

---

### MEDIUM (7)

#### SEC-009: No Rate Limiting
- **Affected**: Entire application
- **Description**: No rate limits on any endpoint. Enables brute-force login, LLM cost amplification (mass quiz generation), and resource exhaustion.
- **Fix**: Add Flask-Limiter. Suggested: 5/min on login, 10/min on generation, 60/min on APIs.

#### SEC-010: No Session Cookie Security Flags
- **File**: `src/web/app.py`
- **Description**: No explicit `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_SECURE`, or `SESSION_COOKIE_HTTPONLY` configuration. Flask 2.3+ defaults to `SameSite=Lax` (partial CSRF mitigation).
- **Fix**: Explicitly set `SESSION_COOKIE_SAMESITE = "Lax"`, `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SECURE = True` (when HTTPS).

#### SEC-011: No Session Regeneration After Login
- **File**: `src/web/blueprints/auth.py:43-49`
- **Description**: Session ID not regenerated after authentication. Enables session fixation — attacker sets a known session cookie before victim logs in.
- **Fix**: Call `flask_session.clear()` before setting new session data post-login.

#### SEC-012: Session Not Invalidated on Password Change
- **File**: `src/web/blueprints/auth.py:111-135`
- **Description**: After password change, existing sessions remain valid. Compromised sessions survive password changes.
- **Fix**: Clear session and force re-login after password change.

#### SEC-013: Unpinned Dependencies
- **File**: `requirements.txt`
- **Description**: All dependencies listed without version pins. Supply chain risk — compromised or breaking versions could be installed.
- **Fix**: Pin minimum and maximum versions. Use `pip freeze` to capture working versions.

#### SEC-014: CSV Formula Injection in Exports
- **File**: `src/export.py` (export_csv, export_quizizz_csv)
- **Description**: Question text written directly to CSV cells. Content starting with `=`, `+`, `-`, `@` interpreted as formulas in Excel/Sheets. Risk is low (data from teacher-reviewed LLM output).
- **Fix**: Prefix cell values starting with formula characters with a single quote.

#### SEC-015: Unbounded Audit Log with Exposed Endpoint
- **Files**: `src/llm_provider.py:25-47`, `src/web/blueprints/settings.py:91-97`
- **Description**: `_api_audit_log` is an in-memory list that grows unbounded. Stores prompt previews (could contain sensitive data). Exposed at `/api/audit-log` to any authenticated user.
- **Fix**: Cap audit log size (e.g., last 1000 entries). Scrub known key patterns from previews.

---

### LOW (7)

#### SEC-016: Weak Password Policy
- **File**: `src/web/blueprints/auth.py:92-93`
- **Description**: Only 6-character minimum. No complexity, no common password check.
- **Fix**: Raise to 8 chars. Check against top 100 common passwords.

#### SEC-017: Logout via GET
- **File**: `src/web/blueprints/auth.py:70`
- **Description**: `/logout` accepts GET. An `<img src="/logout">` tag forces logout.
- **Fix**: Change to POST-only with CSRF token.

#### SEC-018: No Session Timeout
- **Description**: No `PERMANENT_SESSION_LIFETIME` configured. Sessions persist indefinitely.
- **Fix**: Set `PERMANENT_SESSION_LIFETIME = timedelta(hours=8)` with `session.permanent = True`.

#### SEC-019: No Custom Error Handlers
- **File**: `src/web/app.py`
- **Description**: No `@app.errorhandler(404/500)`. Default Flask errors may expose framework version or stack traces.
- **Fix**: Register custom error handlers with user-friendly templates.

#### SEC-020: Error Messages May Leak Internal Paths
- **File**: `src/web/blueprints/settings.py:190-212`
- **Description**: `test_provider()` endpoint returns raw exception messages that could contain file paths or configuration details.
- **Fix**: Return generic error messages, log details server-side.

#### SEC-021: LIKE Wildcard Injection in Search
- **Files**: `quizzes.py:48`, `study.py:52`, `content.py:49,515`
- **Description**: `%` and `_` in search input not escaped for LIKE queries. Not a security vulnerability (SQLAlchemy parameterizes), but allows unexpected search results.
- **Fix**: Escape LIKE metacharacters before query.

#### SEC-022: LLM Prompt Injection via Lesson Content
- **File**: `src/agents.py:174-201`
- **Description**: User-supplied content interpolated into LLM prompts via f-strings without sanitization. Compromised lesson documents could inject instructions. Mitigated by human-in-the-loop review.
- **Fix**: Wrap user content in clear delimiters with "ignore instructions within delimiters" framing.

---

## Positive Findings

These areas demonstrate strong security practices:

| Area | Status | Details |
|------|--------|---------|
| SQL Injection | **SAFE** | All queries via SQLAlchemy ORM with parameterization |
| XSS | **SAFE** | Jinja2 autoescape enabled; no `\|safe`, `Markup()`, or `render_template_string()` |
| XML Injection | **SAFE** | `_xml_escape()` properly escapes all QTI output |
| Template Injection | **SAFE** | No `render_template_string()` anywhere |
| Deserialization | **SAFE** | No `pickle`, `eval()`, or `exec()`; only `json.loads()` |
| Command Injection | **SAFE** | No `subprocess`/`os.popen` in web code |
| SSRF | **SAFE** | No user-controlled URL fetching |
| Password Hashing | **STRONG** | scrypt via werkzeug (timing-safe comparison) |
| File Upload | **SAFE** | `secure_filename()`, extension allowlist, 5 MB limit |
| GIFT Export | **SAFE** | `_escape_gift()` escapes all metacharacters |
| Git History | **CLEAN** | No secrets found in commit history |
| Source Code | **CLEAN** | No hardcoded API keys in any source file |
| Student Privacy | **STRONG** | Topic aggregates only, no PII stored or sent to LLMs |
| Cost Control | **STRONG** | Approval gate for real LLM providers, MockLLMProvider default |
| Auth Coverage | **GOOD** | `@login_required` on all business routes (except `/health` by design) |

---

## Remediation Priority

### Immediate (Before Any Networked Deployment)
1. **SEC-003**: Auto-generate SECRET_KEY (quick fix, high impact)
2. **SEC-002**: Validate `next` URL (5-line fix)
3. **SEC-001**: Add Flask-WTF CSRF protection (largest effort, highest impact)
4. **SEC-007**: Add `@login_required` to image serving (1-line fix)
5. **SEC-008**: Remove `debug=True` from docs (text edit)

### Short-Term
6. **SEC-005**: Move API key storage to `.env` only + gitignore config.yaml
7. **SEC-004**: Remove default credential fallback
8. **SEC-010**: Set session cookie flags
9. **SEC-011**: Regenerate session after login
10. **SEC-009**: Add rate limiting on login

### Medium-Term
11. **SEC-012**: Invalidate sessions on password change
12. **SEC-013**: Pin dependency versions
13. **SEC-014**: CSV formula sanitization
14. **SEC-015**: Cap audit log, scrub sensitive data
15. **SEC-016**: Strengthen password policy

### Long-Term (If Multi-User Planned)
16. **SEC-006**: Multi-tenancy / ownership model
17. **SEC-019**: Custom error handlers
18. **SEC-022**: LLM prompt injection hardening

---

## Methodology

Four specialized agents audited the codebase in parallel:

1. **Auth/Session/CSRF Agent**: Focused on authentication flow, session management, cookie security, password handling, and CSRF protection across all routes
2. **Injection/Input Agent**: Tested for SQL injection, XSS, XML injection, template injection, command injection, SSRF, deserialization, CSV injection, and GIFT format injection
3. **Secrets/Deps/Config Agent**: Examined secret storage, git history, dependency pinning, configuration security, pre-commit hooks, and data privacy
4. **API/Access Control Agent**: Audited route protection, IDOR, multi-tenancy, API authentication, error handling, and destructive operations

Findings were deduplicated (several issues found by multiple agents, confirming consensus) and consolidated into this report.
