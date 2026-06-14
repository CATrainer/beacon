"""Database engine, session factory, and FastAPI dependency.

Beacon uses synchronous SQLAlchemy 2.0 with psycopg3. Endpoints that touch the
DB are defined as plain `def` functions so FastAPI runs them in a threadpool —
simpler and more robust than async sessions for a small internal tool, with no
greenlet/async-session pitfalls.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
