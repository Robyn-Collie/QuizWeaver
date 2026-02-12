"""
Tests for BL-022: Multi-State Standards Database expansion.

Tests cover:
- STANDARD_SETS registry
- Multi-set loading from JSON files
- Search filtering by standard_set
- Custom standards import
- ensure_standard_set_loaded (auto-load)
- get_standard_sets_in_db
- Migration 009 (standard_set column)
- Standards page and API with set filtering
"""

import json
import os
import sqlite3
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.standards import (
    STANDARD_SETS,
    create_standard,
    ensure_standard_set_loaded,
    get_available_standard_sets,
    get_data_dir,
    get_grade_bands,
    get_standard_sets_in_db,
    get_strands,
    get_subjects,
    import_custom_standards,
    list_standards,
    load_standard_set,
    search_standards,
    standards_count,
)


@pytest.fixture
def db_session():
    """Create a temporary in-memory database session."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()
    os.remove(tmp.name)


class TestStandardSetsRegistry:
    """Tests for the STANDARD_SETS constant and metadata."""

    def test_standard_sets_has_expected_keys(self):
        """All five expected standard sets are registered."""
        assert "sol" in STANDARD_SETS
        assert "ccss_ela" in STANDARD_SETS
        assert "ccss_math" in STANDARD_SETS
        assert "ngss" in STANDARD_SETS
        assert "teks" in STANDARD_SETS

    def test_standard_sets_have_label_and_file(self):
        """Each set has a label and file."""
        for key, info in STANDARD_SETS.items():
            assert "label" in info, f"Missing label for {key}"
            assert "file" in info, f"Missing file for {key}"
            assert info["file"].endswith(".json"), f"File for {key} should be .json"

    def test_get_available_standard_sets(self):
        """get_available_standard_sets returns list of dicts."""
        sets = get_available_standard_sets()
        assert len(sets) == 5
        keys = [s["key"] for s in sets]
        assert "sol" in keys
        assert "ngss" in keys
        for s in sets:
            assert "key" in s
            assert "label" in s
            assert "file" in s


class TestDataFilesExist:
    """Verify all standards JSON data files exist and are valid."""

    def test_sol_standards_file_exists(self):
        path = os.path.join(get_data_dir(), "sol_standards.json")
        assert os.path.exists(path)

    def test_ccss_ela_file_exists(self):
        path = os.path.join(get_data_dir(), "ccss_ela_standards.json")
        assert os.path.exists(path)

    def test_ccss_math_file_exists(self):
        path = os.path.join(get_data_dir(), "ccss_math_standards.json")
        assert os.path.exists(path)

    def test_ngss_file_exists(self):
        path = os.path.join(get_data_dir(), "ngss_standards.json")
        assert os.path.exists(path)

    def test_teks_file_exists(self):
        path = os.path.join(get_data_dir(), "teks_standards.json")
        assert os.path.exists(path)

    def test_all_files_valid_json(self):
        """All data files parse as valid JSON with a 'standards' key."""
        for key, info in STANDARD_SETS.items():
            path = os.path.join(get_data_dir(), info["file"])
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert "standards" in data, f"Missing 'standards' key in {info['file']}"
            assert len(data["standards"]) >= 20, (
                f"Expected at least 20 standards in {info['file']}, got {len(data['standards'])}"
            )

    def test_each_standard_has_required_fields(self):
        """Every standard in every file has code, description, subject."""
        for key, info in STANDARD_SETS.items():
            path = os.path.join(get_data_dir(), info["file"])
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for std in data["standards"]:
                assert "code" in std, f"Missing code in {info['file']}: {std}"
                assert "description" in std, f"Missing description in {info['file']}: {std}"
                assert "subject" in std, f"Missing subject in {info['file']}: {std}"


class TestLoadStandardSet:
    """Tests for loading individual standard sets."""

    def test_load_sol_standards(self, db_session):
        count = load_standard_set(db_session, "sol")
        assert count > 0
        total = standards_count(db_session, standard_set="sol")
        assert total == count

    def test_load_ccss_ela_standards(self, db_session):
        count = load_standard_set(db_session, "ccss_ela")
        assert count >= 20

    def test_load_ccss_math_standards(self, db_session):
        count = load_standard_set(db_session, "ccss_math")
        assert count >= 20

    def test_load_ngss_standards(self, db_session):
        count = load_standard_set(db_session, "ngss")
        assert count >= 20

    def test_load_teks_standards(self, db_session):
        count = load_standard_set(db_session, "teks")
        assert count >= 20

    def test_load_unknown_set_raises(self, db_session):
        with pytest.raises(ValueError, match="Unknown standard set"):
            load_standard_set(db_session, "imaginary_set")

    def test_loaded_standards_have_correct_standard_set(self, db_session):
        """Loading NGSS tags all records with standard_set='ngss'."""
        load_standard_set(db_session, "ngss")
        stds = list_standards(db_session, standard_set="ngss")
        assert len(stds) > 0
        for s in stds:
            assert s.standard_set == "ngss"


class TestEnsureStandardSetLoaded:
    """Tests for ensure_standard_set_loaded (auto-load)."""

    def test_loads_if_not_present(self, db_session):
        count = ensure_standard_set_loaded(db_session, "ccss_ela")
        assert count > 0

    def test_skips_if_already_loaded(self, db_session):
        first = ensure_standard_set_loaded(db_session, "ccss_ela")
        assert first > 0
        second = ensure_standard_set_loaded(db_session, "ccss_ela")
        assert second == 0

    def test_returns_zero_for_unknown_set(self, db_session):
        result = ensure_standard_set_loaded(db_session, "nonexistent")
        assert result == 0


class TestMultiSetFiltering:
    """Tests for filtering and searching across multiple loaded sets."""

    @pytest.fixture(autouse=True)
    def load_multiple_sets(self, db_session):
        load_standard_set(db_session, "sol")
        load_standard_set(db_session, "ccss_math")
        self.session = db_session

    def test_list_all_standards_returns_both_sets(self):
        all_stds = list_standards(self.session)
        sol_stds = list_standards(self.session, standard_set="sol")
        math_stds = list_standards(self.session, standard_set="ccss_math")
        assert len(all_stds) == len(sol_stds) + len(math_stds)

    def test_search_filter_by_set(self):
        """Searching within a set only returns standards from that set."""
        results = search_standards(self.session, "Mathematics", standard_set="ccss_math")
        for r in results:
            assert r.standard_set == "ccss_math"

    def test_subjects_filtered_by_set(self):
        sol_subjects = get_subjects(self.session, standard_set="sol")
        math_subjects = get_subjects(self.session, standard_set="ccss_math")
        # CCSS Math is all Mathematics
        assert "Mathematics" in math_subjects

    def test_grade_bands_filtered_by_set(self):
        bands = get_grade_bands(self.session, standard_set="ccss_math")
        assert "6-8" in bands

    def test_standards_count_by_set(self):
        total = standards_count(self.session)
        sol_count = standards_count(self.session, standard_set="sol")
        math_count = standards_count(self.session, standard_set="ccss_math")
        assert total == sol_count + math_count


class TestCustomStandardsImport:
    """Tests for import_custom_standards."""

    def test_import_custom_standards(self, db_session):
        custom_data = [
            {"code": "CUSTOM-001", "description": "Test standard 1", "subject": "Art"},
            {"code": "CUSTOM-002", "description": "Test standard 2", "subject": "Art"},
        ]
        count = import_custom_standards(db_session, custom_data, "my_school", "My School Standards")
        assert count == 2

        stds = list_standards(db_session, standard_set="my_school")
        assert len(stds) == 2
        for s in stds:
            assert s.standard_set == "my_school"
            assert s.source == "My School Standards"


class TestGetStandardSetsInDb:
    """Tests for get_standard_sets_in_db."""

    def test_empty_db_returns_empty(self, db_session):
        result = get_standard_sets_in_db(db_session)
        assert result == []

    def test_returns_loaded_sets_with_counts(self, db_session):
        load_standard_set(db_session, "sol")
        load_standard_set(db_session, "ngss")
        result = get_standard_sets_in_db(db_session)
        keys = [r["key"] for r in result]
        assert "sol" in keys
        assert "ngss" in keys
        for r in result:
            assert r["count"] > 0
            assert "label" in r


class TestCreateStandardWithSet:
    """Test that create_standard accepts standard_set param."""

    def test_create_with_standard_set(self, db_session):
        std = create_standard(
            db_session,
            code="TEST-001",
            description="Test",
            subject="Math",
            standard_set="ccss_math",
        )
        assert std.standard_set == "ccss_math"

    def test_create_default_set_is_sol(self, db_session):
        std = create_standard(
            db_session,
            code="TEST-002",
            description="Test default",
            subject="Math",
        )
        assert std.standard_set == "sol"


class TestMigration009:
    """Test migration 009 for standard_set column."""

    def test_migration_adds_standard_set_column(self):
        """Simulate running migration 009 on a fresh standards table."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            conn = sqlite3.connect(tmp.name)
            # Create standards table WITHOUT standard_set (pre-migration)
            conn.execute("""
                CREATE TABLE standards (
                    id INTEGER PRIMARY KEY,
                    code TEXT UNIQUE NOT NULL,
                    description TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    grade_band TEXT,
                    strand TEXT,
                    full_text TEXT,
                    source TEXT DEFAULT 'Virginia SOL',
                    version TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Insert a pre-migration record
            conn.execute(
                "INSERT INTO standards (code, description, subject) VALUES (?, ?, ?)",
                ("SOL 8.1", "Test", "Mathematics"),
            )
            conn.commit()

            # Run migration 009
            migration_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "migrations",
                "009_expand_standards.sql",
            )
            with open(migration_path) as f:
                migration_sql = f.read()
            conn.executescript(migration_sql)
            conn.commit()

            # Verify column exists and default is 'sol'
            cursor = conn.execute("PRAGMA table_info(standards)")
            columns = {row[1]: row for row in cursor.fetchall()}
            assert "standard_set" in columns

            # Verify UPDATE set existing records to 'sol'
            cursor = conn.execute("SELECT standard_set FROM standards WHERE code='SOL 8.1'")
            row = cursor.fetchone()
            assert row[0] == "sol"

            # Verify index was created
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_standards_standard_set'"
            )
            assert cursor.fetchone() is not None

            conn.close()
        finally:
            os.remove(tmp.name)


class TestStrandsWithStandardSet:
    """Test get_strands filtered by standard_set."""

    def test_strands_filtered_by_set(self, db_session):
        load_standard_set(db_session, "ngss")
        strands = get_strands(db_session, standard_set="ngss")
        assert len(strands) > 0
        # NGSS should have science-related strands
        all_strands_text = " ".join(strands).lower()
        assert "energy" in all_strands_text or "matter" in all_strands_text or "earth" in all_strands_text
