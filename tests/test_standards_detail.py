"""Tests for the standards detail page and curriculum framework content."""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, Standard, get_engine, get_session


@pytest.fixture
def app_with_standards():
    """Flask app with standards including curriculum framework content."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Science 7",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps([]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    # Standard with full curriculum content
    s1 = Standard(
        code="SOL LS.2",
        standard_id="SOL LS.2",
        description="All living things are composed of cells",
        subject="Science",
        grade_band="6-8",
        strand="Life Science",
        full_text="The student will investigate and understand that all living things are composed of cells.",
        source="Virginia SOL",
        version="2023",
        standard_set="sol",
        essential_knowledge=json.dumps([
            "The cell theory states that all living things are made of cells.",
            "Cell structures include: cell membrane, nucleus, cytoplasm, mitochondria.",
        ]),
        essential_understandings=json.dumps([
            "The cell is the basic unit of life.",
            "Plant and animal cells have important differences.",
        ]),
        essential_skills=json.dumps([
            "Compare and contrast plant and animal cells.",
            "Identify cell organelles and describe their functions.",
        ]),
    )

    # Standard without curriculum content
    s2 = Standard(
        code="SOL 3.1",
        standard_id="SOL 3.1",
        description="Read and write six-digit numerals",
        subject="Mathematics",
        grade_band="3-5",
        strand="Number and Number Sense",
        full_text="The student will read, write, and identify the place and value of each digit.",
        source="Virginia SOL",
        version="2023",
        standard_set="sol",
    )

    # Sub-standard of LS.2
    s3 = Standard(
        code="SOL LS.2a",
        standard_id="SOL LS.2a",
        description="Cell membrane regulates transport",
        subject="Science",
        grade_band="6-8",
        strand="Life Science",
        full_text="The student will understand the role of the cell membrane.",
        source="Virginia SOL",
        version="2023",
        standard_set="sol",
    )

    session.add_all([s1, s2, s3])
    session.commit()

    s1_id = s1.id
    s2_id = s2.id
    s3_id = s3.id

    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path, "upload_dir": tempfile.mkdtemp()},
        "llm": {"provider": "mock"},
        "generation": {
            "default_grade_level": "7th Grade Science",
            "quiz_title": "Test",
            "sol_standards": [],
            "target_image_ratio": 0.0,
            "generate_ai_images": False,
            "interactive_review": False,
        },
    }
    app = create_app(test_config)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["_test_ids"] = {"s1_id": s1_id, "s2_id": s2_id, "s3_id": s3_id}

    yield app

    app.config["DB_ENGINE"].dispose()
    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app_with_standards):
    with app_with_standards.test_client() as c:
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        c._app = app_with_standards
        yield c


@pytest.fixture
def anon_client(app_with_standards):
    with app_with_standards.test_client() as c:
        c._app = app_with_standards
        yield c


class TestStandardDetailRoute:
    """Test the /standards/<id> detail page."""

    def test_detail_page_returns_200(self, client):
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/standards/{ids['s1_id']}")
        assert resp.status_code == 200

    def test_detail_requires_login(self, anon_client):
        ids = anon_client._app.config["_test_ids"]
        resp = anon_client.get(f"/standards/{ids['s1_id']}")
        assert resp.status_code == 303

    def test_detail_404_for_missing(self, client):
        resp = client.get("/standards/99999")
        assert resp.status_code == 404

    def test_detail_shows_code_and_description(self, client):
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/standards/{ids['s1_id']}")
        html = resp.data.decode()
        assert "SOL LS.2" in html
        assert "All living things are composed of cells" in html

    def test_detail_shows_essential_knowledge(self, client):
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/standards/{ids['s1_id']}")
        html = resp.data.decode()
        assert "Essential Knowledge" in html
        assert "cell theory" in html
        assert "cell membrane" in html

    def test_detail_shows_essential_understandings(self, client):
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/standards/{ids['s1_id']}")
        html = resp.data.decode()
        assert "Essential Understandings" in html
        assert "basic unit of life" in html

    def test_detail_shows_essential_skills(self, client):
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/standards/{ids['s1_id']}")
        html = resp.data.decode()
        assert "Essential Skills" in html
        assert "Compare and contrast" in html

    def test_detail_shows_copy_buttons(self, client):
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/standards/{ids['s1_id']}")
        html = resp.data.decode()
        assert "copy-btn" in html
        assert "Copy" in html

    def test_detail_shows_use_in_prompt_button(self, client):
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/standards/{ids['s1_id']}")
        html = resp.data.decode()
        assert "use-in-prompt-btn" in html
        assert "Use in Quiz Prompt" in html

    def test_detail_without_curriculum_content(self, client):
        """Standard without essential_knowledge etc. still renders fine."""
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/standards/{ids['s2_id']}")
        html = resp.data.decode()
        assert resp.status_code == 200
        assert "SOL 3.1" in html
        assert "Essential Knowledge" not in html

    def test_detail_shows_sub_standards(self, client):
        """Parent standard shows sub-standards."""
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/standards/{ids['s1_id']}")
        html = resp.data.decode()
        assert "Sub-standards" in html
        assert "SOL LS.2a" in html
        assert "Cell membrane regulates transport" in html

    def test_detail_no_sub_standards_when_none(self, client):
        """Standard without sub-standards doesn't show the section."""
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/standards/{ids['s2_id']}")
        html = resp.data.decode()
        assert "Sub-standards" not in html


class TestStandardsTableClickable:
    """Test that standards table rows link to detail pages."""

    def test_table_rows_are_clickable(self, client):
        resp = client.get("/standards")
        html = resp.data.decode()
        ids = client._app.config["_test_ids"]
        assert f"/standards/{ids['s1_id']}" in html
        assert "cursor:pointer" in html


class TestStandardPreviewAPI:
    """Test the /api/standards/<id>/preview JSON endpoint."""

    def test_preview_returns_json(self, client):
        ids = client._app.config["_test_ids"]
        resp = client.get(f"/api/standards/{ids['s1_id']}/preview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == "SOL LS.2"
        assert data["description"] == "All living things are composed of cells"

    def test_preview_includes_essential_knowledge(self, client):
        ids = client._app.config["_test_ids"]
        data = client.get(f"/api/standards/{ids['s1_id']}/preview").get_json()
        assert len(data["essential_knowledge"]) == 2
        assert "cell theory" in data["essential_knowledge"][0].lower()

    def test_preview_includes_essential_understandings(self, client):
        ids = client._app.config["_test_ids"]
        data = client.get(f"/api/standards/{ids['s1_id']}/preview").get_json()
        assert len(data["essential_understandings"]) == 2

    def test_preview_includes_essential_skills(self, client):
        ids = client._app.config["_test_ids"]
        data = client.get(f"/api/standards/{ids['s1_id']}/preview").get_json()
        assert len(data["essential_skills"]) == 2

    def test_preview_empty_for_standard_without_content(self, client):
        ids = client._app.config["_test_ids"]
        data = client.get(f"/api/standards/{ids['s2_id']}/preview").get_json()
        assert data["essential_knowledge"] == []
        assert data["essential_understandings"] == []
        assert data["essential_skills"] == []

    def test_preview_includes_provenance_key(self, client):
        ids = client._app.config["_test_ids"]
        data = client.get(f"/api/standards/{ids['s1_id']}/preview").get_json()
        assert "provenance" in data

    def test_preview_404_for_missing_standard(self, client):
        resp = client.get("/api/standards/99999/preview")
        assert resp.status_code == 404

    def test_preview_requires_login(self, anon_client):
        ids = anon_client._app.config["_test_ids"]
        resp = anon_client.get(f"/api/standards/{ids['s1_id']}/preview")
        assert resp.status_code == 303
