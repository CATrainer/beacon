"""Trigger source runs and list available adapters."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters import list_adapters
from app.config import settings
from app.core.deps import get_current_user
from app.db import get_db
from app.models.enums import JobStatus, JobType, LeadStage
from app.models.job import Job
from app.models.lane import Lane
from app.models.lead import Lead
from app.queue import enqueue
from app.schemas.job import (
    CostEstimate,
    GeoRequest,
    JobOut,
    ResearchRequest,
    SourceRunRequest,
)
from app.services.geo import GEO_DISCLAIMER, execute_geo_job, select_geo_targets
from app.services.geo import PER_LEAD_ESTIMATE_USD as GEO_PER_LEAD_USD
from app.services.research import (
    PER_LEAD_ESTIMATE_USD,
    execute_research_job,
    select_research_targets,
)
from app.services.scoring import execute_score_job
from app.services.sourcing import execute_source_job

router = APIRouter(tags=["sourcing"], dependencies=[Depends(get_current_user)])


@router.get("/adapters")
def adapters() -> list[dict]:
    """List registered source adapters and whether each can run live right now."""
    out = []
    for a in list_adapters():
        # available() may depend on params; report the no-params (key-only) view.
        try:
            live = a.available({})
        except Exception:  # noqa: BLE001
            live = False
        out.append({"key": a.key, "description": a.description, "live": live})
    return out


@router.post(
    "/lanes/{lane_id}/source", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED
)
async def run_source(
    lane_id: int,
    payload: SourceRunRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobOut:
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lane not found")

    job = Job(
        type=JobType.SOURCE_RUN,
        lane_id=lane_id,
        status=JobStatus.QUEUED,
        params={
            "source_keys": payload.source_keys,
            "limit_per_source": payload.limit_per_source,
            "force_fixtures": payload.force_fixtures,
            "manual_entries": [e.model_dump() for e in payload.manual_entries]
            if payload.manual_entries
            else None,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    queued = await enqueue("run_source_job", job.id)
    if not queued:
        # Redis/worker unavailable — run in the API process's threadpool instead.
        background.add_task(execute_source_job, job.id)

    return JobOut.model_validate(job)


@router.post(
    "/lanes/{lane_id}/rescore", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED
)
async def rescore(
    lane_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobOut:
    """Re-score every non-rejected lead in the lane (after tuning weights, §5)."""
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lane not found")
    job = Job(type=JobType.SCORE, lane_id=lane_id, status=JobStatus.QUEUED, params={})
    db.add(job)
    db.commit()
    db.refresh(job)
    queued = await enqueue("run_score_job", job.id)
    if not queued:
        background.add_task(execute_score_job, job.id)
    return JobOut.model_validate(job)


@router.get("/lanes/{lane_id}/research/estimate", response_model=CostEstimate)
def research_estimate(
    lane_id: int,
    top_n: int | None = None,
    db: Session = Depends(get_db),
) -> CostEstimate:
    """Pre-run cost estimate for Stage-4 research (§9)."""
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lane not found")
    n = top_n or settings.research_top_n_default
    count = len(select_research_targets(db, lane_id, n))
    return CostEstimate(
        lead_count=count,
        per_lead_usd=PER_LEAD_ESTIMATE_USD,
        estimated_usd=round(count * PER_LEAD_ESTIMATE_USD, 2),
    )


@router.post(
    "/lanes/{lane_id}/research", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED
)
async def run_research(
    lane_id: int,
    payload: ResearchRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobOut:
    """Stage-4a research — gated to top-N or specific leads (§2/§4a)."""
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lane not found")
    if payload.lead_ids:
        # Guard against researching rejected leads by id.
        valid = db.query(Lead.id).filter(
            Lead.id.in_(payload.lead_ids),
            Lead.lane_id == lane_id,
            Lead.stage != LeadStage.REJECTED,
        ).all()
        params = {"lead_ids": [r[0] for r in valid]}
    else:
        params = {"top_n": payload.top_n or settings.research_top_n_default}

    job = Job(type=JobType.RESEARCH, lane_id=lane_id, status=JobStatus.QUEUED, params=params)
    db.add(job)
    db.commit()
    db.refresh(job)
    queued = await enqueue("run_research_job", job.id)
    if not queued:
        background.add_task(execute_research_job, job.id)
    return JobOut.model_validate(job)


@router.get("/lanes/{lane_id}/geo/estimate", response_model=CostEstimate)
def geo_estimate(
    lane_id: int, top_n: int | None = None, db: Session = Depends(get_db)
) -> CostEstimate:
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lane not found")
    n = top_n or settings.research_top_n_default
    count = len(select_geo_targets(db, lane_id, n))
    return CostEstimate(
        lead_count=count,
        per_lead_usd=GEO_PER_LEAD_USD,
        estimated_usd=round(count * GEO_PER_LEAD_USD, 2),
    )


@router.get("/geo/disclaimer")
def geo_disclaimer() -> dict:
    """The plain-language caveat the UI must show (§4b)."""
    return {"disclaimer": GEO_DISCLAIMER}


@router.post(
    "/lanes/{lane_id}/geo", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED
)
async def run_geo(
    lane_id: int,
    payload: GeoRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobOut:
    """Stage-4b GEO gap pre-check — triage for ranking only (§4b). Gated to top-N."""
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lane not found")
    if payload.lead_ids:
        valid = db.query(Lead.id).filter(
            Lead.id.in_(payload.lead_ids),
            Lead.lane_id == lane_id,
            Lead.stage != LeadStage.REJECTED,
        ).all()
        params = {"lead_ids": [r[0] for r in valid], "force_fixtures": payload.force_fixtures}
    else:
        params = {
            "top_n": payload.top_n or settings.research_top_n_default,
            "force_fixtures": payload.force_fixtures,
        }
    job = Job(type=JobType.GEO_CHECK, lane_id=lane_id, status=JobStatus.QUEUED, params=params)
    db.add(job)
    db.commit()
    db.refresh(job)
    queued = await enqueue("run_geo_job", job.id)
    if not queued:
        background.add_task(execute_geo_job, job.id)
    return JobOut.model_validate(job)
