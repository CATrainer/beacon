"""Lane model — a configurable target segment.

A Lane is *data, not code* (§3): its sources, Stage-2 qualification rules,
Stage-3 scoring weights, GEO query template and town list all live in the
``config`` JSONB blob, editable in the UI. The shape of ``config`` is validated
by ``app.schemas.lane.LaneConfig``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.types import JSONB


class Lane(Base, TimestampMixin):
    __tablename__ = "lanes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    leads: Mapped[list[Lead]] = relationship(  # noqa: F821
        back_populates="lane", cascade="all, delete-orphan"
    )
