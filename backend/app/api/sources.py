"""Trigger source runs and list available adapters."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters import list_adapters
from app.core.deps import get_current_user
from app.db import get_db
from app.models.enums import JobStatus, JobType
from app.models.job import Job
from app.models.lane import Lane
from app.queue import enqueue
from app.schemas.job import JobOut, SourceRunRequest
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
