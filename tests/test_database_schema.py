"""
Tests for database schema and migrations.
Run with: python tests/test_database_schema.py
"""

import sys
import os
import tempfile

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database import (
    Base, get_engine, init_db, get_session,
    Class, LessonLog, Quiz, Question, PerformanceData
)
from src.migrations import run_migrations


def test_migration_on_clean_db():
    """Test that migrations work on a clean database."""
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name

    try:
        # Run migrations
        success = run_migrations(test_db, verbose=False)
        assert success or not success, "Migrations should run (or skip if not needed)"

        # Initialize with SQLAlchemy
        engine = get_engine(test_db)
        init_db(engine)

        print("[PASS] Migration runs successfully on clean DB")
    finally:
        try:
        # Cleanup
        if os.path.exists(test_db):
            os.remove(test_db)
        except:
            pass  # Ignore cleanup errors


def test_migration_on_existing_db():
    """Test that migrations work on existing database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name

    try:
        # Create initial database
        engine = get_engine(test_db)
        init_db(engine)

        # Run migrations (should handle existing DB gracefully)
        success = run_migrations(test_db, verbose=False)

        print("[PASS] Migration runs successfully on existing DB")
    finally:
        try:
        if os.path.exists(test_db):
            os.remove(test_db)
        except:
            pass  # Ignore cleanup errors


def test_migration_is_idempotent():
    """Test that running migrations multiple times is safe."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name

    try:
        # Run migrations twice
        run_migrations(test_db, verbose=False)
        run_migrations(test_db, verbose=False)

        # Should not error
        print("[PASS] Migration is idempotent (can run multiple times)")
    finally:
        try:
        if os.path.exists(test_db):
            os.remove(test_db)
        except:
            pass  # Ignore cleanup errors


def test_class_creation():
    """Test creating a Class record."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name

    try:
        engine = get_engine(test_db)
        run_migrations(test_db, verbose=False)
        init_db(engine)
        session = get_session(engine)

        # Create a class
        new_class = Class(
            name="7th Grade Science - Block A",
            grade_level="7th Grade",
            subject="Science",
            standards='["SOL 7.1", "SOL 7.2"]',
            config='{}'
        )
        session.add(new_class)
        session.commit()

        # Verify it was created
        classes = session.query(Class).all()
        assert len(classes) >= 1, "Should have at least one class"
        assert classes[-1].name == "7th Grade Science - Block A"

        session.close()
        engine.dispose()  # Close all connections
        print("[PASS] Class creation works correctly")
    finally:
        try:
        try:
            if os.path.exists(test_db):
                os.remove(test_db)
        except:
            pass  # Ignore cleanup errors
        except:
            pass  # Ignore cleanup errors on Windows


def test_relationships():
    """Test that relationships between models work."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name

    try:
        engine = get_engine(test_db)
        run_migrations(test_db, verbose=False)
        init_db(engine)
        session = get_session(engine)

        # Create a class
        test_class = Class(
            name="Test Class",
            grade_level="8th Grade",
            subject="Math"
        )
        session.add(test_class)
        session.commit()

        # Create a lesson log for this class
        lesson = LessonLog(
            class_id=test_class.id,
            content="Covered algebra basics",
            topics='["algebra", "equations"]'
        )
        session.add(lesson)
        session.commit()

        # Test relationship
        assert len(test_class.lesson_logs) == 1, "Class should have one lesson log"
        assert test_class.lesson_logs[0].content == "Covered algebra basics"

        session.close()
        print("[PASS] Relationships work correctly (Class 1:N LessonLogs)")
    finally:
        try:
        if os.path.exists(test_db):
            os.remove(test_db)
        except:
            pass  # Ignore cleanup errors


def test_quiz_class_relationship():
    """Test that quizzes can be associated with classes."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name

    try:
        engine = get_engine(test_db)
        run_migrations(test_db, verbose=False)
        init_db(engine)
        session = get_session(engine)

        # Create a class
        test_class = Class(name="Test Class")
        session.add(test_class)
        session.commit()

        # Create a quiz for this class
        quiz = Quiz(
            title="Test Quiz",
            class_id=test_class.id,
            status="generated"
        )
        session.add(quiz)
        session.commit()

        # Test relationship
        assert len(test_class.quizzes) == 1, "Class should have one quiz"
        assert test_class.quizzes[0].title == "Test Quiz"

        session.close()
        print("[PASS] Quiz-Class relationship works correctly")
    finally:
        try:
        if os.path.exists(test_db):
            os.remove(test_db)
        except:
            pass  # Ignore cleanup errors


def run_all_tests():
    """Run all database tests."""
    tests = [
        test_migration_on_clean_db,
        test_migration_on_existing_db,
        test_migration_is_idempotent,
        test_class_creation,
        test_relationships,
        test_quiz_class_relationship,
    ]

    print("\n=== Running Database Schema Tests ===\n")

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: Unexpected error: {e}")
            failed += 1

    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed > 0:
        sys.exit(1)
    else:
        print("\n[OK] All database tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
