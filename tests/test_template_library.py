"""
Tests for the Community Template Library feature (BL-039 stretch).

Covers:
- Listing built-in templates
- Loading templates by ID
- Searching/filtering templates by subject, grade, tags, and free text
- Template preview (limited questions + metadata)
- Saving user templates (validation, dedup, filesystem)
- Web routes: library browse, preview, use, upload
- Built-in template validation (all shipped templates pass validate_template)
- Edge cases: missing templates, bad IDs, path traversal
"""

import json
import os
import shutil
import tempfile

import pytest

from src.template_library import (
    BUILT_IN_TEMPLATES_DIR,
    get_template,
    get_template_preview,
    list_templates,
    save_user_template,
    search_templates,
)
from src.template_manager import validate_template

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def user_template_dir():
    """Create a temporary directory for user templates, cleaned up after test."""
    tmpdir = tempfile.mkdtemp(prefix="qw_user_templates_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def sample_user_template():
    """Return a minimal valid template dict for user upload tests."""
    return {
        "template_version": "1.0",
        "title": "User Custom Template",
        "subject": "History",
        "grade_level": "10th Grade",
        "question_count": 2,
        "questions": [
            {
                "question_type": "mc",
                "text": "Who was the first president of the United States?",
                "options": [
                    "George Washington",
                    "John Adams",
                    "Thomas Jefferson",
                    "Benjamin Franklin",
                ],
                "correct_answer": "George Washington",
                "points": 1,
            },
            {
                "question_type": "tf",
                "text": "The Declaration of Independence was signed in 1776.",
                "correct_answer": "True",
                "points": 1,
            },
        ],
        "metadata": {
            "created_by": "Test Teacher",
            "tags": ["history", "american history", "10th grade"],
            "description": "A short quiz on early American history.",
        },
    }


# ============================================================
# TestListTemplates
# ============================================================


class TestListTemplates:
    """Tests for list_templates()."""

    def test_list_includes_builtin_templates(self):
        """Built-in templates should be returned when include_builtin=True."""
        templates = list_templates(include_builtin=True)
        assert len(templates) >= 6
        ids = [t["id"] for t in templates]
        assert "elementary_science_mc" in ids
        assert "sol_life_science_7" in ids

    def test_list_excludes_builtin_when_disabled(self, user_template_dir):
        """Setting include_builtin=False should exclude built-in templates."""
        templates = list_templates(include_builtin=False, user_dir=user_template_dir)
        assert len(templates) == 0

    def test_list_includes_user_templates(self, user_template_dir, sample_user_template):
        """User templates from the user_dir should be listed."""
        filepath = os.path.join(user_template_dir, "my_template.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sample_user_template, f)

        templates = list_templates(include_builtin=False, user_dir=user_template_dir)
        assert len(templates) == 1
        assert templates[0]["id"] == "my_template"
        assert templates[0]["source"] == "user"

    def test_list_sorted_by_title(self):
        """Templates should be sorted alphabetically by title."""
        templates = list_templates()
        titles = [t["title"] for t in templates]
        assert titles == sorted(titles, key=str.lower)

    def test_list_summary_fields(self):
        """Each template summary should have required fields."""
        templates = list_templates()
        assert len(templates) > 0
        for t in templates:
            assert "id" in t
            assert "title" in t
            assert "subject" in t
            assert "grade_level" in t
            assert "question_count" in t
            assert "tags" in t
            assert "source" in t

    def test_list_nonexistent_user_dir(self):
        """A nonexistent user_dir should not cause errors."""
        templates = list_templates(
            include_builtin=True,
            user_dir="/nonexistent/path/to/templates",
        )
        # Should still have built-in templates
        assert len(templates) >= 6


# ============================================================
# TestGetTemplate
# ============================================================


class TestGetTemplate:
    """Tests for get_template()."""

    def test_get_builtin_template(self):
        """Should load a built-in template by ID."""
        data = get_template("elementary_science_mc")
        assert data is not None
        assert data["title"] == "Elementary Science: States of Matter"
        assert data["_source"] == "builtin"
        assert data["_id"] == "elementary_science_mc"

    def test_get_template_not_found(self):
        """Should return None for a nonexistent template ID."""
        data = get_template("nonexistent_template_xyz")
        assert data is None

    def test_get_template_path_traversal(self):
        """Path traversal attempts should be sanitized and return None."""
        data = get_template("../../../etc/passwd")
        assert data is None

    def test_get_template_empty_id(self):
        """Empty template ID should return None."""
        data = get_template("")
        assert data is None

    def test_get_template_special_chars(self):
        """IDs with special characters should be sanitized."""
        data = get_template("test/../../file")
        assert data is None

    def test_get_user_template(self, user_template_dir, sample_user_template):
        """Should load a user template by ID."""
        filepath = os.path.join(user_template_dir, "custom_quiz.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sample_user_template, f)

        data = get_template("custom_quiz", user_dir=user_template_dir)
        assert data is not None
        assert data["_source"] == "user"
        assert data["title"] == "User Custom Template"

    def test_builtin_takes_precedence_over_user(self, user_template_dir, sample_user_template):
        """Built-in template should be returned if both exist with same ID."""
        # Write a user template with the same name as a built-in
        filepath = os.path.join(user_template_dir, "elementary_science_mc.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sample_user_template, f)

        data = get_template("elementary_science_mc", user_dir=user_template_dir)
        assert data is not None
        assert data["_source"] == "builtin"


# ============================================================
# TestSearchTemplates
# ============================================================


class TestSearchTemplates:
    """Tests for search_templates()."""

    def test_search_by_subject(self):
        """Filter by subject should return matching templates."""
        results = search_templates(subject="Science")
        assert len(results) >= 1
        for r in results:
            assert "science" in r["subject"].lower()

    def test_search_by_grade_level(self):
        """Filter by grade level should return matching templates."""
        results = search_templates(grade_level="7th")
        assert len(results) >= 1
        for r in results:
            assert "7th" in r["grade_level"].lower()

    def test_search_by_tag(self):
        """Filter by tag should return templates containing that tag."""
        results = search_templates(tags=["vocabulary"])
        assert len(results) >= 1
        for r in results:
            assert "vocabulary" in [t.lower() for t in r["tags"]]

    def test_search_by_query(self):
        """Free-text search should match title, description, tags."""
        results = search_templates(query="photosynthesis")
        # The sol_life_science_7 template mentions photosynthesis
        assert len(results) >= 1

    def test_search_combined_filters(self):
        """Multiple filters should be combined with AND logic."""
        results = search_templates(subject="Science", grade_level="7th")
        for r in results:
            assert "science" in r["subject"].lower()
            assert "7th" in r["grade_level"].lower()

    def test_search_no_results(self):
        """Search with impossible criteria should return empty list."""
        results = search_templates(subject="Underwater Basket Weaving")
        assert results == []

    def test_search_no_filters(self):
        """No filters should return all templates."""
        results = search_templates()
        all_templates = list_templates()
        assert len(results) == len(all_templates)

    def test_search_case_insensitive(self):
        """Searches should be case-insensitive."""
        results_lower = search_templates(subject="science")
        results_upper = search_templates(subject="SCIENCE")
        assert len(results_lower) == len(results_upper)


# ============================================================
# TestGetTemplatePreview
# ============================================================


class TestGetTemplatePreview:
    """Tests for get_template_preview()."""

    def test_preview_limits_questions(self):
        """Preview should only include max_questions questions."""
        preview = get_template_preview("elementary_science_mc", max_questions=3)
        assert preview is not None
        assert len(preview["questions_preview"]) == 3
        assert preview["question_count"] == 10

    def test_preview_metadata_fields(self):
        """Preview should include all expected metadata fields."""
        preview = get_template_preview("sol_life_science_7")
        assert preview is not None
        assert "title" in preview
        assert "subject" in preview
        assert "grade_level" in preview
        assert "question_count" in preview
        assert "question_types" in preview
        assert "total_points" in preview
        assert "tags" in preview
        assert "description" in preview
        assert "source" in preview

    def test_preview_question_types(self):
        """Preview should count question types correctly."""
        preview = get_template_preview("sol_life_science_7")
        assert preview is not None
        types = preview["question_types"]
        assert "mc" in types
        assert "tf" in types
        total_from_types = sum(types.values())
        assert total_from_types == preview["question_count"]

    def test_preview_not_found(self):
        """Preview of nonexistent template should return None."""
        preview = get_template_preview("nonexistent_template")
        assert preview is None

    def test_preview_custom_max(self):
        """Custom max_questions should limit preview size."""
        preview = get_template_preview("exit_ticket_quick", max_questions=1)
        assert preview is not None
        assert len(preview["questions_preview"]) == 1

    def test_preview_all_questions_if_fewer(self):
        """If template has fewer questions than max, show all."""
        preview = get_template_preview("exit_ticket_quick", max_questions=100)
        assert preview is not None
        assert len(preview["questions_preview"]) == preview["question_count"]


# ============================================================
# TestSaveUserTemplate
# ============================================================


class TestSaveUserTemplate:
    """Tests for save_user_template()."""

    def test_save_valid_template(self, user_template_dir, sample_user_template):
        """Valid template should be saved successfully."""
        success, template_id = save_user_template(
            sample_user_template, user_dir=user_template_dir
        )
        assert success is True
        assert template_id == "user_custom_template"

        # Verify file was created
        filepath = os.path.join(user_template_dir, f"{template_id}.json")
        assert os.path.isfile(filepath)

        # Verify content
        with open(filepath, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["title"] == "User Custom Template"

    def test_save_invalid_template(self, user_template_dir):
        """Invalid template should not be saved."""
        bad_template = {"title": "Missing questions"}
        success, error = save_user_template(bad_template, user_dir=user_template_dir)
        assert success is False
        assert "template_version" in error.lower() or "questions" in error.lower()

    def test_save_duplicate_increments_name(self, user_template_dir, sample_user_template):
        """Saving a template with the same title should create a numbered copy."""
        success1, id1 = save_user_template(
            sample_user_template, user_dir=user_template_dir
        )
        success2, id2 = save_user_template(
            sample_user_template, user_dir=user_template_dir
        )
        assert success1 is True
        assert success2 is True
        assert id1 != id2
        assert id2 == "user_custom_template_1"

    def test_save_creates_directory(self, user_template_dir, sample_user_template):
        """Should create the target directory if it does not exist."""
        subdir = os.path.join(user_template_dir, "nested", "dir")
        success, template_id = save_user_template(
            sample_user_template, user_dir=subdir
        )
        assert success is True
        assert os.path.isdir(subdir)

    def test_save_empty_title(self, user_template_dir):
        """Template with empty title should use 'untitled' as filename."""
        template = {
            "template_version": "1.0",
            "title": "",
            "questions": [
                {"question_type": "mc", "text": "Test?", "options": ["A", "B"], "correct_answer": "A", "points": 1}
            ],
        }
        success, template_id = save_user_template(template, user_dir=user_template_dir)
        assert success is True
        assert template_id == "untitled"


# ============================================================
# TestBuiltInTemplates
# ============================================================


class TestBuiltInTemplates:
    """Validate all built-in template JSON files pass validation."""

    def test_all_builtin_templates_valid(self):
        """Every file in data/templates/ should pass validate_template()."""
        template_dir = BUILT_IN_TEMPLATES_DIR
        assert os.path.isdir(template_dir), f"Built-in templates dir not found: {template_dir}"

        json_files = [f for f in os.listdir(template_dir) if f.endswith(".json")]
        assert len(json_files) >= 6, f"Expected at least 6 built-in templates, found {len(json_files)}"

        for filename in json_files:
            filepath = os.path.join(template_dir, filename)
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            is_valid, errors = validate_template(data)
            assert is_valid, f"{filename} failed validation: {errors}"

    def test_all_builtin_templates_have_metadata(self):
        """Every built-in template should have metadata with tags and description."""
        template_dir = BUILT_IN_TEMPLATES_DIR
        for filename in os.listdir(template_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(template_dir, filename)
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            metadata = data.get("metadata", {})
            assert "tags" in metadata, f"{filename} missing metadata.tags"
            assert "description" in metadata, f"{filename} missing metadata.description"
            assert "created_by" in metadata, f"{filename} missing metadata.created_by"
            assert len(metadata["tags"]) > 0, f"{filename} has empty tags"

    def test_all_builtin_templates_have_subject(self):
        """Every built-in template should have a subject field."""
        template_dir = BUILT_IN_TEMPLATES_DIR
        for filename in os.listdir(template_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(template_dir, filename)
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            assert data.get("subject"), f"{filename} missing subject"

    def test_builtin_template_question_counts_match(self):
        """question_count field should match actual questions list length."""
        template_dir = BUILT_IN_TEMPLATES_DIR
        for filename in os.listdir(template_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(template_dir, filename)
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            declared = data.get("question_count", 0)
            actual = len(data.get("questions", []))
            assert declared == actual, (
                f"{filename}: question_count={declared} but has {actual} questions"
            )


# ============================================================
# TestTemplateLibraryRoutes
# ============================================================


class TestTemplateLibraryRoutes:
    """Tests for the web routes in content.py for the template library."""

    @pytest.fixture
    def app(self):
        """Create a Flask test app for template library route tests."""
        db_fd, db_path = tempfile.mkstemp(suffix=".db")

        from src.database import Base, Class, get_engine, get_session

        engine = get_engine(db_path)
        Base.metadata.create_all(engine)
        session = get_session(engine)

        # Seed a class
        cls = Class(
            name="Test Class",
            grade_level="8th Grade",
            subject="Science",
            standards=json.dumps(["SOL 8.1"]),
            config=json.dumps({}),
        )
        session.add(cls)
        session.commit()
        session.close()
        engine.dispose()

        from src.web.app import create_app

        test_config = {
            "paths": {"database_file": db_path},
            "llm": {"provider": "mock"},
            "generation": {
                "default_grade_level": "8th Grade Science",
                "quiz_title": "Test Quiz",
                "sol_standards": [],
                "target_image_ratio": 0.0,
                "generate_ai_images": False,
                "interactive_review": False,
            },
        }
        app = create_app(test_config)
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        yield app

        app.config["DB_ENGINE"].dispose()
        os.close(db_fd)
        try:
            os.remove(db_path)
        except OSError:
            pass

    @pytest.fixture
    def client(self, app):
        """Provide a logged-in Flask test client."""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["username"] = "teacher"
            yield client

    @pytest.fixture
    def anon_client(self, app):
        """Provide an unauthenticated Flask test client."""
        with app.test_client() as client:
            yield client

    def test_library_page_loads(self, client):
        """GET /templates/library should return 200."""
        resp = client.get("/templates/library")
        assert resp.status_code == 200
        assert b"Community Template Library" in resp.data

    def test_library_shows_templates(self, client):
        """Library page should list built-in templates."""
        resp = client.get("/templates/library")
        assert resp.status_code == 200
        assert b"Elementary Science" in resp.data or b"elementary" in resp.data.lower()

    def test_library_filter_by_subject(self, client):
        """Filtering by subject should work."""
        resp = client.get("/templates/library?subject=Science")
        assert resp.status_code == 200

    def test_library_filter_by_query(self, client):
        """Free-text search should work."""
        resp = client.get("/templates/library?q=vocabulary")
        assert resp.status_code == 200

    def test_library_requires_login(self, anon_client):
        """Anonymous access should redirect to login."""
        resp = anon_client.get("/templates/library")
        assert resp.status_code == 303

    def test_preview_page_loads(self, client):
        """GET /templates/library/<id> should return 200 for valid ID."""
        resp = client.get("/templates/library/elementary_science_mc")
        assert resp.status_code == 200
        assert b"States of Matter" in resp.data

    def test_preview_not_found(self, client):
        """GET /templates/library/<bad_id> should return 404."""
        resp = client.get("/templates/library/nonexistent_template")
        assert resp.status_code == 404

    def test_preview_requires_login(self, anon_client):
        """Anonymous access to preview should redirect to login."""
        resp = anon_client.get("/templates/library/elementary_science_mc")
        assert resp.status_code == 303

    def test_use_template(self, client):
        """POST to use template should create quiz and redirect."""
        resp = client.post(
            "/templates/library/exit_ticket_quick/use",
            data={"class_id": 1, "title": "My Exit Ticket"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/quizzes/" in resp.headers.get("Location", "")

    def test_use_template_no_class(self, client):
        """POST without class_id should flash error and redirect back."""
        resp = client.post(
            "/templates/library/exit_ticket_quick/use",
            data={},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "template_library_preview" in resp.headers.get("Location", "") or "/templates/library/" in resp.headers.get("Location", "")

    def test_use_template_not_found(self, client):
        """POST to use nonexistent template should return 404."""
        resp = client.post(
            "/templates/library/nonexistent_template/use",
            data={"class_id": 1},
        )
        assert resp.status_code == 404

    def test_use_template_requires_login(self, anon_client):
        """Anonymous POST should redirect to login."""
        resp = anon_client.post(
            "/templates/library/exit_ticket_quick/use",
            data={"class_id": 1},
        )
        assert resp.status_code == 303

    def test_upload_page_loads(self, client):
        """GET /templates/library/upload should return 200."""
        resp = client.get("/templates/library/upload")
        assert resp.status_code == 200
        assert b"Upload Template" in resp.data

    def test_upload_requires_login(self, anon_client):
        """Anonymous access to upload page should redirect."""
        resp = anon_client.get("/templates/library/upload")
        assert resp.status_code == 303

    def test_upload_no_file(self, client):
        """POST without file should show error."""
        resp = client.post("/templates/library/upload", data={})
        assert resp.status_code == 200
        assert b"Please select a template file" in resp.data

    def test_upload_invalid_json(self, client):
        """POST with invalid JSON should show error."""
        from io import BytesIO

        data = {
            "template_file": (BytesIO(b"not json at all"), "bad.json"),
        }
        resp = client.post(
            "/templates/library/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert b"Invalid JSON" in resp.data

    def test_upload_invalid_template(self, client):
        """POST with JSON that fails validation should show error."""
        from io import BytesIO

        bad_template = json.dumps({"title": "No questions"}).encode("utf-8")
        data = {
            "template_file": (BytesIO(bad_template), "bad_template.json"),
        }
        resp = client.post(
            "/templates/library/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert b"validation failed" in resp.data.lower()
