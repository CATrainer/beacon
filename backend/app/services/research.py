"""Stage 4a — AI research agent + Research Brief (§4a).

Visits a prospect's own pages (home, about, team, services, contact — capped,
robots-respected, rate-limited, honest UA), extracts every email deterministically,
and synthesises a Research Brief via the Anthropic API: positioning & specialisms,
the high-ticket services they push, decision-maker (cross-checked against Companies
House officers), a human hook, and apparent marketing sophistication. Then resolves
the best contact via the waterfall and derives a reachability score.

Expensive — gated to top-N / on-demand by the caller. Per-lead cost is tracked and
summed into the job result (§9).
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import (
    ActivityType,
    EmailConfidence,
    LeadStage,
    LeadStatus,
)
from app.models.lead import ActivityLog, Contact, Lead, ResearchBrief
from app.services import ai
from app.services.contacts import extract_emails, resolve_contact
from app.services.email_resolver import get_email_resolver
from app.services.http import fetch_html
from app.services.scoring import compute_final

log = logging.getLogger(__name__)

#: Rough per-lead cost used for the pre-run estimate shown in the UI (§9).
PER_LEAD_ESTIMATE_USD = 0.05

_PATHS = [
    "", "/about", "/about-us", "/our-team", "/team", "/meet-the-team",
    "/services", "/treatments", "/contact", "/contact-us",
]
_MAX_PAGES = 6
_LINKEDIN_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|company)/[\w\-%.]+", re.I)

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "specialisms": {"type": "string"},
        "high_ticket_services": {"type": "array", "items": {"type": "string"}},
        "decision_maker_name": {"type": ["string", "null"]},
        "decision_maker_role": {"type": ["string", "null"]},
        "human_hook": {"type": ["string", "null"]},
        "marketing_sophistication": {"type": ["string", "null"]},
        "linkedin_url": {"type": ["string", "null"]},
    },
    "required": [
        "summary", "specialisms", "high_ticket_services", "decision_maker_name",
        "decision_maker_role", "human_hook", "marketing_sophistication", "linkedin_url",
    ],
}

_SYSTEM = (
    "You are a B2B research analyst preparing a outreach brief from a prospect's own "
    "website. Use ONLY the provided page text — never invent facts, names, awards or "
    "emails. Identify: positioning & specialisms; the high-ticket services they "
    "actively promote; the likely decision-maker (owner/principal/practice manager) "
    "and role, cross-checked against any Companies House directors provided; a genuine "
    "human hook (new location, award, recent hire, milestone) ONLY if evidenced; and "
    "their apparent marketing sophistication. If something isn't supported by the "
    "text, return null. Keep summary to 2–3 sentences."
)


def candidate_page_urls(website: str) -> list[str]:
    base = website.strip().rstrip("/")
    if "://" not in base:
        base = f"https://{base}"
    seen: list[str] = []
    for p in _PATHS:
        url = base + p if p else base
        if url not in seen:
            seen.append(url)
    return seen


def gather_pages(website: str) -> dict[str, str]:
    """Fetch up to _MAX_PAGES pages; returns {url: raw_html}."""
    pages: dict[str, str] = {}
    for url in candidate_page_urls(website):
        if len(pages) >= _MAX_PAGES:
            break
        html = fetch_html(url)
        if html:
            pages[url] = html
    return pages


def _page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def synthesize_brief(
    company: str,
    website: str,
    pages: dict[str, str],
    ch_directors: list[str],
    *,
    model: str | None = None,
) -> tuple[dict, float]:
    """Call the LLM to synthesise the narrative parts of the brief."""
    model = model or settings.model_default
    combined = []
    for url, html in pages.items():
        combined.append(f"--- {url} ---\n{_page_text(html)[:6000]}")
    corpus = "\n\n".join(combined)[:24000]
    directors = ", ".join(ch_directors) if ch_directors else "none provided"
    user = (
        f"Company: {company}\nWebsite: {website}\n"
        f"Companies House directors: {directors}\n\n"
        f"Website pages:\n{corpus}"
    )
    return ai.complete_json(model=model, system=_SYSTEM, user=user, schema=_SCHEMA, max_tokens=2000)


def _ch_directors(lead: Lead) -> list[str]:
    out: list[str] = []
    for hit in lead.source_hits:
        if hit.source_key == "companies_house":
            out.extend(hit.raw_meta.get("directors", []) or [])
    return out


def reachability_from_contact(contact_confidence: EmailConfidence | None, dm_named: bool) -> float:
    base = {
        EmailConfidence.HIGH: 90.0,
        EmailConfidence.MEDIUM: 60.0,
        EmailConfidence.LOW: 35.0,
        None: 15.0,
    }[contact_confidence]
    if dm_named:
        base = min(100.0, base + 10.0)
    return round(base, 1)


def research_lead(db: Session, lead: Lead, final_weights) -> float:
    """Research one lead: brief + contact + reachability. Returns cost_usd."""
    resolver = get_email_resolver()
    pages = gather_pages(lead.website) if lead.website else {}

    # Deterministic, never-fabricated facts from the pages.
    all_html = "\n".join(pages.values())
    emails_found = extract_emails(all_html)
    linkedins = _LINKEDIN_RE.findall(all_html)
    ch_dirs = _ch_directors(lead)

    brief_data: dict = {}
    cost = 0.0
    if pages and settings.anthropic_enabled:
        brief_data, cost = synthesize_brief(lead.company, lead.website or "", pages, ch_dirs)

    linkedin_url = brief_data.get("linkedin_url") or (linkedins[0] if linkedins else None)

    brief = ResearchBrief(
        lead_id=lead.id,
        summary=brief_data.get("summary"),
        specialisms=brief_data.get("specialisms"),
        high_ticket_services=brief_data.get("high_ticket_services", []) or [],
        decision_maker_name=brief_data.get("decision_maker_name"),
        decision_maker_role=brief_data.get("decision_maker_role"),
        human_hook=brief_data.get("human_hook"),
        marketing_sophistication=brief_data.get("marketing_sophistication"),
        emails_found=emails_found,
        linkedin_url=linkedin_url,
        pages_fetched=list(pages.keys()),
        model_used=settings.model_default if cost else None,
        cost_usd=cost,
        created_at=datetime.now(UTC),
    )
    db.add(brief)

    # Contact waterfall.
    resolved = resolve_contact(
        domain=lead.domain,
        decision_maker_name=brief.decision_maker_name,
        emails_found=emails_found,
        linkedin_url=linkedin_url,
        resolver=resolver,
    )
    primary = db.scalar(
        select(Contact).where(Contact.lead_id == lead.id, Contact.is_primary.is_(True))
    )
    if primary is None:
        primary = Contact(lead_id=lead.id, is_primary=True)
        db.add(primary)
    primary.email = resolved.email
    primary.email_confidence = resolved.email_confidence
    primary.source = resolved.source
    primary.decision_maker_name = resolved.decision_maker_name
    primary.linkedin_url = resolved.linkedin_url

    # Reachability feeds the final score (§5).
    lead.reachability_score = reachability_from_contact(
        resolved.email_confidence, bool(resolved.decision_maker_name)
    )
    lead.final_score = compute_final(
        fit=lead.fit_score,
        gap=lead.gap_score,
        reachability=lead.reachability_score,
        weights=final_weights,
    )
    if lead.stage in (LeadStage.SCORED, LeadStage.QUALIFIED):
        lead.stage = LeadStage.ENRICHED
    if lead.status in (LeadStatus.SOURCED, LeadStatus.QUALIFIED):
        lead.status = LeadStatus.RESEARCHED

    db.add(
        ActivityLog(
            lead_id=lead.id,
            type=ActivityType.RESEARCHED,
            detail={"cost_usd": round(cost, 6), "emails_found": len(emails_found)},
            created_at=datetime.now(UTC),
        )
    )
    conf_val = resolved.email_confidence.value if resolved.email_confidence else None
    db.add(
        ActivityLog(
            lead_id=lead.id,
            type=ActivityType.CONTACT_RESOLVED,
            detail={"source": resolved.source.value, "confidence": conf_val},
            created_at=datetime.now(UTC),
        )
    )
    return cost


def select_research_targets(db: Session, lane_id: int, top_n: int) -> list[Lead]:
    """Top-N scored, non-rejected leads by final score (§2 — Stage 4 gating)."""
    return list(
        db.scalars(
            select(Lead)
            .where(Lead.lane_id == lane_id, Lead.stage != LeadStage.REJECTED)
            .order_by(Lead.final_score.desc().nullslast())
            .limit(top_n)
        ).all()
    )


def execute_research_job(job_id: int) -> None:
    from app.db import SessionLocal
    from app.models.job import Job
    from app.models.lane import Lane
    from app.schemas.lane import LaneConfig

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = datetime.now(UTC)
        db.commit()
        try:
            lane = db.get(Lane, job.lane_id)
            if lane is None:
                raise ValueError(f"Lane {job.lane_id} not found")
            config = LaneConfig.model_validate(lane.config or {})
            params = job.params or {}
            lead_ids = params.get("lead_ids")
            if lead_ids:
                leads = [db.get(Lead, lid) for lid in lead_ids]
                leads = [x for x in leads if x is not None and x.lane_id == lane.id]
            else:
                top_n = int(params.get("top_n", settings.research_top_n_default))
                leads = select_research_targets(db, lane.id, top_n)

            job.total = len(leads)
            db.commit()

            total_cost = 0.0
            by_conf: dict[str, int] = {}
            for i, lead in enumerate(leads):
                try:
                    total_cost += research_lead(db, lead, config.final_weights)
                except Exception as exc:  # noqa: BLE001
                    log.exception("research failed for lead %s", lead.id)
                    db.rollback()
                    db.add(
                        ActivityLog(
                            lead_id=lead.id,
                            type=ActivityType.NOTE,
                            detail={"research_error": str(exc)},
                            created_at=datetime.now(UTC),
                        )
                    )
                job.progress = i + 1
                job.message = f"Researched {i + 1}/{len(leads)} (${total_cost:.2f})"
                db.commit()

            # Tally contact confidence for the result summary.
            for lead in leads:
                primary = db.scalar(
                    select(Contact).where(Contact.lead_id == lead.id, Contact.is_primary.is_(True))
                )
                key = (
                    primary.email_confidence.value
                    if primary and primary.email_confidence
                    else "linkedin_first"
                )
                by_conf[key] = by_conf.get(key, 0) + 1

            job.status = "succeeded"
            job.result = {
                "researched": len(leads),
                "total_cost_usd": round(total_cost, 4),
                "by_confidence": by_conf,
            }
            job.message = f"Researched {len(leads)} leads — est. ${total_cost:.2f}"
            job.finished_at = datetime.now(UTC)
            db.commit()
        except Exception as exc:  # noqa: BLE001
            log.exception("research job %s failed", job_id)
            db.rollback()
            job = db.get(Job, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = datetime.now(UTC)
                db.commit()
