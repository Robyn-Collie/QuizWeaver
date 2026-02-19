"""
Database migration runner for QuizWeaver.

Handles applying SQL migrations to upgrade the database schema.
Migrations are idempotent and safe to run multiple times.

For SQLite databases, raw SQL migration files in ``migrations/`` are
applied directly.  For PostgreSQL (or other non-SQLite databases), the
ORM's ``Base.metadata.create_all()`` handles schema creation and the
raw SQL files are skipped — they contain SQLite-specific syntax
(``AUTOINCREMENT``, ``PRAGMA``, etc.) that is incompatible with
PostgreSQL.
"""

import os
import sqlite3
from pathlib import Path


def detect_dialect(db_path=None):
    """Detect which database dialect is in use.

    Args:
        db_path: Path to a SQLite database file, or ``None`` when
            ``DATABASE_URL`` points to a non-SQLite database.

    Returns:
        ``'sqlite'`` or ``'postgresql'`` (or another dialect name
        inferred from ``DATABASE_URL``).
    """
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        if database_url.startswith("postgresql"):
            return "postgresql"
        if database_url.startswith("mysql"):
            return "mysql"
        if database_url.startswith("sqlite"):
            return "sqlite"
        # Unknown URL scheme — return the scheme portion
        return database_url.split("://")[0] if "://" in database_url else "unknown"
    # No DATABASE_URL → default is SQLite
    return "sqlite"


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

    This function only works for SQLite databases.  For PostgreSQL,
    migrations are handled by the ORM (``Base.metadata.create_all``).

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
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='classes'")
        classes_exists = cursor.fetchone() is not None

        if not classes_exists:
            conn.close()
            return True

        # Check if sort_order column exists on questions table
        # (if questions table doesn't exist yet, ORM will create it with the column)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='questions'")
        questions_exists = cursor.fetchone() is not None

        if questions_exists:
            cursor.execute("PRAGMA table_info(questions)")
            columns = [row[1] for row in cursor.fetchall()]
            sort_order_exists = "sort_order" in columns
        else:
            # Table will be created by ORM with sort_order column
            sort_order_exists = True

        # Check if study_sets table exists (migration 003)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='study_sets'")
        study_sets_exists = cursor.fetchone() is not None

        # Check if rubrics table exists (migration 004)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rubrics'")
        rubrics_exists = cursor.fetchone() is not None

        # Check if source column exists on performance_data (migration 005)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='performance_data'")
        perf_exists = cursor.fetchone() is not None

        perf_source_exists = True
        if perf_exists:
            cursor.execute("PRAGMA table_info(performance_data)")
            perf_columns = [row[1] for row in cursor.fetchall()]
            perf_source_exists = "source" in perf_columns

        # Check if users table exists (migration 006)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        users_exists = cursor.fetchone() is not None

        # Check if standards table exists (migration 007)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='standards'")
        standards_exists = cursor.fetchone() is not None

        # Check if standard_set column exists on standards (migration 009)
        standards_set_exists = True
        if standards_exists:
            cursor.execute("PRAGMA table_info(standards)")
            std_columns = [row[1] for row in cursor.fetchall()]
            standards_set_exists = "standard_set" in std_columns

        # Check if pacing_guides table exists (migration 011)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pacing_guides'")
        pacing_guides_exists = cursor.fetchone() is not None

        conn.close()

        return (
            not sort_order_exists
            or not study_sets_exists
            or not rubrics_exists
            or not perf_source_exists
            or not users_exists
            or not standards_exists
            or not standards_set_exists
            or not pacing_guides_exists
        )
    except Exception as e:
        print(f"Error checking migration status: {e}")
        return True


def run_migrations(db_path, migrations_dir="migrations", verbose=True):
    """
    Run all pending database migrations.

    For SQLite databases, raw SQL migration files are applied directly.
    For PostgreSQL (or other non-SQLite dialects detected via
    ``DATABASE_URL``), raw SQL migrations are skipped — the ORM's
    ``Base.metadata.create_all()`` handles schema creation instead.

    This function is idempotent — it's safe to run multiple times.
    Migrations use CREATE TABLE IF NOT EXISTS and INSERT ... ON CONFLICT.

    Args:
        db_path: Path to SQLite database file
        migrations_dir: Directory containing migration SQL files
        verbose: Whether to print progress messages

    Returns:
        True if migrations were applied, False if skipped or failed
    """
    dialect = detect_dialect(db_path)

    # For non-SQLite databases, skip raw SQL migrations.
    # Schema creation is handled by Base.metadata.create_all() in init_db().
    if dialect != "sqlite":
        if verbose:
            print(
                f"[OK] Database dialect is {dialect}; "
                "raw SQL migrations skipped (ORM handles schema)"
            )
        return False

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
        print("\n=== Running Database Migrations ===")
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
            with open(filepath) as f:
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
            print("\n[OK] All migrations applied successfully\n")

        return True

    except Exception as e:
        print(f"\n[FAIL] Migration failed: {e}")
        if "conn" in locals():
            conn.close()
        return False


def create_default_class_if_needed(db_path):
    """
    Create default "Legacy Class" for existing quizzes if needed.

    This is called after migrations to ensure backward compatibility.
    Only applies to SQLite databases; for PostgreSQL the ORM handles
    initial data seeding separately.

    Args:
        db_path: Path to SQLite database file
    """
    dialect = detect_dialect(db_path)
    if dialect != "sqlite":
        # For non-SQLite, use the ORM to create the default class
        _create_default_class_via_orm()
        return

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


def _create_default_class_via_orm():
    """Create the default Legacy Class using the ORM (for non-SQLite databases)."""
    try:
        from src.database import Class, Quiz, get_engine, get_session

        engine = get_engine()
        session = get_session(engine)

        # Check if legacy class exists
        existing = session.query(Class).filter_by(id=1).first()
        if existing is None:
            legacy = Class(
                id=1,
                name="Legacy Class (Pre-Platform Expansion)",
                grade_level="7th Grade",
                subject="Science",
                standards="[]",
                config="{}",
            )
            session.add(legacy)
            session.commit()

        # Update any null class_id references
        session.query(Quiz).filter(Quiz.class_id.is_(None)).update(
            {"class_id": 1}, synchronize_session="fetch"
        )
        session.commit()
        session.close()
        engine.dispose()
    except Exception as e:
        print(f"Warning: Could not create default class via ORM: {e}")


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
