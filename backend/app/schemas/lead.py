"""Lead read schemas for the ranked queue. Expanded in later slices."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import (
    ContactSource,
    EmailConfidence,
    EmailStatus,
    GeoHookType,
    LeadStage,
    LeadStatus,
)


class LeadListItem(BaseModel):
    id: int
    lane_id: int
    company: str
    website: str | None
    domain: str | None
    location: str | None
    stage: LeadStage
    status: LeadStatus
    fit_score: float | None
    gap_score: float | None
    reachability_score: float | None
    final_score: float | None
    score_breakdown: dict
    reject_reason: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    items: list[LeadListItem]
    total: int
    limit: int
    offset: int


class SourceHitOut(BaseModel):
    id: int
    source_key: str
    source_ref: str | None
    raw_meta: dict
    fetched_at: datetime

    model_config = {"from_attributes": True}


class ResearchBriefOut(BaseModel):
    id: int
    summary: str | None
    specialisms: str | None
    high_ticket_services: list
    decision_maker_name: str | None
    decision_maker_role: str | None
    human_hook: str | None
    marketing_sophistication: str | None
    emails_found: list
    linkedin_url: str | None
    pages_fetched: list
    model_used: str | None
    cost_usd: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactOut(BaseModel):
    id: int
    email: str | None
    email_confidence: EmailConfidence | None
    source: ContactSource | None
    decision_maker_name: str | None
    linkedin_url: str | None
    is_primary: bool

    model_config = {"from_attributes": True}


class GeoCheckOut(BaseModel):
    id: int
    engine: str
    query: str
    prospect_named: bool
    prospect_recommended: bool
    competitors: list
    cited_sources: list
    hook_type: GeoHookType | None
    severity: float | None
    checked_at: datetime

    model_config = {"from_attributes": True}


class EvidenceOut(BaseModel):
    id: int
    query: str
    engine: str | None
    screenshot_path: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class EmailOut(BaseModel):
    id: int
    touch_no: int
    subject: str | None
    body: str | None
    status: EmailStatus
    scheduled_for: datetime | None
    sent_at: datetime | None
    gmail_thread_id: str | None
    gmail_draft_id: str | None

    model_config = {"from_attributes": True}


class EmailUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None


class AuditQueriesOut(BaseModel):
    queries: list[str]
    engines: list[str]


class LeadDetail(LeadListItem):
    reject_overridden: bool
    notes: str | None
    created_at: datetime
    source_hits: list[SourceHitOut]
    research_brief: ResearchBriefOut | None = None
    contact: ContactOut | None = None
    geo_checks: list[GeoCheckOut] = []
    evidence: list[EvidenceOut] = []
    emails: list[EmailOut] = []
