"""Lead read schemas for the ranked queue. Expanded in later slices."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ContactSource, EmailConfidence, LeadStage, LeadStatus


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


class LeadDetail(LeadListItem):
    reject_overridden: bool
    notes: str | None
    created_at: datetime
    source_hits: list[SourceHitOut]
    research_brief: ResearchBriefOut | None = None
    contact: ContactOut | None = None
