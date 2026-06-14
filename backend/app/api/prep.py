"""Human-in-the-loop prep workflow (§6).

The operator opens a lead and works one checklist: copy the exact audit queries to
run in the real ChatGPT/Gemini/Perplexity apps and upload a screenshot per query;
review & edit the AI-drafted emails; then approve → the lead joins the send queue.
Prep is decoupled from send (slice 7).
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user
from app.db import get_db
from app.models.enums import ActivityType, EmailStatus, LeadStage, LeadStatus
from app.models.lane import Lane
from app.models.lead import ActivityLog, Email, Evidence, Lead
from app.schemas.lane import LaneConfig
from app.schemas.lead import AuditQueriesOut, EmailOut, EmailUpdate, EvidenceOut
from app.services import geo
from app.services.drafting import draft_emails

router = APIRouter(tags=["prep"], dependencies=[Depends(get_current_user)])

_ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _now() -> datetime:
    return datetime.now(UTC)


def _get_lead(db: Session, lead_id: int) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.get("/leads/{lead_id}/audit-queries", response_model=AuditQueriesOut)
def audit_queries(lead_id: int, db: Session = Depends(get_db)) -> AuditQueriesOut:
    """The exact buyer-intent queries to paste into the consumer AI apps (§6)."""
    lead = _get_lead(db, lead_id)
    lane = db.get(Lane, lead.lane_id)
    config = LaneConfig.model_validate(lane.config or {})
    return AuditQueriesOut(
        queries=geo.build_queries(lead, config),
        engines=["ChatGPT", "Gemini", "Perplexity"],
    )


@router.post("/leads/{lead_id}/evidence", response_model=EvidenceOut, status_code=201)
def upload_evidence(
    lead_id: int,
    query: str = Form(...),
    engine: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> EvidenceOut:
    """Accept a screenshot for a given audit query (the irreducible manual step)."""
    lead = _get_lead(db, lead_id)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_IMAGE_EXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Upload an image file")

    lead_dir = os.path.join(settings.uploads_dir, str(lead.id))
    os.makedirs(lead_dir, exist_ok=True)
    fname = f"{uuid.uuid4().hex}{ext}"
    abspath = os.path.join(lead_dir, fname)
    with open(abspath, "wb") as out:
        out.write(file.file.read())

    rel_url = f"/uploads/{lead.id}/{fname}"
    ev = Evidence(
        lead_id=lead.id, query=query, engine=engine, screenshot_path=rel_url, uploaded_at=_now()
    )
    db.add(ev)
    db.add(ActivityLog(
        lead_id=lead.id, type=ActivityType.EVIDENCE_UPLOADED,
        detail={"query": query, "engine": engine}, created_at=_now(),
    ))
    db.commit()
    db.refresh(ev)
    return EvidenceOut.model_validate(ev)


@router.delete("/evidence/{evidence_id}", status_code=204)
def delete_evidence(evidence_id: int, db: Session = Depends(get_db)) -> Response:
    ev = db.get(Evidence, evidence_id)
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    # Remove the file too (best-effort).
    rel = ev.screenshot_path.removeprefix("/uploads/")
    abspath = os.path.join(settings.uploads_dir, rel)
    try:
        if os.path.isfile(abspath):
            os.remove(abspath)
    except OSError:
        pass
    db.delete(ev)
    db.commit()
    return Response(status_code=204)


@router.post("/leads/{lead_id}/draft", response_model=list[EmailOut])
def generate_drafts(lead_id: int, db: Session = Depends(get_db)) -> list[EmailOut]:
    """Pre-draft touch-1/2/3 from the brief + GEO evidence (§8 constraints)."""
    if not settings.anthropic_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Anthropic API key not configured")
    lead = _get_lead(db, lead_id)
    touches, cost = draft_emails(lead)

    out: list[Email] = []
    for n in (1, 2, 3):
        data = touches.get(f"touch{n}", {})
        existing = db.scalar(
            select(Email).where(Email.lead_id == lead.id, Email.touch_no == n)
        )
        if existing and existing.status != EmailStatus.DRAFT:
            # Don't overwrite an already-queued/sent email.
            out.append(existing)
            continue
        email = existing or Email(lead_id=lead.id, touch_no=n, status=EmailStatus.DRAFT)
        email.subject = data.get("subject")
        email.body = data.get("body")
        email.status = EmailStatus.DRAFT
        if existing is None:
            db.add(email)
        out.append(email)

    db.add(ActivityLog(
        lead_id=lead.id, type=ActivityType.EMAIL_DRAFTED,
        detail={"cost_usd": round(cost, 6)}, created_at=_now(),
    ))
    db.commit()
    for e in out:
        db.refresh(e)
    out.sort(key=lambda e: e.touch_no)
    return [EmailOut.model_validate(e) for e in out]


@router.patch("/emails/{email_id}", response_model=EmailOut)
def update_email(email_id: int, payload: EmailUpdate, db: Session = Depends(get_db)) -> EmailOut:
    """Operator edits a draft inline."""
    email = db.get(Email, email_id)
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Email not found")
    if email.status != EmailStatus.DRAFT:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Only draft emails can be edited")
    if payload.subject is not None:
        email.subject = payload.subject
    if payload.body is not None:
        email.body = payload.body
    db.commit()
    db.refresh(email)
    return EmailOut.model_validate(email)


@router.post("/leads/{lead_id}/approve", status_code=200)
def approve(lead_id: int, db: Session = Depends(get_db)) -> dict:
    """Approve → move the lead into the send queue (§6). Requires a touch-1 draft."""
    lead = _get_lead(db, lead_id)
    touch1 = db.scalar(select(Email).where(Email.lead_id == lead.id, Email.touch_no == 1))
    if touch1 is None or not (touch1.body or "").strip():
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Draft the touch-1 email before approving"
        )
    lead.stage = LeadStage.READY
    lead.status = LeadStatus.QUEUED
    # Mark touch-1 as queued for the send processor (Gmail-draft creation).
    if touch1.status == EmailStatus.DRAFT:
        touch1.status = EmailStatus.QUEUED
    db.add(ActivityLog(
        lead_id=lead.id, type=ActivityType.STATUS_CHANGED,
        detail={"to": "queued", "via": "prep_approve"}, created_at=_now(),
    ))
    db.commit()
    return {"status": "queued", "lead_id": lead.id}
