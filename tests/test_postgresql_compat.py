"""
Tests for PostgreSQL compatibility layer (GH #29).

Verifies that:
- get_engine() works with SQLite (default, backward-compatible)
- get_engine() works with DATABASE_URL environment variable
- get_engine() works with explicit url parameter
- JSON column types work across models
- Migration runner detects dialect correctly
- Connection pool settings differ by dialect
- Existing SQLite functionality is unchanged

All tests run WITHOUT a real PostgreSQL server -- PostgreSQL connections
are mocked where needed, and SQLite is used for actual data operations.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import inspect

from src.database import (
    Class,
    LessonPlan,
    Question,
    Quiz,
    Standard,
    StudyCard,
    StudySet,
    User,
    get_database_url,
    get_dialect,
    get_engine,
    get_session,
    init_db,
)
from src.migrations import detect_dialect as migration_detect_dialect
from src.migrations import run_migrations

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db():
    """Provide a temporary SQLite database path with cleanup."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    yield tmp.name
    try:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def clean_database_url_env():
    """Ensure DATABASE_URL is not set during tests unless explicitly set."""
    old_val = os.environ.pop("DATABASE_URL", None)
    yield
    if old_val is not None:
        os.environ["DATABASE_URL"] = old_val
    else:
        os.environ.pop("DATABASE_URL", None)


# ---------------------------------------------------------------------------
# get_engine() with SQLite (default behavior)
# ---------------------------------------------------------------------------


class TestGetEngineSQLiteDefault:
    """Verify get_engine() backward compatibility with SQLite."""

    def test_get_engine_with_db_path(self, tmp_db):
        """get_engine(db_path) returns a working SQLite engine."""
        engine = get_engine(tmp_db)
        assert engine is not None
        assert get_dialect(engine) == "sqlite"
        engine.dispose()

    def test_get_engine_creates_tables(self, tmp_db):
        """init_db() with SQLite engine creates all ORM tables."""
        engine = get_engine(tmp_db)
        init_db(engine)
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        expected = [
            "lessons",
            "assets",
            "classes",
            "lesson_logs",
            "quizzes",
            "questions",
            "study_sets",
            "study_cards",
            "feedback_logs",
            "rubrics",
            "rubric_criteria",
            "users",
            "standards",
            "performance_data",
            "lesson_plans",
        ]
        for table in expected:
            assert table in table_names, f"Table {table} not found"
        engine.dispose()

    def test_sqlite_is_default_when_no_database_url(self, tmp_db):
        """When DATABASE_URL is not set, get_engine uses SQLite."""
        assert os.environ.get("DATABASE_URL") is None
        engine = get_engine(tmp_db)
        assert get_dialect(engine) == "sqlite"
        engine.dispose()

    def test_get_engine_backward_compat_positional_arg(self, tmp_db):
        """get_engine(db_path) works as positional arg (backward compat)."""
        engine = get_engine(tmp_db)
        assert engine is not None
        # Verify we can actually use it
        init_db(engine)
        session = get_session(engine)
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# get_engine() with DATABASE_URL
# ---------------------------------------------------------------------------


class TestGetEngineWithDatabaseURL:
    """Verify get_engine() respects DATABASE_URL environment variable."""

    def test_database_url_env_takes_precedence(self, tmp_db):
        """DATABASE_URL env var overrides db_path for URL resolution."""
        # Use a SQLite URL so we can test without PostgreSQL
        sqlite_url = f"sqlite:///{tmp_db}"
        os.environ["DATABASE_URL"] = sqlite_url
        url = get_database_url(db_path="other.db")
        assert url == sqlite_url

    def test_get_engine_with_sqlite_database_url(self, tmp_db):
        """get_engine() works with SQLite DATABASE_URL."""
        sqlite_url = f"sqlite:///{tmp_db}"
        os.environ["DATABASE_URL"] = sqlite_url
        engine = get_engine()
        assert get_dialect(engine) == "sqlite"
        engine.dispose()

    def test_get_engine_with_explicit_url_param(self, tmp_db):
        """Explicit url parameter overrides everything."""
        sqlite_url = f"sqlite:///{tmp_db}"
        engine = get_engine(url=sqlite_url)
        assert engine is not None
        assert get_dialect(engine) == "sqlite"
        engine.dispose()

    def test_explicit_url_overrides_database_url_env(self, tmp_db):
        """Explicit url param takes precedence over DATABASE_URL env."""
        os.environ["DATABASE_URL"] = "sqlite:///should_not_use.db"
        explicit_url = f"sqlite:///{tmp_db}"
        url = get_database_url(db_path="also_not_used.db", url=explicit_url)
        assert url == explicit_url

    def test_get_database_url_raises_without_any_config(self):
        """get_database_url() raises ValueError with no arguments."""
        assert os.environ.get("DATABASE_URL") is None
        with pytest.raises(ValueError, match="No database connection configured"):
            get_database_url()


# ---------------------------------------------------------------------------
# PostgreSQL engine creation (mocked -- no real PG server)
# ---------------------------------------------------------------------------


class TestPostgreSQLEngine:
    """Test PostgreSQL-specific engine configuration (mocked)."""

    @patch("src.database.create_engine")
    def test_postgresql_url_enables_pool(self, mock_create_engine):
        """PostgreSQL URL triggers connection pooling parameters."""
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_create_engine.return_value = mock_engine

        pg_url = "postgresql://user:pass@localhost:5432/quizweaver"
        engine = get_engine(url=pg_url)

        mock_create_engine.assert_called_once_with(
            pg_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        assert engine is mock_engine

    @patch("src.database.create_engine")
    def test_sqlite_url_no_pool_params(self, mock_create_engine, tmp_db):
        """SQLite engine does NOT get pool_size/max_overflow kwargs."""
        mock_engine = MagicMock()
        mock_engine.dialect.name = "sqlite"
        mock_create_engine.return_value = mock_engine

        sqlite_url = f"sqlite:///{tmp_db}"
        get_engine(url=sqlite_url)

        mock_create_engine.assert_called_once_with(sqlite_url)

    @patch("src.database.create_engine")
    def test_postgresql_missing_psycopg2_gives_helpful_error(self, mock_create_engine):
        """When psycopg2 is not installed, error message is helpful."""
        mock_create_engine.side_effect = Exception(
            "No module named 'psycopg2'"
        )
        with pytest.raises(ImportError, match="pip install psycopg2-binary"):
            get_engine(url="postgresql://user:pass@localhost/db")

    @patch("src.database.create_engine")
    def test_postgresql_other_error_not_swallowed(self, mock_create_engine):
        """Non-psycopg2 errors for PostgreSQL are re-raised as-is."""
        mock_create_engine.side_effect = RuntimeError("connection refused")
        with pytest.raises(RuntimeError, match="connection refused"):
            get_engine(url="postgresql://user:pass@localhost/db")


# ---------------------------------------------------------------------------
# get_dialect() helper
# ---------------------------------------------------------------------------


class TestGetDialect:
    """Test the get_dialect() helper function."""

    def test_sqlite_dialect(self, tmp_db):
        """SQLite engine returns 'sqlite' dialect."""
        engine = get_engine(tmp_db)
        assert get_dialect(engine) == "sqlite"
        engine.dispose()

    @patch("src.database.create_engine")
    def test_postgresql_dialect(self, mock_create_engine):
        """PostgreSQL engine returns 'postgresql' dialect."""
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_create_engine.return_value = mock_engine

        engine = get_engine(url="postgresql://user:pass@localhost/db")
        assert get_dialect(engine) == "postgresql"


# ---------------------------------------------------------------------------
# Migration dialect detection
# ---------------------------------------------------------------------------


class TestMigrationDialectDetection:
    """Test migration runner dialect detection."""

    def test_detect_sqlite_by_default(self):
        """Without DATABASE_URL, dialect is sqlite."""
        assert os.environ.get("DATABASE_URL") is None
        assert migration_detect_dialect() == "sqlite"

    def test_detect_postgresql_from_env(self):
        """DATABASE_URL starting with 'postgresql' returns 'postgresql'."""
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
        assert migration_detect_dialect() == "postgresql"

    def test_detect_mysql_from_env(self):
        """DATABASE_URL starting with 'mysql' returns 'mysql'."""
        os.environ["DATABASE_URL"] = "mysql://user:pass@localhost/db"
        assert migration_detect_dialect() == "mysql"

    def test_detect_sqlite_url_from_env(self):
        """DATABASE_URL starting with 'sqlite' returns 'sqlite'."""
        os.environ["DATABASE_URL"] = "sqlite:///test.db"
        assert migration_detect_dialect() == "sqlite"

    def test_run_migrations_skips_for_postgresql(self, tmp_db):
        """run_migrations() skips raw SQL for non-SQLite dialects."""
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
        result = run_migrations(tmp_db, verbose=False)
        assert result is False  # Skipped, not applied

    def test_run_migrations_works_for_sqlite(self, tmp_db):
        """run_migrations() applies raw SQL for SQLite dialect."""
        assert os.environ.get("DATABASE_URL") is None
        result = run_migrations(tmp_db, verbose=False)
        # On a fresh DB, migrations should be applied (True)
        assert result is True


# ---------------------------------------------------------------------------
# JSON column compatibility
# ---------------------------------------------------------------------------


class TestJSONColumnCompatibility:
    """Test that JSON columns work correctly (critical for PG compatibility)."""

    def test_create_class_with_json_fields(self, tmp_db):
        """Class model stores and retrieves JSON in standards/config."""
        engine = get_engine(tmp_db)
        init_db(engine)
        session = get_session(engine)

        standards = ["SOL 7.1", "SOL 7.2", "SOL 7.3"]
        config = {"assumed_knowledge": {"photosynthesis": 3}}

        cls = Class(
            name="JSON Test Class",
            grade_level="7th Grade",
            subject="Science",
            standards=json.dumps(standards),
            config=json.dumps(config),
        )
        session.add(cls)
        session.commit()

        # Re-query to verify round-trip
        loaded = session.query(Class).filter_by(name="JSON Test Class").first()
        assert loaded is not None

        loaded_standards = (
            json.loads(loaded.standards)
            if isinstance(loaded.standards, str)
            else loaded.standards
        )
        loaded_config = (
            json.loads(loaded.config)
            if isinstance(loaded.config, str)
            else loaded.config
        )
        assert loaded_standards == standards
        assert loaded_config == config

        session.close()
        engine.dispose()

    def test_quiz_style_profile_json(self, tmp_db):
        """Quiz.style_profile stores and retrieves JSON correctly."""
        engine = get_engine(tmp_db)
        init_db(engine)
        session = get_session(engine)

        cls = Class(name="Test", grade_level="7th", subject="Sci")
        session.add(cls)
        session.commit()

        profile = {"grade_level": "7th Grade", "image_ratio": 0.3, "provider": "mock"}
        quiz = Quiz(
            title="JSON Test Quiz",
            class_id=cls.id,
            status="generated",
            style_profile=json.dumps(profile),
        )
        session.add(quiz)
        session.commit()

        loaded = session.query(Quiz).filter_by(title="JSON Test Quiz").first()
        loaded_profile = (
            json.loads(loaded.style_profile)
            if isinstance(loaded.style_profile, str)
            else loaded.style_profile
        )
        assert loaded_profile == profile

        session.close()
        engine.dispose()

    def test_question_data_json(self, tmp_db):
        """Question.data stores and retrieves JSON correctly."""
        engine = get_engine(tmp_db)
        init_db(engine)
        session = get_session(engine)

        cls = Class(name="Test", grade_level="7th", subject="Sci")
        session.add(cls)
        session.commit()

        quiz = Quiz(title="Q Test", class_id=cls.id, status="generated")
        session.add(quiz)
        session.commit()

        q_data = {
            "type": "mc",
            "text": "What is H2O?",
            "options": ["Water", "Oxygen", "Hydrogen", "Carbon"],
            "correct_index": 0,
        }
        question = Question(
            quiz_id=quiz.id,
            question_type="mc",
            text="What is H2O?",
            points=5.0,
            data=json.dumps(q_data),
        )
        session.add(question)
        session.commit()

        loaded = session.query(Question).first()
        loaded_data = (
            json.loads(loaded.data)
            if isinstance(loaded.data, str)
            else loaded.data
        )
        assert loaded_data["correct_index"] == 0
        assert loaded_data["options"][0] == "Water"

        session.close()
        engine.dispose()

    def test_update_json_field(self, tmp_db):
        """JSON fields can be updated after initial creation."""
        engine = get_engine(tmp_db)
        init_db(engine)
        session = get_session(engine)

        cls = Class(
            name="Update Test",
            grade_level="8th",
            subject="Math",
            standards=json.dumps(["CCSS.MATH.1"]),
            config=json.dumps({}),
        )
        session.add(cls)
        session.commit()

        # Update
        cls.standards = json.dumps(["CCSS.MATH.1", "CCSS.MATH.2"])
        cls.config = json.dumps({"theme": "dark"})
        session.commit()

        loaded = session.query(Class).filter_by(name="Update Test").first()
        loaded_standards = (
            json.loads(loaded.standards)
            if isinstance(loaded.standards, str)
            else loaded.standards
        )
        assert len(loaded_standards) == 2
        assert "CCSS.MATH.2" in loaded_standards

        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# All model definitions work
# ---------------------------------------------------------------------------


class TestAllModelDefinitions:
    """Verify every ORM model can be instantiated, saved, and queried."""

    def test_all_tables_created(self, tmp_db):
        """All models produce tables via create_all."""
        engine = get_engine(tmp_db)
        init_db(engine)
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        expected_tables = [
            "lessons",
            "assets",
            "classes",
            "lesson_logs",
            "quizzes",
            "questions",
            "study_sets",
            "study_cards",
            "feedback_logs",
            "rubrics",
            "rubric_criteria",
            "users",
            "standards",
            "performance_data",
            "lesson_plans",
        ]
        for t in expected_tables:
            assert t in tables, f"Missing table: {t}"
        engine.dispose()

    def test_create_and_query_user(self, tmp_db):
        """User model works for create and query."""
        engine = get_engine(tmp_db)
        init_db(engine)
        session = get_session(engine)

        user = User(
            username="test_teacher",
            password_hash="hashed_pw",
            display_name="Test Teacher",
            role="teacher",
        )
        session.add(user)
        session.commit()

        loaded = session.query(User).filter_by(username="test_teacher").first()
        assert loaded is not None
        assert loaded.display_name == "Test Teacher"

        session.close()
        engine.dispose()

    def test_create_and_query_standard(self, tmp_db):
        """Standard model works for create and query."""
        engine = get_engine(tmp_db)
        init_db(engine)
        session = get_session(engine)

        std = Standard(
            code="SOL 7.1",
            description="Life processes",
            subject="Science",
            grade_band="6-8",
            standard_set="sol",
        )
        session.add(std)
        session.commit()

        loaded = session.query(Standard).filter_by(code="SOL 7.1").first()
        assert loaded is not None
        assert loaded.standard_set == "sol"

        session.close()
        engine.dispose()

    def test_create_and_query_lesson_plan(self, tmp_db):
        """LessonPlan model works for create and query."""
        engine = get_engine(tmp_db)
        init_db(engine)
        session = get_session(engine)

        cls = Class(name="LP Test", grade_level="7th", subject="Science")
        session.add(cls)
        session.commit()

        plan = LessonPlan(
            class_id=cls.id,
            title="Photosynthesis Lesson",
            topics=json.dumps(["photosynthesis", "chloroplast"]),
            plan_data=json.dumps({"sections": []}),
            status="draft",
        )
        session.add(plan)
        session.commit()

        loaded = session.query(LessonPlan).first()
        assert loaded.title == "Photosynthesis Lesson"

        session.close()
        engine.dispose()

    def test_study_set_with_cards(self, tmp_db):
        """StudySet + StudyCard cascade works."""
        engine = get_engine(tmp_db)
        init_db(engine)
        session = get_session(engine)

        cls = Class(name="Study Test", grade_level="7th", subject="Science")
        session.add(cls)
        session.commit()

        ss = StudySet(
            class_id=cls.id,
            title="Vocab Set",
            material_type="vocabulary",
            status="generated",
        )
        session.add(ss)
        session.commit()

        card = StudyCard(
            study_set_id=ss.id,
            card_type="term",
            front="Photosynthesis",
            back="Process of converting light to energy",
        )
        session.add(card)
        session.commit()

        loaded = session.query(StudySet).first()
        assert len(loaded.cards) == 1
        assert loaded.cards[0].front == "Photosynthesis"

        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# get_database_url() resolution logic
# ---------------------------------------------------------------------------


class TestGetDatabaseURL:
    """Test the URL resolution priority in get_database_url()."""

    def test_explicit_url_first(self):
        """Explicit url parameter has highest priority."""
        os.environ["DATABASE_URL"] = "postgresql://env/db"
        result = get_database_url(db_path="fallback.db", url="postgresql://explicit/db")
        assert result == "postgresql://explicit/db"

    def test_env_url_second(self):
        """DATABASE_URL env var is second priority."""
        os.environ["DATABASE_URL"] = "postgresql://env/db"
        result = get_database_url(db_path="fallback.db")
        assert result == "postgresql://env/db"

    def test_db_path_third(self):
        """db_path is lowest priority fallback."""
        result = get_database_url(db_path="my.db")
        assert result == "sqlite:///my.db"

    def test_no_args_raises(self):
        """No arguments and no env var raises ValueError."""
        with pytest.raises(ValueError):
            get_database_url()


# ---------------------------------------------------------------------------
# Web app integration (DATABASE_URL in create_app)
# ---------------------------------------------------------------------------


class TestWebAppDatabaseURL:
    """Test that the Flask app respects DATABASE_URL."""

    def test_create_app_with_sqlite_default(self, tmp_db):
        """create_app() uses SQLite when DATABASE_URL is not set."""
        from src.web.app import create_app

        config = {
            "paths": {"database_file": tmp_db},
            "llm": {"provider": "mock"},
            "generation": {
                "default_grade_level": "7th Grade",
                "quiz_title": "Test",
                "sol_standards": [],
            },
        }
        app = create_app(config)
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        engine = app.config["DB_ENGINE"]
        assert get_dialect(engine) == "sqlite"
        engine.dispose()

    def test_create_app_with_sqlite_database_url(self, tmp_db):
        """create_app() uses DATABASE_URL when set (SQLite URL for test)."""
        from src.web.app import create_app

        os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db}"
        config = {
            "paths": {"database_file": "should_not_use.db"},
            "llm": {"provider": "mock"},
            "generation": {
                "default_grade_level": "7th Grade",
                "quiz_title": "Test",
                "sol_standards": [],
            },
        }
        app = create_app(config)
        app.config["TESTING"] = True

        engine = app.config["DB_ENGINE"]
        assert get_dialect(engine) == "sqlite"
        engine.dispose()


# ---------------------------------------------------------------------------
# CLI integration (DATABASE_URL in _get_db_session)
# ---------------------------------------------------------------------------


class TestCLIDatabaseURL:
    """Test CLI helpers respect DATABASE_URL."""

    def test_cli_get_db_session_sqlite_default(self, tmp_db):
        """CLI get_db_session uses SQLite when no DATABASE_URL."""
        from src.cli import get_db_session

        config = {"paths": {"database_file": tmp_db}}
        engine, session = get_db_session(config)
        assert get_dialect(engine) == "sqlite"
        session.close()
        engine.dispose()

    def test_cli_get_db_session_database_url(self, tmp_db):
        """CLI get_db_session uses DATABASE_URL when set."""
        from src.cli import get_db_session

        os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db}"
        config = {"paths": {"database_file": "should_not_use.db"}}
        engine, session = get_db_session(config)
        assert get_dialect(engine) == "sqlite"
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Connection pool settings differ by dialect
# ---------------------------------------------------------------------------


class TestConnectionPoolSettings:
    """Verify pool configuration differs between SQLite and PostgreSQL."""

    def test_sqlite_no_pool_size(self, tmp_db):
        """SQLite engine uses default pool (no explicit pool_size)."""
        engine = get_engine(tmp_db)
        # SQLite uses StaticPool or NullPool by default, not QueuePool
        # Just verify it works and is sqlite
        assert get_dialect(engine) == "sqlite"
        engine.dispose()

    @patch("src.database.create_engine")
    def test_postgresql_has_pool_size(self, mock_create_engine):
        """PostgreSQL engine is created with pool_size=5."""
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_create_engine.return_value = mock_engine

        get_engine(url="postgresql://user:pass@localhost/db")

        call_kwargs = mock_create_engine.call_args[1]
        assert call_kwargs["pool_size"] == 5
        assert call_kwargs["max_overflow"] == 10
        assert call_kwargs["pool_pre_ping"] is True

    @patch("src.database.create_engine")
    def test_postgresql_pool_pre_ping_enabled(self, mock_create_engine):
        """PostgreSQL engine has pool_pre_ping=True for connection health."""
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_create_engine.return_value = mock_engine

        get_engine(url="postgresql://user:pass@localhost/db")

        call_kwargs = mock_create_engine.call_args[1]
        assert call_kwargs["pool_pre_ping"] is True
