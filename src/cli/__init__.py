"""
CLI command modules for QuizWeaver.

Provides shared helpers and imports for all CLI command modules.
"""

import os

from src.database import get_engine, get_session, init_db


def get_db_session(config):
    """Helper to get a database engine and session.

    Uses DATABASE_URL environment variable if set (PostgreSQL support),
    otherwise falls back to the SQLite path in config.
    """
    database_url = os.environ.get("DATABASE_URL")
    engine = get_engine(url=database_url) if database_url else get_engine(config["paths"]["database_file"])
    init_db(engine)
    session = get_session(engine)
    return engine, session


def resolve_class_id(config, args, session):
    """Resolve class_id from --class flag, config, or default to 1."""
    class_id = getattr(args, "class_id", None)
    if class_id is not None:
        return int(class_id)

    active = config.get("active_class_id")
    if active is not None:
        return int(active)

    # Default to legacy class
    return 1
