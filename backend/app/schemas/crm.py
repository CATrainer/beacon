"""Slice 7 schemas: sending settings, suppression, activity, pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ActivityType, LeadStatus


class SendingSettingsOut(BaseModel):
    mode: str
    identity: str
    daily_cap: int
    window_start_hour: int
    window_end_hour: int
    min_spacing_seconds: int
    max_spacing_seconds: int


class SendingSettingsUpdate(BaseModel):
    mode: str | None = None
    identity: str | None = None
    daily_cap: int | None = None
    window_start_hour: int | None = None
    window_end_hour: int | None = None
    min_spacing_seconds: int | None = None
    max_spacing_seconds: int | None = None


class SendRequest(BaseModel):
    limit: int | None = None
    ignore_window: bool = False


class SuppressionOut(BaseModel):
    id: int
    email_or_domain: str
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SuppressionCreate(BaseModel):
    email_or_domain: str
    reason: str | None = None


class ActivityOut(BaseModel):
    id: int
    type: ActivityType
    detail: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class StatusUpdate(BaseModel):
    status: LeadStatus
    note: str | None = None


class GmailStatus(BaseModel):
    connected: bool
    configured: bool
    account_email: str | None = None


class PipelineOut(BaseModel):
    counts: dict[str, int]
