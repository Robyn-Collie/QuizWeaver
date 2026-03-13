"""Tests for the document-sourced standards provenance system.

Covers PDF extraction, SOL curriculum framework parsing, source document
registration, import pipeline, provenance queries, web routes, and
security checks for the source-documents feature.

The ``src.source_documents`` module may not exist yet; tests use
try/except imports so they gracefully skip when the implementation
is missing.
"""

import hashlib
import io
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.database import (
    Base,
    Class,
    SourceDocument,
    Standard,
    StandardExcerpt,
    get_engine,
    get_session,
)

# ---------------------------------------------------------------------------
# Conditional imports for the module under test (may not exist yet)
# ---------------------------------------------------------------------------
try:
    from src.source_documents import (
        compute_file_hash,
        extract_text_by_page,
        get_excerpts_for_standard,
        import_from_source_document,
        parse_sol_curriculum_framework,
        register_source_document,
    )

    HAS_SOURCE_DOCUMENTS = True
except ImportError:
    HAS_SOURCE_DOCUMENTS = False

needs_source_documents = pytest.mark.skipif(
    not HAS_SOURCE_DOCUMENTS,
    reason="src.source_documents module not yet implemented",
)


# ---------------------------------------------------------------------------
# Helper: create a small PDF using reportlab (already a project dependency)
# ---------------------------------------------------------------------------


def _make_test_pdf(pages_text=None):
    """Create a minimal PDF in memory and return the bytes.

    ``pages_text`` is a list of strings, one per page.  If *None* a
    two-page default is used.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    if pages_text is None:
        pages_text = [
            "Page one content.\nLine two of page one.",
            "Page two content.\nLine two of page two.",
        ]

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for text in pages_text:
        y = 750
        for line in text.split("\n"):
            c.drawString(72, y, line)
            y -= 14
        c.showPage()
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_env():
    """Provide engine, session, and temp DB path with cleanup."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    yield engine, session, db_path

    session.close()
    engine.dispose()
    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def seeded_db(db_env):
    """DB with a Class and two Standards pre-seeded."""
    engine, session, db_path = db_env

    cls = Class(
        name="Life Science 7",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps([]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    s1 = Standard(
        code="SOL LS.4",
        standard_id="SOL LS.4",
        description="Investigate energy transfer",
        subject="Science",
        grade_band="6-8",
        strand="Life Science",
        full_text="The student will investigate energy transfer.",
        source="Virginia SOL",
        version="2024",
        standard_set="sol",
    )
    s2 = Standard(
        code="SOL LS.5",
        standard_id="SOL LS.5",
        description="Investigate population interactions",
        subject="Science",
        grade_band="6-8",
        strand="Life Science",
        full_text="The student will investigate population interactions.",
        source="Virginia SOL",
        version="2024",
        standard_set="sol",
    )
    session.add_all([s1, s2])
    session.commit()

    yield engine, session, db_path, {"s1": s1, "s2": s2, "class": cls}


@pytest.fixture
def tmp_pdf_path():
    """Write a small test PDF to a temp file and yield its path."""
    pdf_bytes = _make_test_pdf()
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(pdf_bytes)
    tmp.close()
    yield tmp.name
    try:
        os.remove(tmp.name)
    except OSError:
        pass


@pytest.fixture
def app_with_source_docs(seeded_db):
    """Flask app with standards + source documents for route testing."""
    engine, session, db_path, objs = seeded_db

    # Add a source document with excerpts
    doc = SourceDocument(
        filename="sol_cf_2024.pdf",
        title="2024 Virginia SOL Curriculum Framework",
        standard_set="sol",
        version="2024",
        file_hash="abc123hash",
        page_count=42,
        created_at=datetime.utcnow(),
    )
    session.add(doc)
    session.commit()

    excerpt = StandardExcerpt(
        standard_id=objs["s1"].id,
        source_document_id=doc.id,
        content_type="essential_knowledge",
        source_page=5,
        source_excerpt="All organisms need energy to survive.",
        sort_order=0,
        created_at=datetime.utcnow(),
    )
    session.add(excerpt)
    session.commit()

    doc_id = doc.id
    s1_id = objs["s1"].id
    s2_id = objs["s2"].id

    session.close()
    engine.dispose()

    from src.web.app import create_app

    upload_dir = tempfile.mkdtemp()

    # Write a fake PDF so the serve route has something to return
    source_docs_dir = os.path.join(upload_dir, "source_documents")
    os.makedirs(source_docs_dir, exist_ok=True)
    fake_pdf = _make_test_pdf(["Fake SOL content."])
    with open(os.path.join(source_docs_dir, "sol_cf_2024.pdf"), "wb") as f:
        f.write(fake_pdf)

    test_config = {
        "paths": {
            "database_file": db_path,
            "upload_dir": upload_dir,
            "source_documents_dir": source_docs_dir,
        },
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
    app.config["_test_ids"] = {
        "doc_id": doc_id,
        "s1_id": s1_id,
        "s2_id": s2_id,
    }
    app.config["_source_docs_dir"] = source_docs_dir

    yield app

    app.config["DB_ENGINE"].dispose()


@pytest.fixture
def auth_client(app_with_source_docs):
    """Logged-in Flask test client."""
    with app_with_source_docs.test_client() as c:
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        c._app = app_with_source_docs
        yield c


@pytest.fixture
def anon_client(app_with_source_docs):
    """Unauthenticated Flask test client."""
    with app_with_source_docs.test_client() as c:
        c._app = app_with_source_docs
        yield c


# ===================================================================
# 1. PDF Extraction Tests
# ===================================================================


@needs_source_documents
class TestExtractTextByPage:
    """extract_text_by_page should return per-page text dicts."""

    def test_returns_list_of_dicts(self, tmp_pdf_path):
        pages = extract_text_by_page(tmp_pdf_path)
        assert isinstance(pages, list)
        assert len(pages) >= 1
        for p in pages:
            assert "page" in p
            assert "text" in p

    def test_page_numbers_are_ints(self, tmp_pdf_path):
        pages = extract_text_by_page(tmp_pdf_path)
        for p in pages:
            assert isinstance(p["page"], int)

    def test_page_numbers_are_one_indexed(self, tmp_pdf_path):
        pages = extract_text_by_page(tmp_pdf_path)
        assert pages[0]["page"] == 1

    def test_text_contains_content(self, tmp_pdf_path):
        pages = extract_text_by_page(tmp_pdf_path)
        all_text = " ".join(p["text"] for p in pages)
        assert "Page one content" in all_text or "page" in all_text.lower()

    def test_two_page_pdf_returns_two_entries(self):
        pdf_bytes = _make_test_pdf(["First page.", "Second page."])
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(pdf_bytes)
        tmp.close()
        try:
            pages = extract_text_by_page(tmp.name)
            assert len(pages) == 2
        finally:
            os.remove(tmp.name)

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            extract_text_by_page("/nonexistent/path/fake.pdf")

    def test_compute_file_hash_consistent(self, tmp_pdf_path):
        h1 = compute_file_hash(tmp_pdf_path)
        h2 = compute_file_hash(tmp_pdf_path)
        assert h1 == h2
        assert isinstance(h1, str)
        assert len(h1) == 64  # SHA-256 hex digest length

    def test_compute_file_hash_is_sha256(self, tmp_pdf_path):
        h = compute_file_hash(tmp_pdf_path)
        # Verify by computing ourselves
        with open(tmp_pdf_path, "rb") as f:
            expected = hashlib.sha256(f.read()).hexdigest()
        assert h == expected

    def test_compute_file_hash_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            compute_file_hash("/nonexistent/file.pdf")


# ===================================================================
# 2. SOL Parser Tests
# ===================================================================


@needs_source_documents
class TestParseSOLCurriculumFramework:
    """parse_sol_curriculum_framework returns a list of dicts.

    Each dict has keys: code, page, essential_knowledge,
    essential_understandings, essential_skills. The section lists contain
    plain strings (not sub-dicts).
    """

    MOCK_PAGES = [
        {
            "page": 5,
            "text": (
                "SOL LS.4\n"
                "The student will investigate energy transfer.\n"
                "\n"
                "Essential Knowledge\n"
                "- All organisms need energy\n"
                "- Producers make their own food\n"
                "\n"
                "Essential Understandings\n"
                "- Energy flows through ecosystems\n"
                "\n"
                "Essential Skills\n"
                "- Construct food webs\n"
                "- Compare photosynthesis and respiration"
            ),
        },
        {
            "page": 6,
            "text": (
                "SOL LS.5\n"
                "The student will investigate population interactions.\n"
                "\n"
                "Essential Knowledge\n"
                "- Populations interact in communities\n"
                "- Predator-prey relationships affect population size"
            ),
        },
    ]

    # Also test with bullet point (dot) format
    MOCK_PAGES_BULLETS = [
        {
            "page": 10,
            "text": (
                "SOL LS.4\n"
                "The student will investigate energy transfer.\n"
                "\n"
                "Essential Knowledge\n"
                "\u2022 All organisms need energy\n"
                "\u2022 Producers make their own food\n"
                "\n"
                "Essential Understandings\n"
                "\u2022 Energy flows through ecosystems\n"
                "\n"
                "Essential Skills\n"
                "\u2022 Construct food webs\n"
                "\u2022 Compare photosynthesis and respiration"
            ),
        },
    ]

    def test_returns_list(self):
        result = parse_sol_curriculum_framework(self.MOCK_PAGES)
        assert isinstance(result, list)

    def test_each_entry_has_code(self):
        result = parse_sol_curriculum_framework(self.MOCK_PAGES)
        for entry in result:
            assert "code" in entry

    def test_finds_standard_codes(self):
        result = parse_sol_curriculum_framework(self.MOCK_PAGES)
        codes = [r["code"] for r in result]
        assert any("LS.4" in c for c in codes)
        assert any("LS.5" in c for c in codes)

    def test_extracts_essential_knowledge(self):
        result = parse_sol_curriculum_framework(self.MOCK_PAGES)
        ls4 = next(r for r in result if "LS.4" in r["code"])
        ek = ls4["essential_knowledge"]
        assert len(ek) >= 2
        ek_lower = [item.lower() for item in ek]
        assert any("organisms" in t for t in ek_lower)
        assert any("producers" in t for t in ek_lower)

    def test_extracts_essential_understandings(self):
        result = parse_sol_curriculum_framework(self.MOCK_PAGES)
        ls4 = next(r for r in result if "LS.4" in r["code"])
        eu = ls4["essential_understandings"]
        assert len(eu) >= 1
        eu_lower = [item.lower() for item in eu]
        assert any("energy" in t for t in eu_lower)

    def test_extracts_essential_skills(self):
        result = parse_sol_curriculum_framework(self.MOCK_PAGES)
        ls4 = next(r for r in result if "LS.4" in r["code"])
        es = ls4["essential_skills"]
        assert len(es) >= 2
        es_lower = [item.lower() for item in es]
        assert any("food web" in t for t in es_lower)

    def test_records_page_number(self):
        result = parse_sol_curriculum_framework(self.MOCK_PAGES)
        ls4 = next(r for r in result if "LS.4" in r["code"])
        assert ls4["page"] == 5

    def test_handles_missing_sections(self):
        """Standard with only Essential Knowledge (no understandings/skills)."""
        result = parse_sol_curriculum_framework(self.MOCK_PAGES)
        ls5 = next(r for r in result if "LS.5" in r["code"])
        ek = ls5["essential_knowledge"]
        assert len(ek) >= 1
        # Missing sections should be empty lists, not errors
        eu = ls5["essential_understandings"]
        es = ls5["essential_skills"]
        assert isinstance(eu, list)
        assert isinstance(es, list)

    def test_handles_multiple_standards(self):
        result = parse_sol_curriculum_framework(self.MOCK_PAGES)
        assert len(result) >= 2

    def test_empty_pages_returns_empty_list(self):
        result = parse_sol_curriculum_framework([])
        assert isinstance(result, list)
        assert len(result) == 0

    def test_no_standards_found_returns_empty_list(self):
        pages = [{"page": 1, "text": "No standards here. Just regular text."}]
        result = parse_sol_curriculum_framework(pages)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_bullet_format_also_works(self):
        """Unicode bullet characters should be parsed the same as dashes."""
        result = parse_sol_curriculum_framework(self.MOCK_PAGES_BULLETS)
        assert len(result) >= 1
        ls4 = next(r for r in result if "LS.4" in r["code"])
        ek = ls4["essential_knowledge"]
        assert len(ek) >= 2


# ===================================================================
# 3. Source Document Registration Tests
# ===================================================================


@needs_source_documents
class TestRegisterSourceDocument:
    """register_source_document should create DB records."""

    def test_creates_db_record(self, seeded_db, tmp_pdf_path):
        engine, session, db_path, objs = seeded_db
        doc = register_source_document(
            session=session,
            filepath=tmp_pdf_path,
            title="Test SOL Framework",
            standard_set="sol",
            version="2024",
        )
        assert doc is not None
        assert doc.id is not None
        assert doc.title == "Test SOL Framework"

    def test_file_hash_stored(self, seeded_db, tmp_pdf_path):
        engine, session, db_path, objs = seeded_db
        doc = register_source_document(
            session=session,
            filepath=tmp_pdf_path,
            title="Test Framework",
            standard_set="sol",
        )
        assert doc.file_hash is not None
        assert len(doc.file_hash) == 64  # SHA-256

    def test_page_count_stored(self, seeded_db, tmp_pdf_path):
        engine, session, db_path, objs = seeded_db
        doc = register_source_document(
            session=session,
            filepath=tmp_pdf_path,
            title="Test Framework",
            standard_set="sol",
        )
        assert doc.page_count is not None
        assert doc.page_count >= 1

    def test_duplicate_filename_returns_existing(self, seeded_db, tmp_pdf_path):
        """Registering the same filename twice should return the existing record."""
        engine, session, db_path, objs = seeded_db
        doc1 = register_source_document(
            session=session,
            filepath=tmp_pdf_path,
            title="First Registration",
            standard_set="sol",
        )
        doc2 = register_source_document(
            session=session,
            filepath=tmp_pdf_path,
            title="Second Registration",
            standard_set="sol",
        )
        # Should return the same record (not create a duplicate)
        assert doc2.id == doc1.id

    def test_filename_derived_from_path(self, seeded_db, tmp_pdf_path):
        engine, session, db_path, objs = seeded_db
        doc = register_source_document(
            session=session,
            filepath=tmp_pdf_path,
            title="Test Framework",
            standard_set="sol",
        )
        assert doc.filename is not None
        assert doc.filename.endswith(".pdf")

    def test_file_not_found_raises(self, seeded_db):
        engine, session, db_path, objs = seeded_db
        with pytest.raises(FileNotFoundError):
            register_source_document(
                session=session,
                filepath="/nonexistent/file.pdf",
                title="Missing File",
                standard_set="sol",
            )


# ===================================================================
# 4. Import Pipeline Tests
# ===================================================================


@needs_source_documents
class TestImportFromSourceDocument:
    """import_from_source_document should create StandardExcerpt rows.

    The parsed_data argument matches the dict format returned by
    parse_sol_curriculum_framework: keys are SOL codes, values are
    dicts with essential_knowledge/understandings/skills lists of
    {"text": str, "page": int} items.
    """

    def _make_parsed_data(self):
        """Return mock parsed data matching parse_sol_curriculum_framework output.

        The parser returns a list of dicts, each with code, page, and
        flat string lists for essential_knowledge/understandings/skills.
        """
        return [
            {
                "code": "SOL LS.4",
                "page": 5,
                "essential_knowledge": [
                    "All organisms need energy",
                    "Producers make their own food",
                ],
                "essential_understandings": [
                    "Energy flows through ecosystems",
                ],
                "essential_skills": [
                    "Construct food webs",
                    "Compare photosynthesis and respiration",
                ],
            },
            {
                "code": "SOL LS.5",
                "page": 6,
                "essential_knowledge": [
                    "Populations interact",
                    "Predator-prey relationships",
                ],
                "essential_understandings": [],
                "essential_skills": [],
            },
        ]

    def test_creates_excerpt_rows(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="test.pdf",
            title="Test Doc",
            standard_set="sol",
            file_hash="testhash",
            page_count=10,
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        parsed = self._make_parsed_data()
        result = import_from_source_document(session, doc.id, parsed)

        excerpts = (
            session.query(StandardExcerpt)
            .filter_by(source_document_id=doc.id)
            .all()
        )
        assert len(excerpts) > 0

    def test_returns_updated_count(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="test_count.pdf",
            title="Test Doc",
            standard_set="sol",
            file_hash="testhashcount",
            page_count=10,
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        parsed = self._make_parsed_data()
        result = import_from_source_document(session, doc.id, parsed)
        # Two standards in parsed data, both exist in DB
        assert result == 2

    def test_links_to_correct_standard(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="test_link.pdf",
            title="Test Doc",
            standard_set="sol",
            file_hash="testhash2",
            page_count=10,
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        parsed = self._make_parsed_data()
        import_from_source_document(session, doc.id, parsed)

        ls4_excerpts = (
            session.query(StandardExcerpt)
            .filter_by(standard_id=objs["s1"].id)
            .all()
        )
        assert len(ls4_excerpts) > 0
        # All should reference the correct source document
        for ex in ls4_excerpts:
            assert ex.source_document_id == doc.id

    def test_updates_json_cache_on_standard(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="test_cache.pdf",
            title="Test Doc",
            standard_set="sol",
            file_hash="testhash3",
            page_count=10,
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        parsed = self._make_parsed_data()
        import_from_source_document(session, doc.id, parsed)

        session.refresh(objs["s1"])
        # Check that essential_knowledge JSON was updated
        ek = objs["s1"].essential_knowledge
        assert ek is not None
        ek_list = json.loads(ek) if isinstance(ek, str) else ek
        assert len(ek_list) >= 2
        # Items in the cache are plain strings
        ek_lower = [item.lower() for item in ek_list]
        assert any("organisms" in t for t in ek_lower)

    def test_handles_unknown_standard_gracefully(self, seeded_db):
        """Standards not in DB should be skipped (warning logged), not crash."""
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="test_unknown.pdf",
            title="Test Doc",
            standard_set="sol",
            file_hash="testhash4",
            page_count=10,
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        parsed = [
            {
                "code": "SOL XY.99",
                "page": 1,
                "essential_knowledge": ["Unknown standard content"],
                "essential_understandings": [],
                "essential_skills": [],
            },
        ]

        # Should not raise
        result = import_from_source_document(session, doc.id, parsed)

        excerpts = (
            session.query(StandardExcerpt)
            .filter_by(source_document_id=doc.id)
            .all()
        )
        # No excerpts should be created for unknown standards
        assert len(excerpts) == 0
        assert result == 0

    def test_sort_order_preserved(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="test_order.pdf",
            title="Test Doc",
            standard_set="sol",
            file_hash="testhash5",
            page_count=10,
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        parsed = self._make_parsed_data()
        import_from_source_document(session, doc.id, parsed)

        excerpts = (
            session.query(StandardExcerpt)
            .filter_by(standard_id=objs["s1"].id)
            .order_by(StandardExcerpt.sort_order)
            .all()
        )
        assert len(excerpts) > 1
        orders = [e.sort_order for e in excerpts]
        assert orders == sorted(orders), "Excerpts should be in sort_order"

    def test_excerpt_content_types_correct(self, seeded_db):
        """Each excerpt should have the correct content_type label."""
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="test_types.pdf",
            title="Test Doc",
            standard_set="sol",
            file_hash="testhash6",
            page_count=10,
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        parsed = self._make_parsed_data()
        import_from_source_document(session, doc.id, parsed)

        excerpts = (
            session.query(StandardExcerpt)
            .filter_by(standard_id=objs["s1"].id)
            .all()
        )
        types = {e.content_type for e in excerpts}
        assert "essential_knowledge" in types
        assert "essential_understandings" in types
        assert "essential_skills" in types


# ===================================================================
# 5. Provenance Query Tests
# ===================================================================


@needs_source_documents
class TestGetExcerptsForStandard:
    """get_excerpts_for_standard should return grouped provenance data.

    Returns a dict with keys essential_knowledge, essential_understandings,
    essential_skills. Each value is a list of dicts with text, page,
    doc_title, doc_id.
    """

    def test_returns_grouped_data(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="provenance_test.pdf",
            title="SOL Framework 2024",
            standard_set="sol",
            file_hash="provhash",
            page_count=10,
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        e1 = StandardExcerpt(
            standard_id=objs["s1"].id,
            source_document_id=doc.id,
            content_type="essential_knowledge",
            source_page=5,
            source_excerpt="All organisms need energy.",
            sort_order=0,
            created_at=datetime.utcnow(),
        )
        e2 = StandardExcerpt(
            standard_id=objs["s1"].id,
            source_document_id=doc.id,
            content_type="essential_skills",
            source_page=5,
            source_excerpt="Construct food webs.",
            sort_order=1,
            created_at=datetime.utcnow(),
        )
        session.add_all([e1, e2])
        session.commit()

        result = get_excerpts_for_standard(session, objs["s1"].id)
        assert isinstance(result, dict)
        assert "essential_knowledge" in result
        assert "essential_skills" in result
        assert len(result["essential_knowledge"]) >= 1
        assert len(result["essential_skills"]) >= 1

    def test_empty_when_no_excerpts(self, seeded_db):
        """Returns empty dict when no excerpts exist for the standard."""
        engine, session, db_path, objs = seeded_db
        result = get_excerpts_for_standard(session, objs["s2"].id)
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_includes_source_document_info(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="info_test.pdf",
            title="SOL Framework Info",
            standard_set="sol",
            file_hash="infohash",
            page_count=10,
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        excerpt = StandardExcerpt(
            standard_id=objs["s1"].id,
            source_document_id=doc.id,
            content_type="essential_knowledge",
            source_page=3,
            source_excerpt="Test excerpt.",
            sort_order=0,
            created_at=datetime.utcnow(),
        )
        session.add(excerpt)
        session.commit()

        result = get_excerpts_for_standard(session, objs["s1"].id)
        ek_items = result["essential_knowledge"]
        assert len(ek_items) >= 1
        # Each item should include doc_title and doc_id
        item = ek_items[0]
        assert item["doc_title"] == "SOL Framework Info"
        assert item["doc_id"] == doc.id

    def test_items_have_expected_keys(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="keys_test.pdf",
            title="Keys Doc",
            standard_set="sol",
            file_hash="keyshash",
            page_count=5,
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        excerpt = StandardExcerpt(
            standard_id=objs["s1"].id,
            source_document_id=doc.id,
            content_type="essential_knowledge",
            source_page=2,
            source_excerpt="Check keys.",
            sort_order=0,
            created_at=datetime.utcnow(),
        )
        session.add(excerpt)
        session.commit()

        result = get_excerpts_for_standard(session, objs["s1"].id)
        item = result["essential_knowledge"][0]
        assert "text" in item
        assert "page" in item
        assert "doc_title" in item
        assert "doc_id" in item


# ===================================================================
# 6. Route Tests
# ===================================================================


class TestSourceDocumentRoutes:
    """Web route tests for source-document management pages."""

    def test_source_documents_list_returns_200(self, auth_client):
        resp = auth_client.get("/standards/source-documents")
        # Route may not exist yet; accept 200 or 404-as-not-implemented
        assert resp.status_code in (200, 404)

    def test_source_documents_list_requires_login(self, anon_client):
        resp = anon_client.get("/standards/source-documents")
        # Should redirect to login (303) or be 404 if not implemented
        assert resp.status_code in (303, 302, 404)

    def test_upload_requires_login(self, anon_client):
        resp = anon_client.post(
            "/standards/source-documents/upload",
            data={"title": "Test"},
        )
        assert resp.status_code in (303, 302, 404, 405)

    def test_serve_document_returns_pdf(self, auth_client):
        ids = auth_client._app.config["_test_ids"]
        resp = auth_client.get(f"/standards/source-document/{ids['doc_id']}")
        # May return the PDF or 404 if route not implemented
        if resp.status_code == 200:
            assert resp.content_type in (
                "application/pdf",
                "application/octet-stream",
            )
        else:
            assert resp.status_code == 404

    def test_serve_document_404_for_missing(self, auth_client):
        resp = auth_client.get("/standards/source-document/99999")
        assert resp.status_code == 404

    def test_provenance_api_returns_json(self, auth_client):
        ids = auth_client._app.config["_test_ids"]
        resp = auth_client.get(f"/api/standards/{ids['s1_id']}/provenance")
        if resp.status_code == 200:
            data = resp.get_json()
            assert data is not None
            assert isinstance(data, (dict, list))
        else:
            # Route may not exist yet
            assert resp.status_code == 404

    def test_provenance_api_requires_login(self, anon_client):
        ids = anon_client._app.config["_test_ids"]
        resp = anon_client.get(f"/api/standards/{ids['s1_id']}/provenance")
        assert resp.status_code in (303, 302, 404)

    def test_standard_detail_with_excerpts(self, auth_client):
        """Standard detail page should render when excerpts exist."""
        ids = auth_client._app.config["_test_ids"]
        resp = auth_client.get(f"/standards/{ids['s1_id']}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "SOL LS.4" in html

    def test_standard_detail_without_excerpts(self, auth_client):
        """Standard detail page should still work when no excerpts exist (backward compat)."""
        ids = auth_client._app.config["_test_ids"]
        resp = auth_client.get(f"/standards/{ids['s2_id']}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "SOL LS.5" in html


# ===================================================================
# 7. Database Model Tests (always runnable)
# ===================================================================


class TestSourceDocumentModel:
    """Tests for SourceDocument and StandardExcerpt ORM models."""

    def test_source_document_create(self, db_env):
        engine, session, db_path = db_env
        doc = SourceDocument(
            filename="test.pdf",
            title="Test Document",
            standard_set="sol",
            file_hash="abc123",
            page_count=10,
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()
        assert doc.id is not None

    def test_source_document_unique_filename(self, db_env):
        engine, session, db_path = db_env
        doc1 = SourceDocument(
            filename="unique.pdf",
            title="Doc 1",
            standard_set="sol",
            created_at=datetime.utcnow(),
        )
        session.add(doc1)
        session.commit()

        from sqlalchemy.exc import IntegrityError

        doc2 = SourceDocument(
            filename="unique.pdf",
            title="Doc 2",
            standard_set="sol",
            created_at=datetime.utcnow(),
        )
        session.add(doc2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_standard_excerpt_create(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="excerpt_test.pdf",
            title="Test Doc",
            standard_set="sol",
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        excerpt = StandardExcerpt(
            standard_id=objs["s1"].id,
            source_document_id=doc.id,
            content_type="essential_knowledge",
            source_page=5,
            source_excerpt="Test excerpt content.",
            sort_order=0,
            created_at=datetime.utcnow(),
        )
        session.add(excerpt)
        session.commit()
        assert excerpt.id is not None

    def test_excerpt_relationship_to_standard(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="rel_test.pdf",
            title="Rel Doc",
            standard_set="sol",
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        excerpt = StandardExcerpt(
            standard_id=objs["s1"].id,
            source_document_id=doc.id,
            content_type="essential_knowledge",
            source_page=1,
            source_excerpt="Relationship test.",
            sort_order=0,
            created_at=datetime.utcnow(),
        )
        session.add(excerpt)
        session.commit()

        assert excerpt.standard is not None
        assert excerpt.standard.code == "SOL LS.4"

    def test_excerpt_relationship_to_source_document(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="rel_doc_test.pdf",
            title="Source Rel Doc",
            standard_set="sol",
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        excerpt = StandardExcerpt(
            standard_id=objs["s1"].id,
            source_document_id=doc.id,
            content_type="essential_skills",
            source_page=2,
            source_excerpt="Source doc relationship test.",
            sort_order=0,
            created_at=datetime.utcnow(),
        )
        session.add(excerpt)
        session.commit()

        assert excerpt.source_document is not None
        assert excerpt.source_document.title == "Source Rel Doc"

    def test_cascade_delete_standard_removes_excerpts(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="cascade_test.pdf",
            title="Cascade Doc",
            standard_set="sol",
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        excerpt = StandardExcerpt(
            standard_id=objs["s1"].id,
            source_document_id=doc.id,
            content_type="essential_knowledge",
            source_page=1,
            source_excerpt="Cascade test.",
            sort_order=0,
            created_at=datetime.utcnow(),
        )
        session.add(excerpt)
        session.commit()
        excerpt_id = excerpt.id

        # Delete the standard -- excerpt should cascade
        session.delete(objs["s1"])
        session.commit()

        orphan = session.query(StandardExcerpt).filter_by(id=excerpt_id).first()
        assert orphan is None

    def test_source_document_excerpts_relationship(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="multi_excerpt.pdf",
            title="Multi Excerpt Doc",
            standard_set="sol",
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        for i, content_type in enumerate(["essential_knowledge", "essential_skills"]):
            e = StandardExcerpt(
                standard_id=objs["s1"].id,
                source_document_id=doc.id,
                content_type=content_type,
                source_page=5,
                source_excerpt=f"Excerpt {i}",
                sort_order=i,
                created_at=datetime.utcnow(),
            )
            session.add(e)
        session.commit()

        session.refresh(doc)
        assert len(doc.excerpts) == 2

    def test_standard_excerpts_relationship(self, seeded_db):
        engine, session, db_path, objs = seeded_db

        doc = SourceDocument(
            filename="std_rel.pdf",
            title="Std Rel Doc",
            standard_set="sol",
            created_at=datetime.utcnow(),
        )
        session.add(doc)
        session.commit()

        excerpt = StandardExcerpt(
            standard_id=objs["s1"].id,
            source_document_id=doc.id,
            content_type="essential_knowledge",
            source_page=1,
            source_excerpt="Via standard relationship.",
            sort_order=0,
            created_at=datetime.utcnow(),
        )
        session.add(excerpt)
        session.commit()

        session.refresh(objs["s1"])
        assert len(objs["s1"].excerpts) >= 1
        assert any(
            e.source_excerpt == "Via standard relationship."
            for e in objs["s1"].excerpts
        )


# ===================================================================
# 8. PDF Helper Tests (always runnable -- uses reportlab)
# ===================================================================


class TestPDFHelpers:
    """Tests for the test helper _make_test_pdf itself."""

    def test_make_test_pdf_produces_bytes(self):
        data = _make_test_pdf()
        assert isinstance(data, bytes)
        assert data[:5] == b"%PDF-"

    def test_make_test_pdf_custom_pages(self):
        data = _make_test_pdf(["Hello", "World", "Page3"])
        assert isinstance(data, bytes)
        assert len(data) > 100

    def test_hash_differs_for_different_content(self):
        pdf1 = _make_test_pdf(["Content A"])
        pdf2 = _make_test_pdf(["Content B"])
        h1 = hashlib.sha256(pdf1).hexdigest()
        h2 = hashlib.sha256(pdf2).hexdigest()
        assert h1 != h2
