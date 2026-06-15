"""Send queue, sending settings, suppression, pipeline, status & activity (§7).

Beacon is the CRM — these endpoints cover the send-and-track half of the loop.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.enums import ActivityType, JobStatus, JobType
from app.models.job import Job
from app.models.lead import ActivityLog, Lead, Suppression
from app.queue import enqueue
from app.schemas.crm import (
    ActivityOut,
    PipelineOut,
    SendingSettingsOut,
    SendingSettingsUpdate,
    SendRequest,
    SourcingSettingsOut,
    SourcingSettingsUpdate,
    StatusUpdate,
    SuppressionCreate,
    SuppressionOut,
)
from app.schemas.job import JobOut
from app.services.app_settings import (
    get_sending_settings,
    get_sourcing_settings,
    update_sending_settings,
    update_sourcing_settings,
)
from app.services.sending import execute_send_job

router = APIRouter(tags=["crm"], dependencies=[Depends(get_current_user)])


def _now() -> datetime:
    return datetime.now(UTC)


# --- Send queue -------------------------------------------------------------
@router.post("/send/process", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def process_send_queue(
    payload: SendRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobOut:
    """Process the send queue — create Gmail drafts for approved leads (§7)."""
    job = Job(
        type=JobType.SEND,
        status=JobStatus.QUEUED,
        params={"limit": payload.limit, "ignore_window": payload.ignore_window},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    queued = await enqueue("run_send_job", job.id)
    if not queued:
        background.add_task(execute_send_job, job.id)
    return JobOut.model_validate(job)


# --- Sending settings -------------------------------------------------------
@router.get("/settings/sending", response_model=SendingSettingsOut)
def read_sending_settings(db: Session = Depends(get_db)) -> SendingSettingsOut:
    return SendingSettingsOut(**get_sending_settings(db).model_dump())


@router.put("/settings/sending", response_model=SendingSettingsOut)
def write_sending_settings(
    payload: SendingSettingsUpdate, db: Session = Depends(get_db)
) -> SendingSettingsOut:
    updated = update_sending_settings(db, payload.model_dump(exclude_none=True))
    return SendingSettingsOut(**updated.model_dump())


# --- Scheduled sourcing settings -------------------------------------------
@router.get("/settings/sourcing", response_model=SourcingSettingsOut)
def read_sourcing_settings(db: Session = Depends(get_db)) -> SourcingSettingsOut:
    return SourcingSettingsOut(**get_sourcing_settings(db).model_dump())


@router.put("/settings/sourcing", response_model=SourcingSettingsOut)
def write_sourcing_settings(
    payload: SourcingSettingsUpdate, db: Session = Depends(get_db)
) -> SourcingSettingsOut:
    updated = update_sourcing_settings(db, payload.model_dump(exclude_none=True))
    return SourcingSettingsOut(**updated.model_dump())


# --- Suppression ------------------------------------------------------------
@router.get("/suppression", response_model=list[SuppressionOut])
def list_suppression(db: Session = Depends(get_db)) -> list[SuppressionOut]:
    rows = db.scalars(select(Suppression).order_by(Suppression.created_at.desc())).all()
    return [SuppressionOut.model_validate(r) for r in rows]


@router.post("/suppression", response_model=SuppressionOut, status_code=201)
def add_suppression(payload: SuppressionCreate, db: Session = Depends(get_db)) -> SuppressionOut:
    val = payload.email_or_domain.strip().lower()
    if not val:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="email_or_domain required")
    if db.scalar(select(Suppression).where(Suppression.email_or_domain == val)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Already suppressed")
    row = Suppression(email_or_domain=val, reason=payload.reason, created_at=_now())
    db.add(row)
    db.commit()
    db.refresh(row)
    return SuppressionOut.model_validate(row)


@router.delete("/suppression/{suppression_id}", status_code=204)
def delete_suppression(suppression_id: int, db: Session = Depends(get_db)) -> Response:
    row = db.get(Suppression, suppression_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(row)
    db.commit()
    return Response(status_code=204)


# --- Pipeline / CRM ---------------------------------------------------------
@router.get("/pipeline", response_model=PipelineOut)
def pipeline(db: Session = Depends(get_db)) -> PipelineOut:
    rows = db.execute(select(Lead.status, func.count(Lead.id)).group_by(Lead.status)).all()
    return PipelineOut(counts={str(s): n for s, n in rows})


@router.patch("/leads/{lead_id}/status")
def change_status(lead_id: int, payload: StatusUpdate, db: Session = Depends(get_db)) -> dict:
    """Manual CRM stage move (e.g. mark Call booked, Lost)."""
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lead not found")
    previous = lead.status
    lead.status = payload.status
    db.add(ActivityLog(
        lead_id=lead.id, type=ActivityType.STATUS_CHANGED,
        detail={"from": str(previous), "to": str(payload.status), "note": payload.note},
        created_at=_now(),
    ))
    db.commit()
    return {"status": str(lead.status), "lead_id": lead.id}


@router.get("/leads/{lead_id}/activity", response_model=list[ActivityOut])
def lead_activity(lead_id: int, db: Session = Depends(get_db)) -> list[ActivityOut]:
    rows = db.scalars(
        select(ActivityLog)
        .where(ActivityLog.lead_id == lead_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(200)
    ).all()
    return [ActivityOut.model_validate(r) for r in rows]
