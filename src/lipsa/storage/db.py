"""
Database engine, session factory, and connection configuration for LIPSA.

Key requirements from the approved design (Storage Schema + Security sections):
- SQLite with WAL journal mode for concurrent access (CLI + optional web UI)
- busy_timeout=5000
- check_same_thread=False when needed
- Connection pooling configured safely
- User data directory: ~/.lipsa/lipsa.db
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from lipsa.storage.models import Base


def get_database_path() -> Path:
    """Return the path to the main SQLite database file (~/.lipsa/lipsa.db)."""
    if os.name == "nt":
        base = Path(os.environ.get("USERPROFILE", Path.home()))
    else:
        base = Path.home()
    data_dir = base / ".lipsa"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "lipsa.db"


def get_database_url() -> str:
    """Return the SQLAlchemy database URL (always SQLite for v1)."""
    db_path = get_database_path()
    # Use absolute path with forward slashes for SQLAlchemy on all platforms
    return f"sqlite:///{db_path.as_posix()}"


# Global engine and session factory (configured once)
_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """
    Get (or create) the singleton SQLAlchemy engine with proper SQLite settings.

    Applies:
    - WAL mode
    - busy_timeout=5000
    - Foreign key enforcement
    """
    global _engine, _SessionLocal

    if _engine is not None:
        return _engine

    db_url = get_database_url()
    _engine = create_engine(
        db_url,
        connect_args={
            "check_same_thread": False,  # Required for SQLite + threading (web UI + CLI)
        },
        echo=False,
        future=True,
    )

    # Apply SQLite pragmas on every new connection
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    return _engine


def get_session() -> Session:
    """Get a new database session."""
    if _SessionLocal is None:
        get_engine()  # initialize
    assert _SessionLocal is not None
    return _SessionLocal()


def get_session_context() -> Iterator[Session]:
    """Context manager style session (for use in with statements)."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> Path:
    """
    Create all tables using the current metadata (used by `lipsa db init`).

    In production we prefer Alembic migrations. This function is useful for:
    - Very early development
    - Tests
    - Emergency "just make the DB exist" scenarios
    """
    engine = get_engine()
    Base.metadata.create_all(engine)
    return get_database_path()


def run_migrations() -> None:
    """
    Run Alembic migrations to head (the proper way after PR #2).

    This will be wired into the `lipsa db init` / upgrade commands.
    """
    from alembic.config import Config

    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


def get_db_info() -> dict:
    """Return basic info about the current database for diagnostics."""
    db_path = get_database_path()
    engine = get_engine()

    with engine.connect() as conn:
        wal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        busy_timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()

    return {
        "database_path": str(db_path),
        "exists": db_path.exists(),
        "size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "journal_mode": wal_mode,
        "busy_timeout": busy_timeout,
    }
