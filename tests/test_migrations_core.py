"""Tests for src/migrations.py — database migration runner.

Covers migration file discovery, idempotent application, schema checks,
default class creation, and error handling.
"""

import os
import sqlite3
import tempfile

import pytest

from src.migrations import (
    check_if_migration_needed,
    create_default_class_if_needed,
    get_migration_files,
    init_database_with_migrations,
    run_migrations,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db():
    """Provide a temporary SQLite database path with cleanup."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    yield tmp.name
    try:
        os.remove(tmp.name)
    except OSError:
        pass


@pytest.fixture
def mini_migrations(tmp_path):
    """Create a minimal migrations directory with a simple SQL file."""
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()

    sql = (
        "CREATE TABLE IF NOT EXISTS classes (\n"
        "    id INTEGER PRIMARY KEY,\n"
        "    name TEXT NOT NULL,\n"
        "    grade_level TEXT,\n"
        "    subject TEXT,\n"
        "    standards TEXT,\n"
        "    config TEXT\n"
        ");\n"
        "CREATE TABLE IF NOT EXISTS questions (\n"
        "    id INTEGER PRIMARY KEY,\n"
        "    quiz_id INTEGER,\n"
        "    question_type TEXT,\n"
        "    sort_order INTEGER DEFAULT 0\n"
        ");\n"
        "CREATE TABLE IF NOT EXISTS study_sets (\n"
        "    id INTEGER PRIMARY KEY\n"
        ");\n"
        "CREATE TABLE IF NOT EXISTS rubrics (\n"
        "    id INTEGER PRIMARY KEY\n"
        ");\n"
        "CREATE TABLE IF NOT EXISTS performance_data (\n"
        "    id INTEGER PRIMARY KEY,\n"
        "    source TEXT DEFAULT 'manual_entry'\n"
        ");\n"
        "CREATE TABLE IF NOT EXISTS users (\n"
        "    id INTEGER PRIMARY KEY\n"
        ");\n"
        "CREATE TABLE IF NOT EXISTS standards (\n"
        "    id INTEGER PRIMARY KEY,\n"
        "    standard_set TEXT DEFAULT 'sol'\n"
        ");\n"
        "CREATE TABLE IF NOT EXISTS quizzes (\n"
        "    id INTEGER PRIMARY KEY,\n"
        "    class_id INTEGER\n"
        ");\n"
    )
    (mig_dir / "001_init.sql").write_text(sql)
    return str(mig_dir)


# ---------------------------------------------------------------------------
# get_migration_files
# ---------------------------------------------------------------------------


def test_get_migration_files_returns_sorted_list(mini_migrations):
    """Migration files are returned sorted by filename."""
    files = get_migration_files(mini_migrations)
    assert len(files) >= 1
    assert files[0][0] == "001_init.sql"


def test_get_migration_files_empty_for_missing_dir():
    """Returns empty list when migrations directory does not exist."""
    files = get_migration_files("nonexistent_dir_xyz")
    assert files == []


# ---------------------------------------------------------------------------
# check_if_migration_needed
# ---------------------------------------------------------------------------


def test_migration_needed_for_new_db(temp_db):
    """A brand new database always needs migration."""
    # Remove the file so it's truly new
    os.remove(temp_db)
    assert check_if_migration_needed(temp_db) is True


def test_migration_not_needed_after_full_run(temp_db, mini_migrations):
    """After running migrations, check_if_migration_needed returns False."""
    run_migrations(temp_db, mini_migrations, verbose=False)
    assert check_if_migration_needed(temp_db) is False


def test_migration_needed_when_table_missing(temp_db):
    """Migration is needed when expected tables are missing."""
    # Create a DB with only some tables
    conn = sqlite3.connect(temp_db)
    conn.execute("CREATE TABLE classes (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE questions (id INTEGER PRIMARY KEY, sort_order INTEGER)")
    conn.commit()
    conn.close()
    # Missing study_sets, rubrics, etc.
    assert check_if_migration_needed(temp_db) is True


# ---------------------------------------------------------------------------
# run_migrations
# ---------------------------------------------------------------------------


def test_run_migrations_creates_tables(temp_db, mini_migrations):
    """Running migrations creates the expected tables."""
    result = run_migrations(temp_db, mini_migrations, verbose=False)
    assert result is True

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "classes" in tables
    assert "questions" in tables
    assert "study_sets" in tables
    assert "users" in tables


def test_run_migrations_idempotent(temp_db, mini_migrations):
    """Running migrations twice does not error."""
    result1 = run_migrations(temp_db, mini_migrations, verbose=False)
    assert result1 is True

    # Second run should see no migration needed
    result2 = run_migrations(temp_db, mini_migrations, verbose=False)
    assert result2 is False


def test_run_migrations_no_files_returns_false(temp_db, tmp_path):
    """Returns False when no migration files are found."""
    empty_dir = tmp_path / "empty_mig"
    empty_dir.mkdir()
    result = run_migrations(temp_db, str(empty_dir), verbose=False)
    assert result is False


def test_run_migrations_handles_duplicate_column(temp_db, tmp_path):
    """Duplicate column errors are handled gracefully."""
    mig_dir = tmp_path / "dup_mig"
    mig_dir.mkdir()

    # First migration: create table
    (mig_dir / "001_create.sql").write_text("CREATE TABLE IF NOT EXISTS test_tbl (id INTEGER PRIMARY KEY, col1 TEXT);")
    # Second migration: add the same column (triggers duplicate column)
    (mig_dir / "002_dup.sql").write_text("ALTER TABLE test_tbl ADD COLUMN col1 TEXT;")

    # This needs to run on a DB that requires migration
    # Force migration needed by not having classes table
    result = run_migrations(temp_db, str(mig_dir), verbose=False)
    # Should not raise — duplicate column is caught
    assert result is True


# ---------------------------------------------------------------------------
# create_default_class_if_needed
# ---------------------------------------------------------------------------


def test_create_default_class_inserts_legacy(temp_db, mini_migrations):
    """Creates a Legacy Class with id=1 when none exists."""
    run_migrations(temp_db, mini_migrations, verbose=False)
    create_default_class_if_needed(temp_db)

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM classes WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert "Legacy" in row[0]


def test_create_default_class_idempotent(temp_db, mini_migrations):
    """Calling create_default_class twice does not duplicate the record."""
    run_migrations(temp_db, mini_migrations, verbose=False)
    create_default_class_if_needed(temp_db)
    create_default_class_if_needed(temp_db)

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM classes WHERE id = 1")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 1


def test_create_default_class_updates_null_class_ids(temp_db, mini_migrations):
    """Quizzes with NULL class_id are updated to class_id=1."""
    run_migrations(temp_db, mini_migrations, verbose=False)

    conn = sqlite3.connect(temp_db)
    conn.execute("INSERT INTO quizzes (id, class_id) VALUES (1, NULL)")
    conn.commit()
    conn.close()

    create_default_class_if_needed(temp_db)

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT class_id FROM quizzes WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row[0] == 1


# ---------------------------------------------------------------------------
# init_database_with_migrations
# ---------------------------------------------------------------------------


def test_init_database_full_workflow(temp_db, mini_migrations):
    """Full init creates tables and default class."""
    result = init_database_with_migrations(temp_db, mini_migrations)
    assert result is True

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM classes WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
