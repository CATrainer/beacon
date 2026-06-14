"""OAuth credentials and editable app settings (Slice 7)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.types import JSONB


class OAuthCredential(Base, TimestampMixin):
    """A stored OAuth credential (e.g. the Gmail sending account's tokens).

    Secrets live here (DB), never in logs. One row per provider for this 2-person
    tool. ``token_json`` holds the refresh/access token payload.
    """

    __tablename__ = "oauth_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    account_email: Mapped[str | None] = mapped_column(String(320))
    token_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class AppSetting(Base, TimestampMixin):
    """Operator-editable settings (sending mode, identity, caps, window).

    Defaults come from env (`app.config`); rows here override them so the operator
    can tune in the UI without a redeploy (§7 — sending identity is a setting).
    """

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
