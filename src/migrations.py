"""
Database migration runner for QuizWeaver.

Handles applying SQL migrations to upgrade the database schema.
Migrations are idempotent and safe to run multiple times.
"""

import os
import sqlite3
from pathlib import Path


def get_migration_files(migrations_dir="migrations"):
    """
    Get list of migration SQL files in order.

    Args:
        migrations_dir: Directory containing migration files

    Returns:
        List of (filename, filepath) tuples sorted by name
    """
    migrations_path = Path(migrations_dir)
    if not migrations_path.exists():
        return []

    sql_files = sorted(migrations_path.glob("*.sql"))
    return [(f.name, str(f)) for f in sql_files]


def check_if_migration_needed(db_path):
    """
    Check if database needs migration by testing for new tables/columns.

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if migration needed, False otherwise
    """
    if not os.path.exists(db_path):
        # New database, migrations will be needed
        return True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if classes table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='classes'"
        )
        classes_exists = cursor.fetchone() is not None

        if not classes_exists:
            conn.close()
            return True

        # Check if sort_order column exists on questions table
        # (if questions table doesn't exist yet, ORM will create it with the column)
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='questions'"
        )
        questions_exists = cursor.fetchone() is not None

        if questions_exists:
            cursor.execute("PRAGMA table_info(questions)")
            columns = [row[1] for row in cursor.fetchall()]
            sort_order_exists = "sort_order" in columns
        else:
            # Table will be created by ORM with sort_order column
            sort_order_exists = True

        # Check if study_sets table exists (migration 003)
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='study_sets'"
        )
        study_sets_exists = cursor.fetchone() is not None

        # Check if rubrics table exists (migration 004)
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rubrics'"
        )
        rubrics_exists = cursor.fetchone() is not None

        conn.close()

        return not sort_order_exists or not study_sets_exists or not rubrics_exists
    except Exception as e:
        print(f"Error checking migration status: {e}")
        return True


def run_migrations(db_path, migrations_dir="migrations", verbose=True):
    """
    Run all pending database migrations.

    This function is idempotent - it's safe to run multiple times.
    Migrations use CREATE TABLE IF NOT EXISTS and INSERT ... ON CONFLICT.

    Args:
        db_path: Path to SQLite database file
        migrations_dir: Directory containing migration SQL files
        verbose: Whether to print progress messages

    Returns:
        True if migrations were applied, False if skipped or failed
    """
    if not check_if_migration_needed(db_path):
        if verbose:
            print("[OK] Database schema is up to date, no migrations needed")
        return False

    migration_files = get_migration_files(migrations_dir)
    if not migration_files:
        if verbose:
            print("[OK] No migration files found, skipping")
        return False

    if verbose:
        print(f"\n=== Running Database Migrations ===")
        print(f"Database: {db_path}")
        print(f"Migrations: {len(migration_files)} file(s)\n")

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign keys
        cursor = conn.cursor()

        for filename, filepath in migration_files:
            if verbose:
                print(f"Applying: {filename}...", end=" ")

            # Read migration SQL
            with open(filepath, 'r') as f:
                migration_sql = f.read()

            # Execute migration (may contain multiple statements)
            try:
                cursor.executescript(migration_sql)
                if verbose:
                    print("[OK]")
            except sqlite3.OperationalError as e:
                err_msg = str(e).lower()
                # Safe to ignore: column already exists or table not yet created by ORM
                if "duplicate column name" in err_msg:
                    if verbose:
                        print("[OK] (already applied)")
                elif "no such table" in err_msg:
                    if verbose:
                        print("[OK] (table managed by ORM)")
                else:
                    raise

        conn.commit()
        conn.close()

        if verbose:
            print(f"\n[OK] All migrations applied successfully\n")

        return True

    except Exception as e:
        print(f"\n[FAIL] Migration failed: {e}")
        if 'conn' in locals():
            conn.close()
        return False


def create_default_class_if_needed(db_path):
    """
    Create default "Legacy Class" for existing quizzes if needed.

    This is called after migrations to ensure backward compatibility.

    Args:
        db_path: Path to SQLite database file
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if legacy class exists
        cursor.execute("SELECT id FROM classes WHERE id = 1")
        if cursor.fetchone() is None:
            # Create legacy class
            cursor.execute(
                """
                INSERT INTO classes (id, name, grade_level, subject, standards, config)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "Legacy Class (Pre-Platform Expansion)",
                    "7th Grade",
                    "Science",
                    "[]",
                    "{}",
                ),
            )

        # Update any null class_id references
        cursor.execute("UPDATE quizzes SET class_id = 1 WHERE class_id IS NULL")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Warning: Could not create default class: {e}")


def init_database_with_migrations(db_path, migrations_dir="migrations"):
    """
    Initialize database and run migrations if needed.

    This is the main entry point to be called on application startup.

    Args:
        db_path: Path to SQLite database file
        migrations_dir: Directory containing migration SQL files

    Returns:
        True if database is ready, False on failure
    """
    try:
        # Run migrations
        migrations_applied = run_migrations(db_path, migrations_dir, verbose=True)

        # Ensure default class exists for backward compatibility
        if migrations_applied:
            create_default_class_if_needed(db_path)

        return True
    except Exception as e:
        print(f"[FAIL] Database initialization failed: {e}")
        return False


if __name__ == "__main__":
    # Test the migration system
    import sys

    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "quiz_warehouse.db"

    print(f"Testing migrations on: {db_path}")
    success = init_database_with_migrations(db_path)
    sys.exit(0 if success else 1)
