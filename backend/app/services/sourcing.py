"""Stage 1–2 orchestration: source → dedupe/merge → qualify → enrich.

Runs adapters for a lane, merges hits onto one Lead per company (union is richer
than any single source, §3), applies Stage-2 qualification, then best-effort
Companies House director enrichment. Updates the Job row so the UI can poll.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters import RawCandidate, get_adapter
from app.models.enums import ActivityType, JobStatus, JobType, LeadStage, LeadStatus
from app.models.job import Job
from app.models.lane import Lane
from app.models.lead import (
    ActivityLog,
    Contact,
    Email,
    Evidence,
    GeoCheck,
    Lead,
    ResearchBrief,
    SourceCursor,
    SourceHit,
    Suppression,
)
from app.schemas.lane import LaneConfig
from app.services import companies_house
from app.services.dedupe import compute_dedupe_key, extract_domain, normalize_name
from app.services.qualification import qualify

# Child tables that point at a lead — reassigned when two leads merge.
_LEAD_CHILDREN = (SourceHit, ResearchBrief, GeoCheck, Contact, Evidence, Email, ActivityLog)

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _add_activity(db: Session, lead_id: int, type_: ActivityType, detail: dict) -> None:
    db.add(ActivityLog(lead_id=lead_id, type=type_, detail=detail, created_at=_now()))


def _get_or_create_cursor(db: Session, lane_id: int, source_key: str) -> SourceCursor:
    """Get the cursor row, creating it atomically (concurrent runs may race)."""
    row = db.scalar(
        select(SourceCursor).where(
            SourceCursor.lane_id == lane_id, SourceCursor.source_key == source_key
        )
    )
    if row is not None:
        return row
    try:
        with db.begin_nested():
            row = SourceCursor(lane_id=lane_id, source_key=source_key, cursor={})
            db.add(row)
            db.flush()
        return row
    except IntegrityError:
        # Another concurrent run created it first — re-read.
        return db.scalar(
            select(SourceCursor).where(
                SourceCursor.lane_id == lane_id, SourceCursor.source_key == source_key
            )
        )


def _suppressed_domains(db: Session) -> set[str]:
    out: set[str] = set()
    for s in db.scalars(select(Suppression)).all():
        val = s.email_or_domain.strip().lower()
        out.add(val.split("@")[-1] if "@" in val else val)
    return out


def merge_leads(db: Session, winner: Lead, loser: Lead) -> None:
    """Fold ``loser`` into ``winner``: reassign all child rows, then delete loser.

    Used by dedup hardening to collapse a name-only lead into the domain-keyed one
    for the same company (historical split).
    """
    if winner.id == loser.id:
        return
    # Keep the richer fields.
    winner.website = winner.website or loser.website
    winner.domain = winner.domain or loser.domain
    winner.location = winner.location or loser.location
    for model in _LEAD_CHILDREN:
        db.execute(update(model).where(model.lead_id == loser.id).values(lead_id=winner.id))
    db.delete(loser)
    db.flush()


def _resolve_lead(db: Session, lane_id: int, company: str, domain: str | None) -> Lead | None:
    """Find the existing lead for this company, matching across key types (§dedup).

    Strong match on domain; otherwise match on normalised name (so a no-website
    hit folds into an existing domain-keyed lead, and vice-versa).
    """
    norm = normalize_name(company)
    if domain:
        lead = db.scalar(select(Lead).where(Lead.lane_id == lane_id, Lead.domain == domain))
        if lead is not None:
            # Fold any historical name-only duplicates of the same company.
            dups = db.scalars(
                select(Lead).where(
                    Lead.lane_id == lane_id,
                    Lead.norm_name == norm,
                    Lead.domain.is_(None),
                    Lead.id != lead.id,
                )
            ).all()
            for d in dups:
                merge_leads(db, lead, d)
            return lead
    matches = db.scalars(
        select(Lead).where(Lead.lane_id == lane_id, Lead.norm_name == norm)
    ).all()
    if matches:
        return next((m for m in matches if m.domain), matches[0])
    return None


def _ingest_candidate(
    db: Session,
    lane_id: int,
    cand: RawCandidate,
    cache: dict[str, Lead],
    counts: dict[str, int],
) -> Lead:
    domain = extract_domain(cand.website)
    norm = normalize_name(cand.company_name)

    # In-run cache keyed by domain AND name so two hits for one company converge.
    lead = (cache.get(f"d:{domain}") if domain else None) or cache.get(f"n:{norm}")
    if lead is None:
        lead = _resolve_lead(db, lane_id, cand.company_name, domain)

    if lead is None:
        lead = Lead(
            lane_id=lane_id,
            company=cand.company_name,
            website=cand.website,
            domain=domain,
            location=cand.location,
            norm_name=norm,
            stage=LeadStage.SOURCED,
            status=LeadStatus.SOURCED,
            dedupe_key=compute_dedupe_key(cand.company_name, domain),
        )
        db.add(lead)
        db.flush()  # assign id
        _add_activity(db, lead.id, ActivityType.LEAD_CREATED, {"source": cand.source_key})
        counts["created"] += 1
    else:
        # Upgrade a name-only lead to domain-keyed once we learn its website.
        if domain and not lead.domain:
            lead.domain = domain
            lead.website = lead.website or cand.website
            lead.dedupe_key = compute_dedupe_key(cand.company_name, domain)
        if not lead.website and cand.website:
            lead.website = cand.website
        if not lead.location and cand.location:
            lead.location = cand.location
        if not lead.norm_name:
            lead.norm_name = norm
        counts["merged"] += 1

    db.add(
        SourceHit(
            lead_id=lead.id,
            source_key=cand.source_key,
            source_ref=cand.source_ref,
            raw_meta=cand.raw_meta,
            fetched_at=_now(),
        )
    )
    _add_activity(
        db, lead.id, ActivityType.SOURCE_HIT_ADDED,
        {"source": cand.source_key, "ref": cand.source_ref},
    )
    if lead.domain:
        cache[f"d:{lead.domain}"] = lead
    cache[f"n:{lead.norm_name}"] = lead
    return lead


def _run(db: Session, job: Job) -> dict:
    params = job.params or {}
    lane = db.get(Lane, job.lane_id)
    if lane is None:
        raise ValueError(f"Lane {job.lane_id} not found")

    config = LaneConfig.model_validate(lane.config or {})
    only_keys = set(params.get("source_keys") or [])
    limit_per_source = int(params.get("limit_per_source", 50))
    force_fixtures = bool(params.get("force_fixtures", False))
    manual_entries = params.get("manual_entries")

    # --- Fetch from each enabled source -------------------------------------
    candidates: list[RawCandidate] = []
    by_source: dict[str, int] = {}
    enabled = [s for s in config.sources if s.enabled and (not only_keys or s.key in only_keys)]

    for src in enabled:
        adapter = get_adapter(src.key)
        if adapter is None:
            log.warning("unknown adapter '%s' in lane %s", src.key, lane.id)
            continue
        src_params = dict(src.params)
        if src.key == "manual_paste" and manual_entries:
            src_params["entries"] = manual_entries
        job.message = f"Fetching from {src.key}…"
        db.commit()

        # Load (or race-safely create) the per-(lane, source) resume cursor.
        cur_row = _get_or_create_cursor(db, lane.id, src.key)
        cursor = dict(cur_row.cursor or {})

        fetched = adapter.fetch(
            src_params, limit_per_source, lane.config,
            cursor=cursor, force_fixtures=force_fixtures,
        )
        cur_row.cursor = cursor  # adapter advanced it in place; persist for next run
        candidates.extend(fetched)
        by_source[src.key] = len(fetched)
        job.message = f"Fetched {len(fetched)} from {src.key}"
        db.commit()

    job.total = len(candidates)
    db.commit()

    # --- Dedupe / merge into Leads ------------------------------------------
    cache: dict[str, Lead] = {}
    counts = {"created": 0, "merged": 0, "qualified": 0, "rejected": 0, "enriched": 0}
    for i, cand in enumerate(candidates):
        _ingest_candidate(db, lane.id, cand, cache, counts)
        job.progress = i + 1
        if (i + 1) % 10 == 0:
            db.commit()
    db.commit()

    # --- Stage 2 qualification ----------------------------------------------
    suppressed = _suppressed_domains(db)
    job.message = "Qualifying…"
    db.commit()
    qualified_leads: list[Lead] = []
    # The cache stores each lead under both a domain and a name key — dedupe to
    # unique leads (and drop any merged-away leads no longer in the session).
    unique_leads = list({lead.id: lead for lead in cache.values() if lead in db}.values())
    for lead in unique_leads:
        if lead.reject_overridden:
            continue
        result = qualify(
            company=lead.company,
            website=lead.website,
            domain=lead.domain,
            rules=config.qualification,
            suppressed=suppressed,
        )
        if result.passed:
            lead.stage = LeadStage.QUALIFIED
            lead.status = LeadStatus.QUALIFIED
            lead.reject_reason = None
            qualified_leads.append(lead)
            counts["qualified"] += 1
            _add_activity(db, lead.id, ActivityType.QUALIFIED, {})
        else:
            lead.stage = LeadStage.REJECTED
            lead.status = LeadStatus.REJECTED
            lead.reject_reason = result.reason
            counts["rejected"] += 1
            _add_activity(db, lead.id, ActivityType.REJECTED, {"reason": result.reason})
    db.commit()

    # --- Stage 3 scoring of survivors ---------------------------------------
    # Cheap signals score everyone who survived qualification. Skip the homepage
    # fetch on fixture runs (the example.com sites don't resolve) — Places
    # metadata still drives the score.
    if qualified_leads:
        from app.services.scoring import score_leads

        job.message = "Scoring…"
        db.commit()
        counts["scored"] = score_leads(
            db,
            qualified_leads,
            config.scoring,
            config.final_weights,
            fetch=not force_fixtures,
        )
        db.commit()

    # --- Companies House enrichment (best-effort, director candidates) -------
    if companies_house.available():
        job.message = "Enriching with Companies House…"
        db.commit()
        for lead in qualified_leads:
            postcode = None
            for sh in lead.source_hits:
                postcode = sh.raw_meta.get("postcode")
                if postcode:
                    break
            data = companies_house.director_candidates(lead.company, postcode)
            if data:
                db.add(
                    SourceHit(
                        lead_id=lead.id,
                        source_key="companies_house",
                        source_ref=data.get("company_number"),
                        raw_meta=data,
                        fetched_at=_now(),
                    )
                )
                counts["enriched"] += 1
        db.commit()

    return {
        "candidates": len(candidates),
        "by_source": by_source,
        **counts,
        "used_fixtures": force_fixtures,
    }


def execute_source_job(job_id: int) -> None:
    """Top-level entrypoint run by the worker. Owns its own DB session."""
    from app.db import SessionLocal

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            log.error("source job %s not found", job_id)
            return
        job.status = "running"
        job.started_at = _now()
        db.commit()
        try:
            result = _run(db, job)
            job.status = "succeeded"
            job.result = result
            job.message = (
                f"Done: {result['created']} new, {result['merged']} merged, "
                f"{result['qualified']} qualified, {result['rejected']} rejected"
            )
            job.finished_at = _now()
            db.commit()
            log.info("source job %s succeeded: %s", job_id, result)
        except Exception as exc:  # noqa: BLE001
            log.exception("source job %s failed", job_id)
            db.rollback()
            job = db.get(Job, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = _now()
                db.commit()


def run_scheduled_sourcing() -> None:
    """Cron entrypoint: run an incremental source pull for every active lane.

    No-op unless enabled in settings. Each lane's run resumes from its saved
    cursors, so this keeps the funnel growing without re-scanning.
    """
    from app.db import SessionLocal
    from app.services.app_settings import get_sourcing_settings

    with SessionLocal() as db:
        cfg = get_sourcing_settings(db)
        if not cfg.enabled:
            log.info("scheduled sourcing disabled; skipping")
            return
        lane_ids = [
            lane.id for lane in db.scalars(select(Lane).where(Lane.is_active.is_(True))).all()
        ]

    log.info("scheduled sourcing: %d active lanes (limit %d)", len(lane_ids), cfg.limit)
    for lane_id in lane_ids:
        with SessionLocal() as db:
            job = Job(
                type=JobType.SOURCE_RUN,
                lane_id=lane_id,
                status=JobStatus.QUEUED,
                params={"limit_per_source": cfg.limit},
            )
            db.add(job)
            db.commit()
            job_id = job.id
        execute_source_job(job_id)
