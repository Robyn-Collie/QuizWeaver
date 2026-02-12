"""
Extended tests for migration helper functions in src/migrations.py.

Covers get_migration_files, check_if_migration_needed,
create_default_class_if_needed, and init_database_with_migrations.

Run with: python -m pytest tests/test_migrations_extended.py -v
"""

import os
import sqlite3
import sys
import tempfile

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import get_engine, init_db
from src.migrations import (
    check_if_migration_needed,
    create_default_class_if_needed,
    get_migration_files,
    init_database_with_migrations,
    run_migrations,
)


@pytest.fixture
def tmp_db():
    """Create a temporary database file for testing."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    yield tmp.name
    try:
        os.remove(tmp.name)
    except OSError:
        pass


# =========================================================================
# TestGetMigrationFiles
# =========================================================================


class TestGetMigrationFiles:
    """Tests for the get_migration_files helper function."""

    def test_returns_files_from_real_dir(self):
        """Call with the real 'migrations' directory and verify non-empty list
        of .sql files is returned."""
        results = get_migration_files("migrations")
        assert len(results) > 0, "Should find at least one migration file"
        for filename, filepath in results:
            assert filename.endswith(".sql"), f"Each file should be a .sql file, got {filename}"

    def test_returns_empty_for_nonexistent_dir(self):
        """Call with a directory that does not exist and verify empty list."""
        results = get_migration_files("nonexistent_migrations_dir")
        assert results == [], "Should return empty list for nonexistent directory"

    def test_returns_sorted_files(self):
        """Create a temp dir with out-of-order .sql files and verify they
        are returned in sorted order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files in reverse order
            for name in ["002_second.sql", "001_first.sql", "003_third.sql"]:
                open(os.path.join(tmpdir, name), "w").close()

            results = get_migration_files(tmpdir)
            filenames = [fname for fname, _ in results]
            assert filenames == ["001_first.sql", "002_second.sql", "003_third.sql"], (
                f"Files should be sorted, got {filenames}"
            )

    def test_returns_tuples(self):
        """Verify each element returned is a (filename, filepath) tuple."""
        results = get_migration_files("migrations")
        assert len(results) > 0, "Need at least one file to test tuple structure"
        for item in results:
            assert isinstance(item, tuple), f"Each item should be a tuple, got {type(item)}"
            assert len(item) == 2, f"Each tuple should have 2 elements, got {len(item)}"
            filename, filepath = item
            assert isinstance(filename, str), "Filename should be a string"
            assert isinstance(filepath, str), "Filepath should be a string"
            assert filename.endswith(".sql"), f"Filename should end with .sql, got {filename}"
            assert filepath.endswith(filename), f"Filepath should end with the filename: {filepath} vs {filename}"


# =========================================================================
# TestCheckIfMigrationNeeded
# =========================================================================


class TestCheckIfMigrationNeeded:
    """Tests for the check_if_migration_needed helper function."""

    def test_new_db_needs_migration(self):
        """A nonexistent database path should indicate migration is needed."""
        result = check_if_migration_needed("this_db_does_not_exist_12345.db")
        assert result is True, "Nonexistent DB should need migration"

    def test_migrated_db_no_migration(self, tmp_db):
        """A database that has been migrated (has classes table) should not
        need migration."""
        # Run the real migrations to create the classes table
        run_migrations(tmp_db, verbose=False)
        result = check_if_migration_needed(tmp_db)
        assert result is False, "Migrated DB should not need migration"

    def test_empty_db_needs_no_migration_when_orm_creates_tables(self, tmp_db):
        """When init_db creates all tables via ORM (including classes),
        check_if_migration_needed should return False."""
        engine = get_engine(tmp_db)
        init_db(engine)
        engine.dispose()
        result = check_if_migration_needed(tmp_db)
        assert result is False, "DB with ORM-created classes table should not need migration"

    def test_db_without_classes_needs_migration(self, tmp_db):
        """A bare SQLite file that has some table but not 'classes' should
        indicate migration is needed."""
        conn = sqlite3.connect(tmp_db)
        conn.execute("CREATE TABLE dummy (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        result = check_if_migration_needed(tmp_db)
        assert result is True, "DB without classes table should need migration"


# =========================================================================
# TestCreateDefaultClassIfNeeded
# =========================================================================


class TestCreateDefaultClassIfNeeded:
    """Tests for the create_default_class_if_needed helper function."""

    def _prepare_migrated_db(self, db_path):
        """Run migrations and ORM init to get a fully ready database."""
        run_migrations(db_path, verbose=False)
        engine = get_engine(db_path)
        init_db(engine)
        engine.dispose()

    def test_creates_legacy_class(self, tmp_db):
        """After calling create_default_class_if_needed on a fresh migrated DB,
        a class with id=1 and name containing 'Legacy' should exist."""
        self._prepare_migrated_db(tmp_db)

        # The migration SQL itself inserts the legacy class, so delete it
        # first to test the Python function in isolation.
        conn = sqlite3.connect(tmp_db)
        conn.execute("DELETE FROM classes WHERE id = 1")
        conn.commit()
        conn.close()

        create_default_class_if_needed(tmp_db)

        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM classes WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row is not None, "Legacy class should exist at id=1"
        assert "Legacy" in row[1], f"Class name should contain 'Legacy', got '{row[1]}'"

    def test_idempotent(self, tmp_db):
        """Calling create_default_class_if_needed twice should still result
        in exactly one legacy class."""
        self._prepare_migrated_db(tmp_db)

        # Delete legacy class inserted by migration SQL, then call twice
        conn = sqlite3.connect(tmp_db)
        conn.execute("DELETE FROM classes WHERE id = 1")
        conn.commit()
        conn.close()

        create_default_class_if_needed(tmp_db)
        create_default_class_if_needed(tmp_db)

        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM classes WHERE id = 1")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1, f"Should have exactly 1 legacy class, got {count}"

    def test_updates_null_quiz_class_ids(self, tmp_db):
        """A quiz with class_id=NULL should be updated to class_id=1 after
        calling create_default_class_if_needed."""
        self._prepare_migrated_db(tmp_db)

        # Insert a quiz with NULL class_id directly via SQL
        conn = sqlite3.connect(tmp_db)
        conn.execute("INSERT INTO quizzes (id, title, class_id, status) VALUES (1, 'Old Quiz', NULL, 'generated')")
        conn.commit()
        conn.close()

        create_default_class_if_needed(tmp_db)

        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT class_id FROM quizzes WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row is not None, "Quiz should exist"
        assert row[0] == 1, f"Quiz class_id should be 1, got {row[0]}"

    def test_preserves_existing_quiz_class_ids(self, tmp_db):
        """A quiz that already has a non-NULL class_id should not be changed."""
        self._prepare_migrated_db(tmp_db)

        # Create a second class, then a quiz assigned to it
        conn = sqlite3.connect(tmp_db)
        conn.execute("INSERT INTO classes (id, name) VALUES (2, 'Other Class')")
        conn.execute("INSERT INTO quizzes (id, title, class_id, status) VALUES (1, 'Assigned Quiz', 2, 'generated')")
        conn.commit()
        conn.close()

        create_default_class_if_needed(tmp_db)

        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT class_id FROM quizzes WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row is not None, "Quiz should exist"
        assert row[0] == 2, f"Quiz class_id should remain 2 (not overwritten), got {row[0]}"


# =========================================================================
# TestInitDatabaseWithMigrations
# =========================================================================


class TestInitDatabaseWithMigrations:
    """Tests for the init_database_with_migrations entry point."""

    def test_full_init_on_fresh_db(self, tmp_db):
        """Calling init_database_with_migrations on a fresh temp DB should
        return True and create the classes table."""
        # Remove the temp file so we start from scratch (nonexistent DB)
        os.remove(tmp_db)

        result = init_database_with_migrations(tmp_db)
        assert result is True, "init_database_with_migrations should return True"

        # Verify the classes table was created
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='classes'")
        row = cursor.fetchone()
        conn.close()

        assert row is not None, "classes table should exist after full init"

    def test_init_on_existing_db(self, tmp_db):
        """Calling init_database_with_migrations twice should succeed both
        times (idempotent)."""
        # Remove temp file for a clean start
        os.remove(tmp_db)

        result1 = init_database_with_migrations(tmp_db)
        result2 = init_database_with_migrations(tmp_db)

        assert result1 is True, "First init should return True"
        assert result2 is True, "Second init should also return True"
