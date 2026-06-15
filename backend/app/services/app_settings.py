"""Operator-editable settings, backed by the ``app_settings`` table.

Defaults come from env (`app.config`); a single ``sending`` row overrides them so
the operator can tune sending mode / identity / caps / window in the UI without a
redeploy (§7).
"""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.integration import AppSetting

_SENDING_KEY = "sending"
_SOURCING_KEY = "sourcing"


class SendingSettings(BaseModel):
    mode: str = settings.sending_mode
    identity: str = settings.sending_identity
    daily_cap: int = settings.send_daily_cap
    window_start_hour: int = settings.send_window_start_hour
    window_end_hour: int = settings.send_window_end_hour
    min_spacing_seconds: int = settings.send_min_spacing_seconds
    max_spacing_seconds: int = settings.send_max_spacing_seconds


class SourcingSettings(BaseModel):
    enabled: bool = settings.scheduled_sourcing_enabled
    hour: int = settings.scheduled_sourcing_hour
    limit: int = settings.scheduled_sourcing_limit


def get_sourcing_settings(db: Session) -> SourcingSettings:
    row = db.scalar(select(AppSetting).where(AppSetting.key == _SOURCING_KEY))
    if row and row.value:
        return SourcingSettings(**{**SourcingSettings().model_dump(), **row.value})
    return SourcingSettings()


def update_sourcing_settings(db: Session, patch: dict) -> SourcingSettings:
    current = get_sourcing_settings(db).model_dump()
    merged = {**current, **{k: v for k, v in patch.items() if v is not None}}
    validated = SourcingSettings(**merged)
    row = db.scalar(select(AppSetting).where(AppSetting.key == _SOURCING_KEY))
    if row is None:
        row = AppSetting(key=_SOURCING_KEY, value=validated.model_dump())
        db.add(row)
    else:
        row.value = validated.model_dump()
    db.commit()
    return validated


def get_sending_settings(db: Session) -> SendingSettings:
    row = db.scalar(select(AppSetting).where(AppSetting.key == _SENDING_KEY))
    if row and row.value:
        return SendingSettings(**{**SendingSettings().model_dump(), **row.value})
    return SendingSettings()


def update_sending_settings(db: Session, patch: dict) -> SendingSettings:
    current = get_sending_settings(db).model_dump()
    merged = {**current, **{k: v for k, v in patch.items() if v is not None}}
    validated = SendingSettings(**merged)
    row = db.scalar(select(AppSetting).where(AppSetting.key == _SENDING_KEY))
    if row is None:
        row = AppSetting(key=_SENDING_KEY, value=validated.model_dump())
        db.add(row)
    else:
        row.value = validated.model_dump()
    db.commit()
    return validated
