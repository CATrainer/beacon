"""Pytest fixtures: in-memory SQLite DB, app override, authed client."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db import get_db
from app.main import app
from app.models import Base, User


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db(engine) -> Iterator[Session]:
    """A clean session per test; tables truncated between tests."""
    TestSession = sessionmaker(bind=engine, autoflush=False, future=True)
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        # wipe rows so each test starts clean
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


@pytest.fixture
def client(db) -> Iterator[TestClient]:
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def user(db) -> User:
    u = User(email="caleb@heuricity.com", name="Caleb", password_hash=hash_password("password123"))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def auth_headers(client, user) -> dict[str, str]:
    resp = client.post(
        "/api/auth/login",
        data={"username": user.email, "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
