"""Send queue processing (§7). Gmail-draft mode: create a Gmail draft per approved
lead, ready for the operator to eyeball and hit send.

Server-side guardrails: per-identity daily cap, a send window, randomised spacing,
and a suppression check — never burst, never send to a suppressed address, never
auto-send to a LOW-confidence/unverified email (§9).
"""

from __future__ import annotations

import logging
import random
import time
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import (
    ActivityType,
    EmailConfidence,
    EmailStatus,
    LeadStatus,
)
from app.models.lead import ActivityLog, Contact, Email, Lead, Suppression
from app.services.app_settings import get_sending_settings
from app.services.sender import get_sender

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _suppressed(db: Session) -> set[str]:
    out: set[str] = set()
    for s in db.scalars(select(Suppression)).all():
        out.add(s.email_or_domain.strip().lower())
    return out


def _is_suppressed(email: str, suppressed: set[str]) -> bool:
    email = email.lower()
    domain = email.split("@")[-1]
    return email in suppressed or domain in suppressed


def _within_window(start_hour: int, end_hour: int) -> bool:
    h = _now().hour
    return start_hour <= h < end_hour


def _sent_today(db: Session) -> int:
    start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(
        select(func.count(Email.id)).where(
            Email.status == EmailStatus.SENT, Email.sent_at >= start
        )
    ) or 0


def _run(db: Session, job) -> dict:
    cfg = get_sending_settings(db)
    params = job.params or {}
    ignore_window = bool(params.get("ignore_window", False))

    if not ignore_window and not _within_window(cfg.window_start_hour, cfg.window_end_hour):
        job.message = (
            f"Outside send window ({cfg.window_start_hour:02d}:00–"
            f"{cfg.window_end_hour:02d}:00 UTC)"
        )
        return {"drafted": 0, "skipped_reason": "outside send window"}

    remaining = max(0, cfg.daily_cap - _sent_today(db))
    requested = params.get("limit")
    if requested:
        remaining = min(remaining, int(requested))

    # Queued touch-1 emails, best leads first.
    rows = db.scalars(
        select(Email)
        .join(Lead, Email.lead_id == Lead.id)
        .where(
            Email.touch_no == 1,
            Email.status == EmailStatus.QUEUED,
            Lead.status == LeadStatus.QUEUED,
        )
        .order_by(Lead.final_score.desc().nullslast())
        .limit(remaining)
    ).all()

    job.total = len(rows)
    db.commit()

    sender = get_sender(db)
    suppressed = _suppressed(db)
    counts = {"drafted": 0, "suppressed": 0, "no_email": 0, "simulated": sender.simulated}

    for i, email in enumerate(rows):
        lead = db.get(Lead, email.lead_id)
        primary = db.scalar(
            select(Contact).where(Contact.lead_id == lead.id, Contact.is_primary.is_(True))
        )
        addr = primary.email if primary else None

        if not addr:
            email.status = EmailStatus.CANCELLED
            counts["no_email"] += 1
            db.add(ActivityLog(
                lead_id=lead.id, type=ActivityType.NOTE,
                detail={"send_skip": "no email (LinkedIn-first)"}, created_at=_now(),
            ))
            job.progress = i + 1
            db.commit()
            continue

        if _is_suppressed(addr, suppressed):
            email.status = EmailStatus.CANCELLED
            lead.status = LeadStatus.SUPPRESSED
            counts["suppressed"] += 1
            db.add(ActivityLog(
                lead_id=lead.id, type=ActivityType.NOTE,
                detail={"send_skip": "suppressed", "address": addr}, created_at=_now(),
            ))
            job.progress = i + 1
            db.commit()
            continue

        # Never auto-send to LOW-confidence in a real send; in draft mode a human
        # still reviews, but we keep the guard explicit and skip.
        if primary.email_confidence == EmailConfidence.LOW:
            db.add(ActivityLog(
                lead_id=lead.id, type=ActivityType.NOTE,
                detail={"send_skip": "LOW email confidence — verify first"},
                created_at=_now(),
            ))
            job.progress = i + 1
            db.commit()
            continue

        result = sender.create_draft(
            to=addr, subject=email.subject or "", body=email.body or "", from_addr=cfg.identity,
        )
        email.gmail_draft_id = result.draft_id
        email.gmail_thread_id = result.thread_id
        email.status = EmailStatus.SENT
        email.sent_at = _now()
        lead.status = LeadStatus.SENT
        counts["drafted"] += 1
        db.add(ActivityLog(
            lead_id=lead.id, type=ActivityType.EMAIL_SENT,
            detail={
                "mode": cfg.mode, "to": addr, "draft_id": result.draft_id,
                "simulated": result.simulated,
            },
            created_at=_now(),
        ))
        job.progress = i + 1
        job.message = f"Drafted {counts['drafted']}/{len(rows)}"
        db.commit()

        # Randomised spacing for real sends only (never burst).
        if not result.simulated and i < len(rows) - 1:
            time.sleep(random.uniform(cfg.min_spacing_seconds, cfg.max_spacing_seconds))

    return counts


def execute_send_job(job_id: int) -> None:
    from app.db import SessionLocal
    from app.models.job import Job

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = _now()
        db.commit()
        try:
            counts = _run(db, job)
            job.status = "succeeded"
            job.result = counts
            if "skipped_reason" not in counts:
                job.message = (
                    f"{'Simulated ' if counts.get('simulated') else ''}drafted "
                    f"{counts['drafted']} (suppressed {counts.get('suppressed', 0)}, "
                    f"no-email {counts.get('no_email', 0)})"
                )
            job.finished_at = _now()
            db.commit()
        except Exception as exc:  # noqa: BLE001
            log.exception("send job %s failed", job_id)
            db.rollback()
            job = db.get(Job, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = _now()
                db.commit()
