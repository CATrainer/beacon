"""Job and source-run schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import JobStatus, JobType


class ManualEntry(BaseModel):
    company_name: str
    website: str | None = None
    location: str | None = None


class SourceRunRequest(BaseModel):
    #: Restrict to specific adapter keys; None = all enabled sources in the lane.
    source_keys: list[str] | None = None
    limit_per_source: int = Field(default=50, ge=1, le=1000)
    #: Force fixture data even when keys are present (handy for demos/tests).
    force_fixtures: bool = False
    #: For the manual_paste source.
    manual_entries: list[ManualEntry] | None = None


class ResearchRequest(BaseModel):
    #: Research the top-N leads by Stage-3 score (gating, §2). Ignored if lead_ids set.
    top_n: int | None = Field(default=None, ge=1, le=500)
    #: Research specific leads on-demand (e.g. operator opened/shortlisted them).
    lead_ids: list[int] | None = None


class CostEstimate(BaseModel):
    lead_count: int
    per_lead_usd: float
    estimated_usd: float


class JobOut(BaseModel):
    id: int
    type: JobType
    status: JobStatus
    lane_id: int | None
    progress: int
    total: int
    message: str | None
    result: dict
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}
