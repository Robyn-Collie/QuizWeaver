"""Tests for cloze per-blank dropdown options in web UI and QTI export."""

import json
import os
import tempfile
import zipfile

import pytest

from src.database import Base, Class, Question, Quiz, get_engine, get_session
from src.export import export_qti


@pytest.fixture
def quiz_with_cloze(tmp_path):
    """Create a quiz with cloze questions — some blanks with options, some without."""
    db_path = str(tmp_path / "test.db")
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

    quiz = Quiz(
        title="Cloze Test Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "7th Grade"}),
    )
    session.add(quiz)
    session.commit()

    # Cloze with dropdown options on both blanks
    q1 = Question(
        quiz_id=quiz.id,
        question_type="cloze",
        title="Q1",
        text="Photosynthesis uses {{1}} to produce {{2}}.",
        points=4.0,
        data=json.dumps({
            "type": "cloze",
            "text": "Photosynthesis uses {{1}} to produce {{2}}.",
            "blanks": [
                {"id": "1", "answer": "sunlight", "alternatives": ["light"], "options": ["sunlight", "water", "carbon dioxide"]},
                {"id": "2", "answer": "glucose", "alternatives": [], "options": ["glucose", "oxygen", "ATP"]},
            ],
        }),
    )
    # Cloze without options (text input blanks)
    q2 = Question(
        quiz_id=quiz.id,
        question_type="cloze",
        title="Q2",
        text="The cell membrane is {{1}} permeable.",
        points=2.0,
        data=json.dumps({
            "type": "cloze",
            "text": "The cell membrane is {{1}} permeable.",
            "blanks": [
                {"id": "1", "answer": "selectively", "alternatives": ["semi"]},
            ],
        }),
    )
    # Cloze with mixed blanks — one dropdown, one text input
    q3 = Question(
        quiz_id=quiz.id,
        question_type="cloze",
        title="Q3",
        text="DNA stands for {{1}} acid, found in the {{2}}.",
        points=4.0,
        data=json.dumps({
            "type": "cloze",
            "text": "DNA stands for {{1}} acid, found in the {{2}}.",
            "blanks": [
                {"id": "1", "answer": "deoxyribonucleic", "alternatives": []},
                {"id": "2", "answer": "nucleus", "alternatives": [], "options": ["nucleus", "cytoplasm", "ribosome"]},
            ],
        }),
    )

    session.add_all([q1, q2, q3])
    session.commit()

    result = {
        "quiz": quiz,
        "questions": [q1, q2, q3],
    }

    yield result

    session.close()
    engine.dispose()


@pytest.fixture
def app_with_cloze():
    """Flask app with cloze questions for template rendering tests."""
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

    quiz = Quiz(
        title="Cloze Render Test",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "7th Grade"}),
    )
    session.add(quiz)
    session.commit()

    q1 = Question(
        quiz_id=quiz.id,
        question_type="cloze",
        title="Q1",
        text="Plants use {{1}} for energy.",
        points=2.0,
        data=json.dumps({
            "type": "cloze",
            "text": "Plants use {{1}} for energy.",
            "blanks": [
                {"id": "1", "answer": "sunlight", "alternatives": [], "options": ["sunlight", "water", "soil"]},
            ],
        }),
    )
    q2 = Question(
        quiz_id=quiz.id,
        question_type="cloze",
        title="Q2",
        text="Water is {{1}}.",
        points=2.0,
        data=json.dumps({
            "type": "cloze",
            "text": "Water is {{1}}.",
            "blanks": [
                {"id": "1", "answer": "essential", "alternatives": ["vital"]},
            ],
        }),
    )

    session.add_all([q1, q2])
    session.commit()

    quiz_id = quiz.id
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
    app.config["_test_quiz_id"] = quiz_id

    yield app

    app.config["DB_ENGINE"].dispose()
    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app_with_cloze):
    with app_with_cloze.test_client() as c:
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        c._app = app_with_cloze
        yield c


class TestClozeDropdownRendering:
    """Verify cloze dropdowns render correctly in the web UI."""

    def test_dropdown_rendered_for_blank_with_options(self, client):
        quiz_id = client._app.config["_test_quiz_id"]
        resp = client.get(f"/quizzes/{quiz_id}?skip_onboarding=1")
        html = resp.data.decode()
        assert resp.status_code == 200
        assert "cloze-dropdown" in html
        assert "<select" in html
        assert "sunlight" in html
        assert "water" in html
        assert "soil" in html

    def test_underline_rendered_for_blank_without_options(self, client):
        quiz_id = client._app.config["_test_quiz_id"]
        resp = client.get(f"/quizzes/{quiz_id}?skip_onboarding=1")
        html = resp.data.decode()
        assert "cloze-blank" in html
        assert "________" in html


class TestClozeQTIExportDropdown:
    """Verify QTI export uses correct format for dropdown vs text input blanks."""

    def test_dropdown_blank_uses_response_lid(self, quiz_with_cloze):
        d = quiz_with_cloze
        buf = export_qti(d["quiz"], d["questions"])
        with zipfile.ZipFile(buf) as zf:
            xml_files = [n for n in zf.namelist() if n.endswith(".xml") and n != "imsmanifest.xml"]
            assessment = zf.read(xml_files[0]).decode()
            # Q1 has dropdown options — should use response_lid + render_choice
            assert "response_lid" in assessment
            assert "render_choice" in assessment
            assert "response_label" in assessment

    def test_text_blank_uses_response_str(self, quiz_with_cloze):
        d = quiz_with_cloze
        buf = export_qti(d["quiz"], d["questions"])
        with zipfile.ZipFile(buf) as zf:
            xml_files = [n for n in zf.namelist() if n.endswith(".xml") and n != "imsmanifest.xml"]
            assessment = zf.read(xml_files[0]).decode()
            # Q2 has no options — should use response_str + render_fib
            assert "response_str" in assessment
            assert "render_fib" in assessment

    def test_mixed_blanks_both_formats(self, quiz_with_cloze):
        """Q3 has one text blank and one dropdown blank."""
        d = quiz_with_cloze
        buf = export_qti(d["quiz"], d["questions"])
        with zipfile.ZipFile(buf) as zf:
            xml_files = [n for n in zf.namelist() if n.endswith(".xml") and n != "imsmanifest.xml"]
            assessment = zf.read(xml_files[0]).decode()
            # Both formats should be present
            assert "response_lid" in assessment
            assert "response_str" in assessment

    def test_dropdown_options_in_xml(self, quiz_with_cloze):
        """Dropdown option text should appear in the QTI XML."""
        d = quiz_with_cloze
        buf = export_qti(d["quiz"], d["questions"])
        with zipfile.ZipFile(buf) as zf:
            xml_files = [n for n in zf.namelist() if n.endswith(".xml") and n != "imsmanifest.xml"]
            assessment = zf.read(xml_files[0]).decode()
            assert "sunlight" in assessment
            assert "carbon dioxide" in assessment
            assert "glucose" in assessment

    def test_correct_answer_condition(self, quiz_with_cloze):
        """The correct answer should have a respcondition with score."""
        d = quiz_with_cloze
        buf = export_qti(d["quiz"], d["questions"])
        with zipfile.ZipFile(buf) as zf:
            xml_files = [n for n in zf.namelist() if n.endswith(".xml") and n != "imsmanifest.xml"]
            assessment = zf.read(xml_files[0]).decode()
            assert "varequal" in assessment
            assert "SCORE" in assessment

    def test_backward_compat_no_options(self, quiz_with_cloze):
        """Existing cloze without options still works."""
        d = quiz_with_cloze
        # Q2 has no options, alternatives only
        buf = export_qti(d["quiz"], [d["questions"][1]])  # only Q2
        with zipfile.ZipFile(buf) as zf:
            xml_files = [n for n in zf.namelist() if n.endswith(".xml") and n != "imsmanifest.xml"]
            assessment = zf.read(xml_files[0]).decode()
            assert "response_str" in assessment
            assert "render_fib" in assessment
            assert "response_lid" not in assessment
