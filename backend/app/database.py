"""Database engine, session factory, and initialization helpers."""

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# Override with DATABASE_URL in .env for non-default setups.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# SQLite only supports one writer thread at a time; FastAPI can share sessions
# across threads, so disable the per-thread check.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def enable_sqlite_foreign_keys(target_engine) -> None:
    """Turn on foreign key enforcement for SQLite connections.

    SQLite ships with FK enforcement disabled by default; without this, orphaned
    rows would silently be allowed. This is a no-op for other database dialects.
    """
    if target_engine.dialect.name != "sqlite":
        return

    @event.listens_for(target_engine, "connect")
    def _set_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


enable_sqlite_foreign_keys(engine)


def init_db() -> None:
    """Create all tables if they do not exist."""
    # Import models so they register with Base.metadata before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
