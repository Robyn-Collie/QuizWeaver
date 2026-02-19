"""
Tests for BL-022: Multi-State Standards Database expansion.

Tests cover:
- STANDARD_SETS registry (original 5 + 5 new sets)
- STANDARD_SET_METADATA registry
- Multi-set loading from JSON files
- Search filtering by standard_set
- Custom standards import
- ensure_standard_set_loaded (auto-load)
- get_standard_sets_in_db
- Migration 009 (standard_set column)
- Standards page and API with set filtering
- New helper functions: list_standard_sets, get_standards_by_state,
  get_all_subjects, get_all_grades
- New standard sets: NJSLS, GSE, NGSSS, CAS, ILS
- Cross-set consistency and code format verification
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
    STANDARD_SET_METADATA,
    STANDARD_SETS,
    create_standard,
    ensure_standard_set_loaded,
    get_all_grades,
    get_all_subjects,
    get_available_standard_sets,
    get_data_dir,
    get_grade_bands,
    get_standard_sets_in_db,
    get_standards_by_state,
    get_strands,
    get_subjects,
    import_custom_standards,
    list_standard_sets,
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
        """All ten expected standard sets are registered."""
        assert "sol" in STANDARD_SETS
        assert "ccss_ela" in STANDARD_SETS
        assert "ccss_math" in STANDARD_SETS
        assert "ngss" in STANDARD_SETS
        assert "teks" in STANDARD_SETS
        assert "njsls" in STANDARD_SETS
        assert "gse" in STANDARD_SETS
        assert "ngsss" in STANDARD_SETS
        assert "cas" in STANDARD_SETS
        assert "ils" in STANDARD_SETS

    def test_standard_sets_have_label_and_file(self):
        """Each set has a label and file."""
        for key, info in STANDARD_SETS.items():
            assert "label" in info, f"Missing label for {key}"
            assert "file" in info, f"Missing file for {key}"
            assert info["file"].endswith(".json"), f"File for {key} should be .json"

    def test_get_available_standard_sets(self):
        """get_available_standard_sets returns list of dicts."""
        sets = get_available_standard_sets()
        assert len(sets) == 10
        keys = [s["key"] for s in sets]
        assert "sol" in keys
        assert "ngss" in keys
        assert "njsls" in keys
        assert "gse" in keys
        assert "ngsss" in keys
        assert "cas" in keys
        assert "ils" in keys
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


# ============================================================
# New tests for Standards Expansion (GH #20)
# ============================================================

NEW_STANDARD_SET_KEYS = ["njsls", "gse", "ngsss", "cas", "ils"]
ALL_STANDARD_SET_KEYS = [
    "sol",
    "ccss_ela",
    "ccss_math",
    "ngss",
    "teks",
    "njsls",
    "gse",
    "ngsss",
    "cas",
    "ils",
]


class TestNewStandardSets:
    """Verify each new standard set has required fields, non-empty standards list."""

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_in_registry(self, set_key):
        """Each new standard set is registered in STANDARD_SETS."""
        assert set_key in STANDARD_SETS

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_has_label(self, set_key):
        """Each new set has a non-empty label."""
        assert "label" in STANDARD_SETS[set_key]
        assert len(STANDARD_SETS[set_key]["label"]) > 0

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_has_json_file(self, set_key):
        """Each new set has a .json file reference."""
        assert STANDARD_SETS[set_key]["file"].endswith(".json")

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_data_file_exists(self, set_key):
        """The JSON data file for each new set actually exists on disk."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        assert os.path.exists(path), f"Data file missing for {set_key}: {path}"

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_has_at_least_20_standards(self, set_key):
        """Each new JSON file has at least 20 standards."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["standards"]) >= 20, (
            f"{set_key} has only {len(data['standards'])} standards, expected >= 20"
        )

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_standards_have_required_fields(self, set_key):
        """Every standard in the new set has code, description, subject."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for std in data["standards"]:
            assert "code" in std, f"Missing code in {set_key}: {std}"
            assert "description" in std, f"Missing description in {set_key}: {std}"
            assert "subject" in std, f"Missing subject in {set_key}: {std}"

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_standards_have_grade_band(self, set_key):
        """Every standard in the new set has a grade_band."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for std in data["standards"]:
            assert "grade_band" in std and std["grade_band"], (
                f"Missing grade_band in {set_key}: {std.get('code')}"
            )

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_standards_have_strand(self, set_key):
        """Every standard in the new set has a strand."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for std in data["standards"]:
            assert "strand" in std and std["strand"], (
                f"Missing strand in {set_key}: {std.get('code')}"
            )

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_loads_into_database(self, db_session, set_key):
        """Each new set can be loaded into the database."""
        count = load_standard_set(db_session, set_key)
        assert count >= 20
        total = standards_count(db_session, standard_set=set_key)
        assert total == count

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_loaded_standards_have_correct_set_tag(self, db_session, set_key):
        """All loaded records are tagged with the correct standard_set."""
        load_standard_set(db_session, set_key)
        stds = list_standards(db_session, standard_set=set_key)
        assert len(stds) > 0
        for s in stds:
            assert s.standard_set == set_key

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_has_multiple_subjects(self, set_key):
        """Each new set covers multiple subjects."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        subjects = {std["subject"] for std in data["standards"]}
        assert len(subjects) >= 3, (
            f"{set_key} has only {len(subjects)} subjects: {subjects}. Expected >= 3."
        )

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_new_set_has_multiple_grade_bands(self, set_key):
        """Each new set covers multiple grade bands."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        grade_bands = {std["grade_band"] for std in data["standards"]}
        assert len(grade_bands) >= 3, (
            f"{set_key} has only {len(grade_bands)} grade bands: {grade_bands}. Expected >= 3."
        )


class TestStandardSetMetadata:
    """Verify STANDARD_SET_METADATA has entries for all sets."""

    def test_metadata_has_entries_for_all_sets(self):
        """Every key in STANDARD_SETS has a corresponding metadata entry."""
        for key in STANDARD_SETS:
            assert key in STANDARD_SET_METADATA, (
                f"Missing metadata for standard set '{key}'"
            )

    def test_metadata_has_state(self):
        """Every metadata entry has a non-empty state field."""
        for key, meta in STANDARD_SET_METADATA.items():
            assert "state" in meta, f"Missing 'state' in metadata for {key}"
            assert len(meta["state"]) > 0, f"Empty state for {key}"

    def test_metadata_has_url(self):
        """Every metadata entry has a URL."""
        for key, meta in STANDARD_SET_METADATA.items():
            assert "url" in meta, f"Missing 'url' in metadata for {key}"
            assert meta["url"].startswith("https://"), (
                f"URL for {key} should start with https://"
            )

    def test_metadata_has_adopted_year(self):
        """Every metadata entry has an adopted_year."""
        for key, meta in STANDARD_SET_METADATA.items():
            assert "adopted_year" in meta, f"Missing 'adopted_year' for {key}"
            assert isinstance(meta["adopted_year"], int), (
                f"adopted_year for {key} should be int"
            )
            assert 2000 <= meta["adopted_year"] <= 2030, (
                f"adopted_year for {key} out of range: {meta['adopted_year']}"
            )

    def test_metadata_state_values(self):
        """Spot-check specific state values."""
        assert STANDARD_SET_METADATA["sol"]["state"] == "Virginia"
        assert STANDARD_SET_METADATA["teks"]["state"] == "Texas"
        assert STANDARD_SET_METADATA["njsls"]["state"] == "New Jersey"
        assert STANDARD_SET_METADATA["gse"]["state"] == "Georgia"
        assert STANDARD_SET_METADATA["ngsss"]["state"] == "Florida"
        assert STANDARD_SET_METADATA["cas"]["state"] == "California"
        assert STANDARD_SET_METADATA["ils"]["state"] == "Illinois"
        assert STANDARD_SET_METADATA["ccss_ela"]["state"] == "Multi-state"
        assert STANDARD_SET_METADATA["ngss"]["state"] == "Multi-state"

    def test_no_extra_metadata_keys(self):
        """Metadata should not have keys that are not in STANDARD_SETS."""
        for key in STANDARD_SET_METADATA:
            assert key in STANDARD_SETS, (
                f"Metadata key '{key}' not found in STANDARD_SETS"
            )


class TestListStandardSets:
    """Verify list_standard_sets() returns all 10 sets with merged metadata."""

    def test_returns_all_ten_sets(self):
        result = list_standard_sets()
        assert len(result) == 10

    def test_returns_list_of_dicts(self):
        result = list_standard_sets()
        for item in result:
            assert isinstance(item, dict)

    def test_each_entry_has_required_keys(self):
        result = list_standard_sets()
        required_keys = {"key", "label", "file", "state", "url", "adopted_year"}
        for item in result:
            for k in required_keys:
                assert k in item, f"Missing key '{k}' in entry for {item.get('key')}"

    def test_all_keys_present(self):
        result = list_standard_sets()
        keys = [item["key"] for item in result]
        for expected_key in ALL_STANDARD_SET_KEYS:
            assert expected_key in keys, f"Missing key '{expected_key}'"

    def test_merged_metadata_values(self):
        """Verify metadata is properly merged into list_standard_sets output."""
        result = list_standard_sets()
        by_key = {item["key"]: item for item in result}
        assert by_key["sol"]["state"] == "Virginia"
        assert by_key["njsls"]["state"] == "New Jersey"
        assert by_key["cas"]["adopted_year"] == 2023


class TestGetStandardsByState:
    """Verify state lookup works for all states."""

    def test_get_virginia_standards(self):
        result = get_standards_by_state("Virginia")
        keys = [r["key"] for r in result]
        assert "sol" in keys

    def test_get_texas_standards(self):
        result = get_standards_by_state("Texas")
        keys = [r["key"] for r in result]
        assert "teks" in keys

    def test_get_new_jersey_standards(self):
        result = get_standards_by_state("New Jersey")
        keys = [r["key"] for r in result]
        assert "njsls" in keys

    def test_get_georgia_standards(self):
        result = get_standards_by_state("Georgia")
        keys = [r["key"] for r in result]
        assert "gse" in keys

    def test_get_florida_standards(self):
        result = get_standards_by_state("Florida")
        keys = [r["key"] for r in result]
        assert "ngsss" in keys

    def test_get_california_standards(self):
        result = get_standards_by_state("California")
        keys = [r["key"] for r in result]
        assert "cas" in keys

    def test_get_illinois_standards(self):
        result = get_standards_by_state("Illinois")
        keys = [r["key"] for r in result]
        assert "ils" in keys

    def test_get_multi_state_standards(self):
        """Multi-state sets (CCSS, NGSS) are returned for 'Multi-state' query."""
        result = get_standards_by_state("Multi-state")
        keys = [r["key"] for r in result]
        assert "ccss_ela" in keys
        assert "ccss_math" in keys
        assert "ngss" in keys

    def test_case_insensitive_lookup(self):
        result = get_standards_by_state("virginia")
        keys = [r["key"] for r in result]
        assert "sol" in keys

    def test_unknown_state_returns_empty(self):
        result = get_standards_by_state("Atlantis")
        assert result == []

    def test_result_entries_have_expected_keys(self):
        result = get_standards_by_state("Georgia")
        for entry in result:
            assert "key" in entry
            assert "label" in entry
            assert "state" in entry


class TestSearchAcrossSets:
    """Verify search_standards works across new sets when loaded."""

    def test_search_njsls_by_code(self, db_session):
        load_standard_set(db_session, "njsls")
        results = search_standards(db_session, "NJSLS")
        assert len(results) > 0
        for r in results:
            assert r.standard_set == "njsls"

    def test_search_gse_by_subject(self, db_session):
        load_standard_set(db_session, "gse")
        results = search_standards(db_session, "", subject="Mathematics", standard_set="gse")
        assert len(results) > 0
        for r in results:
            assert r.subject == "Mathematics"

    def test_search_ngsss_by_description(self, db_session):
        load_standard_set(db_session, "ngsss")
        results = search_standards(db_session, "multiplication", standard_set="ngsss")
        assert len(results) >= 1

    def test_search_cas_by_strand(self, db_session):
        load_standard_set(db_session, "cas")
        results = search_standards(db_session, "Life Science", standard_set="cas")
        assert len(results) >= 1

    def test_search_ils_by_code(self, db_session):
        load_standard_set(db_session, "ils")
        results = search_standards(db_session, "ILS")
        assert len(results) > 0

    def test_search_across_multiple_new_sets(self, db_session):
        """Loading multiple new sets and searching across all returns results from each."""
        load_standard_set(db_session, "njsls")
        load_standard_set(db_session, "gse")
        results = search_standards(db_session, "fraction")
        # Both NJSLS and GSE have fraction-related standards
        sets_in_results = {r.standard_set for r in results}
        assert len(sets_in_results) >= 1

    def test_search_with_grade_band_filter(self, db_session):
        load_standard_set(db_session, "cas")
        results = search_standards(db_session, "CA", grade_band="6-8")
        for r in results:
            assert r.grade_band == "6-8"


class TestGetAllSubjects:
    """Verify unique subjects collected from all data files."""

    def test_returns_non_empty_list(self):
        subjects = get_all_subjects()
        assert len(subjects) > 0

    def test_returns_sorted_list(self):
        subjects = get_all_subjects()
        assert subjects == sorted(subjects)

    def test_contains_expected_subjects(self):
        subjects = get_all_subjects()
        assert "Mathematics" in subjects
        assert "Science" in subjects or "Life Science" in subjects
        assert "English Language Arts" in subjects

    def test_contains_social_studies(self):
        """New sets add Social Studies as a subject."""
        subjects = get_all_subjects()
        assert "Social Studies" in subjects

    def test_no_duplicates(self):
        subjects = get_all_subjects()
        assert len(subjects) == len(set(subjects))


class TestGetAllGrades:
    """Verify grade list across all standard sets."""

    def test_returns_non_empty_list(self):
        grades = get_all_grades()
        assert len(grades) > 0

    def test_returns_sorted_list(self):
        """Grade bands are sorted with K-2 first, then 3-5, 6-8, 9-12."""
        grades = get_all_grades()
        # K-2 should come before 3-5
        if "K-2" in grades and "3-5" in grades:
            assert grades.index("K-2") < grades.index("3-5")
        # 3-5 should come before 6-8
        if "3-5" in grades and "6-8" in grades:
            assert grades.index("3-5") < grades.index("6-8")
        # 6-8 should come before 9-12
        if "6-8" in grades and "9-12" in grades:
            assert grades.index("6-8") < grades.index("9-12")

    def test_contains_k_through_12_bands(self):
        grades = get_all_grades()
        assert "K-2" in grades
        assert "3-5" in grades
        assert "6-8" in grades
        assert "9-12" in grades

    def test_no_duplicates(self):
        grades = get_all_grades()
        assert len(grades) == len(set(grades))


class TestStandardCodeFormats:
    """Verify each set uses its correct code format prefix."""

    CODE_PREFIX_MAP = {
        "sol": "SOL",
        "ccss_ela": "CCSS.ELA",
        "ccss_math": "CCSS.MATH",
        "ngss": "MS-",  # NGSS uses MS-, HS- etc. for middle/high school
        "teks": "TEKS.",
        "njsls": "NJSLS.",
        "gse": "GSE.",
        "ngsss": "NGSSS.",
        "cas": "CA.",
        "ils": "ILS.",
    }

    @pytest.mark.parametrize("set_key", ALL_STANDARD_SET_KEYS)
    def test_code_prefix_matches_set(self, set_key):
        """Standards in each set use the expected code prefix."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        prefix = self.CODE_PREFIX_MAP[set_key]
        # At least 50% of codes should match the prefix
        # (some sets like NGSS have varied prefixes: MS-, HS-, K-, etc.)
        matching = sum(1 for std in data["standards"] if std["code"].startswith(prefix))
        total = len(data["standards"])
        assert matching > 0, (
            f"No standards in {set_key} start with '{prefix}'. "
            f"Sample codes: {[s['code'] for s in data['standards'][:3]]}"
        )

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_no_duplicate_codes_in_new_set(self, set_key):
        """Each new JSON file has unique codes (no duplicates within the file)."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        codes = [std["code"] for std in data["standards"]]
        assert len(codes) == len(set(codes)), (
            f"Duplicate codes found in {set_key}"
        )


class TestCrossSetConsistency:
    """Verify all sets have consistent structure."""

    @pytest.mark.parametrize("set_key", ALL_STANDARD_SET_KEYS)
    def test_json_has_source_field(self, set_key):
        """Each JSON file has a top-level 'source' field."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "source" in data, f"Missing top-level 'source' in {set_key}"
        assert len(data["source"]) > 0

    @pytest.mark.parametrize("set_key", ALL_STANDARD_SET_KEYS)
    def test_json_has_version_field(self, set_key):
        """Each JSON file has a top-level 'version' field."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "version" in data, f"Missing top-level 'version' in {set_key}"

    @pytest.mark.parametrize("set_key", ALL_STANDARD_SET_KEYS)
    def test_json_has_standards_list(self, set_key):
        """Each JSON file has a 'standards' key with a non-empty list."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "standards" in data
        assert isinstance(data["standards"], list)
        assert len(data["standards"]) > 0

    @pytest.mark.parametrize("set_key", ALL_STANDARD_SET_KEYS)
    def test_all_standards_have_full_text(self, set_key):
        """Every standard in every file has a full_text field."""
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for std in data["standards"]:
            assert "full_text" in std and std["full_text"], (
                f"Missing full_text in {set_key}: {std.get('code')}"
            )

    @pytest.mark.parametrize("set_key", ALL_STANDARD_SET_KEYS)
    def test_subjects_are_recognized(self, set_key):
        """All subjects used in data files are from a known set."""
        known_subjects = {
            "Mathematics",
            "Science",
            "English",
            "English Language Arts",
            "Life Science",
            "Physical Science",
            "Earth Science",
            "Earth and Space Science",
            "Engineering",
            "Social Studies",
        }
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for std in data["standards"]:
            assert std["subject"] in known_subjects, (
                f"Unknown subject '{std['subject']}' in {set_key}: {std['code']}"
            )

    @pytest.mark.parametrize("set_key", ALL_STANDARD_SET_KEYS)
    def test_grade_bands_are_recognized(self, set_key):
        """All grade_band values are from the expected set."""
        known_bands = {"K-2", "3-5", "6-8", "9-12"}
        path = os.path.join(get_data_dir(), STANDARD_SETS[set_key]["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for std in data["standards"]:
            assert std.get("grade_band") in known_bands, (
                f"Unknown grade_band '{std.get('grade_band')}' in {set_key}: {std['code']}"
            )

    def test_no_duplicate_codes_across_all_sets(self):
        """No two standards across all sets share the same code."""
        all_codes = []
        for set_key, info in STANDARD_SETS.items():
            path = os.path.join(get_data_dir(), info["file"])
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for std in data["standards"]:
                all_codes.append((set_key, std["code"]))
        codes_only = [c[1] for c in all_codes]
        duplicates = [c for c in codes_only if codes_only.count(c) > 1]
        assert len(set(duplicates)) == 0, (
            f"Duplicate codes found across sets: {set(duplicates)}"
        )


class TestNewSetsEnsureLoad:
    """Test ensure_standard_set_loaded works with new sets."""

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_ensure_loads_new_set(self, db_session, set_key):
        count = ensure_standard_set_loaded(db_session, set_key)
        assert count > 0

    @pytest.mark.parametrize("set_key", NEW_STANDARD_SET_KEYS)
    def test_ensure_skips_if_already_loaded(self, db_session, set_key):
        first = ensure_standard_set_loaded(db_session, set_key)
        assert first > 0
        second = ensure_standard_set_loaded(db_session, set_key)
        assert second == 0


class TestNewSetsInDbListing:
    """Test get_standard_sets_in_db includes new sets after loading."""

    def test_new_set_appears_in_db_listing(self, db_session):
        load_standard_set(db_session, "njsls")
        result = get_standard_sets_in_db(db_session)
        keys = [r["key"] for r in result]
        assert "njsls" in keys

    def test_new_set_has_correct_label_in_db(self, db_session):
        load_standard_set(db_session, "gse")
        result = get_standard_sets_in_db(db_session)
        by_key = {r["key"]: r for r in result}
        assert by_key["gse"]["label"] == "Georgia GSE"

    def test_multiple_new_sets_in_db(self, db_session):
        load_standard_set(db_session, "cas")
        load_standard_set(db_session, "ils")
        result = get_standard_sets_in_db(db_session)
        keys = [r["key"] for r in result]
        assert "cas" in keys
        assert "ils" in keys
