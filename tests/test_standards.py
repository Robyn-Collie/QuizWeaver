"""Tests for the standards database module."""

import json
import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base, Standard
from src.standards import (
    create_standard,
    get_standard,
    get_standard_by_code,
    list_standards,
    search_standards,
    delete_standard,
    bulk_import_standards,
    load_standards_from_json,
    get_subjects,
    get_grade_bands,
    get_strands,
    standards_count,
)


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def sample_standards(db_session):
    """Pre-populate some standards for tests."""
    standards = [
        create_standard(
            db_session,
            code="SOL 7.1",
            description="Negative exponents for powers of ten",
            subject="Mathematics",
            grade_band="6-8",
            strand="Number and Number Sense",
            full_text="The student will investigate and describe the concept of negative exponents for powers of ten.",
            source="Virginia SOL",
            version="2023",
        ),
        create_standard(
            db_session,
            code="SOL 7.2",
            description="Solve problems with rational numbers",
            subject="Mathematics",
            grade_band="6-8",
            strand="Computation and Estimation",
            full_text="The student will solve practical problems involving operations with rational numbers.",
            source="Virginia SOL",
            version="2023",
        ),
        create_standard(
            db_session,
            code="SOL 7.1E",
            description="Plan and conduct investigations",
            subject="Science",
            grade_band="6-8",
            strand="Scientific Investigation",
            full_text="The student will demonstrate an understanding of scientific reasoning by planning and conducting investigations.",
            source="Virginia SOL",
            version="2023",
        ),
        create_standard(
            db_session,
            code="SOL 8.5R",
            description="Read and analyze fictional texts",
            subject="English",
            grade_band="6-8",
            strand="Reading",
            full_text="The student will read and analyze a variety of fictional texts.",
            source="Virginia SOL",
            version="2023",
        ),
        create_standard(
            db_session,
            code="SOL A.1",
            description="Represent verbal quantitative situations algebraically",
            subject="Mathematics",
            grade_band="9-12",
            strand="Expressions and Operations",
            full_text="The student will represent verbal quantitative situations algebraically.",
            source="Virginia SOL",
            version="2023",
        ),
    ]
    return standards


class TestCreateStandard:
    def test_create_standard_basic(self, db_session):
        std = create_standard(
            db_session,
            code="SOL 8.3",
            description="Estimate square roots",
            subject="Mathematics",
        )
        assert std.id is not None
        assert std.code == "SOL 8.3"
        assert std.description == "Estimate square roots"
        assert std.subject == "Mathematics"
        assert std.source == "Virginia SOL"  # default

    def test_create_standard_all_fields(self, db_session):
        std = create_standard(
            db_session,
            code="SOL BIO.3",
            description="Cell structure and function",
            subject="Science",
            grade_band="9-12",
            strand="Life at the Cellular Level",
            full_text="The student will investigate cell structure.",
            source="Virginia SOL",
            version="2023",
        )
        assert std.grade_band == "9-12"
        assert std.strand == "Life at the Cellular Level"
        assert std.full_text == "The student will investigate cell structure."
        assert std.version == "2023"

    def test_create_standard_unique_code(self, db_session):
        create_standard(db_session, code="SOL 1.1", description="Test", subject="Math")
        with pytest.raises(Exception):
            create_standard(db_session, code="SOL 1.1", description="Duplicate", subject="Math")


class TestGetStandard:
    def test_get_standard_by_id(self, db_session, sample_standards):
        std = get_standard(db_session, sample_standards[0].id)
        assert std is not None
        assert std.code == "SOL 7.1"

    def test_get_standard_not_found(self, db_session):
        assert get_standard(db_session, 9999) is None

    def test_get_standard_by_code(self, db_session, sample_standards):
        std = get_standard_by_code(db_session, "SOL 7.2")
        assert std is not None
        assert std.description == "Solve problems with rational numbers"

    def test_get_standard_by_code_not_found(self, db_session):
        assert get_standard_by_code(db_session, "SOL 99.99") is None


class TestListStandards:
    def test_list_all(self, db_session, sample_standards):
        results = list_standards(db_session)
        assert len(results) == 5

    def test_list_by_subject(self, db_session, sample_standards):
        results = list_standards(db_session, subject="Mathematics")
        assert len(results) == 3
        for std in results:
            assert std.subject == "Mathematics"

    def test_list_by_grade_band(self, db_session, sample_standards):
        results = list_standards(db_session, grade_band="6-8")
        assert len(results) == 4

    def test_list_by_subject_and_grade(self, db_session, sample_standards):
        results = list_standards(db_session, subject="Mathematics", grade_band="6-8")
        assert len(results) == 2

    def test_list_by_source(self, db_session, sample_standards):
        results = list_standards(db_session, source="Virginia SOL")
        assert len(results) == 5

    def test_list_empty(self, db_session):
        results = list_standards(db_session)
        assert results == []

    def test_list_ordered_by_code(self, db_session, sample_standards):
        results = list_standards(db_session)
        codes = [s.code for s in results]
        assert codes == sorted(codes)


class TestSearchStandards:
    def test_search_by_code(self, db_session, sample_standards):
        results = search_standards(db_session, "SOL 7")
        assert len(results) >= 2

    def test_search_by_description(self, db_session, sample_standards):
        results = search_standards(db_session, "rational numbers")
        assert len(results) == 1
        assert results[0].code == "SOL 7.2"

    def test_search_by_full_text(self, db_session, sample_standards):
        results = search_standards(db_session, "scientific reasoning")
        assert len(results) == 1
        assert results[0].code == "SOL 7.1E"

    def test_search_case_insensitive(self, db_session, sample_standards):
        results = search_standards(db_session, "RATIONAL NUMBERS")
        assert len(results) == 1

    def test_search_with_subject_filter(self, db_session, sample_standards):
        results = search_standards(db_session, "SOL", subject="Science")
        assert all(s.subject == "Science" for s in results)

    def test_search_with_grade_filter(self, db_session, sample_standards):
        results = search_standards(db_session, "SOL", grade_band="9-12")
        assert all(s.grade_band == "9-12" for s in results)

    def test_search_no_results(self, db_session, sample_standards):
        results = search_standards(db_session, "quantum physics")
        assert results == []

    def test_search_by_strand(self, db_session, sample_standards):
        results = search_standards(db_session, "Number and Number Sense")
        assert len(results) == 1
        assert results[0].code == "SOL 7.1"


class TestDeleteStandard:
    def test_delete_existing(self, db_session, sample_standards):
        std_id = sample_standards[0].id
        assert delete_standard(db_session, std_id) is True
        assert get_standard(db_session, std_id) is None

    def test_delete_nonexistent(self, db_session):
        assert delete_standard(db_session, 9999) is False


class TestBulkImport:
    def test_bulk_import(self, db_session):
        data = [
            {"code": "SOL T.1", "description": "Test 1", "subject": "Math"},
            {"code": "SOL T.2", "description": "Test 2", "subject": "Math"},
        ]
        imported = bulk_import_standards(db_session, data)
        assert imported == 2
        assert standards_count(db_session) == 2

    def test_bulk_import_skips_duplicates(self, db_session):
        data = [
            {"code": "SOL T.1", "description": "Test 1", "subject": "Math"},
        ]
        bulk_import_standards(db_session, data)
        imported = bulk_import_standards(db_session, data)
        assert imported == 0
        assert standards_count(db_session) == 1

    def test_bulk_import_empty_list(self, db_session):
        assert bulk_import_standards(db_session, []) == 0


class TestLoadFromJSON:
    def test_load_from_json(self, db_session):
        data = {
            "source": "Virginia SOL",
            "version": "2023",
            "standards": [
                {"code": "SOL J.1", "description": "JSON Test", "subject": "Math"},
                {"code": "SOL J.2", "description": "JSON Test 2", "subject": "Science"},
            ],
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(data, f)
            json_path = f.name

        try:
            imported = load_standards_from_json(db_session, json_path)
            assert imported == 2
            std = get_standard_by_code(db_session, "SOL J.1")
            assert std.source == "Virginia SOL"
            assert std.version == "2023"
        finally:
            os.unlink(json_path)

    def test_load_from_json_file_not_found(self, db_session):
        with pytest.raises(FileNotFoundError):
            load_standards_from_json(db_session, "/nonexistent/file.json")

    def test_load_real_sol_data(self, db_session):
        """Test loading the actual sol_standards.json data file."""
        json_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "sol_standards.json",
        )
        if not os.path.exists(json_path):
            pytest.skip("sol_standards.json not found")

        imported = load_standards_from_json(db_session, json_path)
        assert imported > 0
        assert standards_count(db_session) > 50


class TestHelperQueries:
    def test_get_subjects(self, db_session, sample_standards):
        subjects = get_subjects(db_session)
        assert "Mathematics" in subjects
        assert "Science" in subjects
        assert "English" in subjects
        assert subjects == sorted(subjects)

    def test_get_grade_bands(self, db_session, sample_standards):
        bands = get_grade_bands(db_session)
        assert "6-8" in bands
        assert "9-12" in bands

    def test_get_strands(self, db_session, sample_standards):
        strands = get_strands(db_session)
        assert "Number and Number Sense" in strands
        assert "Scientific Investigation" in strands

    def test_get_strands_by_subject(self, db_session, sample_standards):
        strands = get_strands(db_session, subject="Mathematics")
        assert "Number and Number Sense" in strands
        assert "Scientific Investigation" not in strands

    def test_standards_count(self, db_session, sample_standards):
        assert standards_count(db_session) == 5

    def test_standards_count_empty(self, db_session):
        assert standards_count(db_session) == 0
