"""Portable column types.

``JSONB`` uses Postgres JSONB in production and falls back to generic JSON on
other dialects (e.g. SQLite in the test suite), so models stay DB-agnostic.
"""

from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

# Postgres-native JSONB where available; plain JSON elsewhere.
JSONB = JSON().with_variant(PG_JSONB(), "postgresql")
