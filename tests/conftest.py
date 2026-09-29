"""Shared pytest fixtures.

Makes the backend package importable and provides an isolated in-memory
SQLite database (with foreign key enforcement enabled) per test.
"""

import os
import sys

# Allow `import app.*` when running pytest from the repository root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, enable_sqlite_foreign_keys


@pytest.fixture()
def db_session():
    """A fresh session against an in-memory SQLite database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(monkeypatch):
    """A FastAPI TestClient backed by an isolated in-memory database.

    The development fallback planner is enabled so generate-plan works
    deterministically without an LLM API key.
    """
    from fastapi.testclient import TestClient

    from app.database import Base, get_db
    from app.main import app

    monkeypatch.setenv("AI_USE_FALLBACK", "1")
    monkeypatch.delenv("AI_LLM_API_KEY", raising=False)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
