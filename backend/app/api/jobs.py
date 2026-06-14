"""Job polling endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.enums import JobType
from app.models.job import Job
from app.schemas.job import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    lane_id: int | None = None,
    type: JobType | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[JobOut]:
    conditions = []
    if lane_id is not None:
        conditions.append(Job.lane_id == lane_id)
    if type is not None:
        conditions.append(Job.type == type)
    rows = db.scalars(
        select(Job).where(*conditions).order_by(Job.created_at.desc()).limit(limit)
    ).all()
    return [JobOut.model_validate(r) for r in rows]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobOut.model_validate(job)
