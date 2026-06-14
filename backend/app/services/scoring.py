"""Stage 3 — fit & wealth scoring from cheap signals (§3/§5).

Scores survivors 0–100 on likelihood-to-pay-and-be-worth-it from data already
cheaply available: Places metadata (reviews, rating) the source hits carry, plus
a single lightweight homepage fetch (keyword scans). Sub-scores are stored in
``score_breakdown`` so the UI can show *why* a lead scored what it did.

The final score blends the components that exist (fit now; gap severity and
reachability arrive in slices 4–5) using the lane's ``final_weights``.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.enums import ActivityType, LeadStage, LeadStatus
from app.models.lead import ActivityLog, Lead
from app.schemas.lane import FinalWeights, ScoringWeights
from app.services.http import fetch_html

log = logging.getLogger(__name__)

# --- Keyword lexicons -------------------------------------------------------
HIGH_TICKET_KEYWORDS = [
    "implant", "invisalign", "veneer", "aesthetic", "botox", "filler",
    "cosmetic", "orthodont", "smile makeover", "facial", "rejuvenation",
]
BOOKING_KEYWORDS = ["book online", "book now", "request appointment", "online booking", "book a"]
BLOG_KEYWORDS = ["/blog", "blog", "latest news", "/news", "articles"]
AD_MARKERS = ["googletagmanager", "gtag(", "fbq(", "fbevents", "google-analytics"]
MULTI_LOCATION_MARKERS = [
    "our clinics", "our locations", "our practices", "our branches",
    "clinics across", "locations across", "find a clinic",
]
PREMIUM_KEYWORDS = [
    "luxury", "tailor-made", "tailormade", "bespoke", "handcrafted", "exclusive",
    "boutique", "private", "five-star", "5-star", "first class", "curated",
]
BESPOKE_KEYWORDS = [
    "tailor-made", "tailormade", "bespoke", "tailored", "made-to-measure",
    "design your", "custom itinerary", "personalised",
]


@dataclass
class ScoreContext:
    html: str = ""
    review_count: int = 0
    rating: float | None = None
    source_keys: set[str] = field(default_factory=set)
    membership: dict[str, bool] = field(default_factory=dict)


def _count_hits(html: str, keywords: list[str]) -> int:
    return sum(1 for k in keywords if k in html)


# --- Per-signal strength functions (each returns 0.0–1.0) -------------------
def _s_high_ticket(ctx: ScoreContext) -> float:
    return min(_count_hits(ctx.html, HIGH_TICKET_KEYWORDS) / 3.0, 1.0)


def _s_review_count(ctx: ScoreContext) -> float:
    # log scale: ~1000 reviews → 1.0
    return min(math.log10(ctx.review_count + 1) / 3.0, 1.0) if ctx.review_count else 0.0


def _s_rating(ctx: ScoreContext) -> float:
    if ctx.rating is None:
        return 0.0
    return max(0.0, min((ctx.rating - 3.0) / 2.0, 1.0))  # 3.0→0, 5.0→1


def _s_multiple_locations(ctx: ScoreContext) -> float:
    return 1.0 if _count_hits(ctx.html, MULTI_LOCATION_MARKERS) else 0.0


def _s_booking_funnel(ctx: ScoreContext) -> float:
    return 1.0 if _count_hits(ctx.html, BOOKING_KEYWORDS) else 0.0


def _s_blog(ctx: ScoreContext) -> float:
    return 1.0 if _count_hits(ctx.html, BLOG_KEYWORDS) else 0.0


def _s_tracked_ads(ctx: ScoreContext) -> float:
    return 1.0 if _count_hits(ctx.html, AD_MARKERS) else 0.0


def _s_premium(ctx: ScoreContext) -> float:
    return min(_count_hits(ctx.html, PREMIUM_KEYWORDS) / 3.0, 1.0)


def _s_bespoke(ctx: ScoreContext) -> float:
    return min(_count_hits(ctx.html, BESPOKE_KEYWORDS) / 2.0, 1.0)


def _s_membership_aito(ctx: ScoreContext) -> float:
    return 1.0 if ctx.membership.get("aito") else 0.0


def _s_membership_atol_abta(ctx: ScoreContext) -> float:
    return 1.0 if ctx.membership.get("atol") or ctx.membership.get("abta") else 0.0


def _s_review_signals(ctx: ScoreContext) -> float:
    # combined size + quality proxy for travel
    return round((_s_review_count(ctx) + _s_rating(ctx)) / 2.0, 4)


def _s_premium_positioning(ctx: ScoreContext) -> float:
    return _s_premium(ctx)


def _s_bespoke_language(ctx: ScoreContext) -> float:
    return _s_bespoke(ctx)


STRENGTH_FUNCS = {
    "high_ticket_services": _s_high_ticket,
    "review_count": _s_review_count,
    "rating": _s_rating,
    "multiple_locations": _s_multiple_locations,
    "booking_funnel": _s_booking_funnel,
    "blog": _s_blog,
    "tracked_ads": _s_tracked_ads,
    "premium_positioning": _s_premium_positioning,
    "bespoke_language": _s_bespoke_language,
    "membership_aito": _s_membership_aito,
    "membership_atol_abta": _s_membership_atol_abta,
    "review_signals": _s_review_signals,
}


def build_context(lead: Lead, *, fetch: bool) -> ScoreContext:
    ctx = ScoreContext()
    for hit in lead.source_hits:
        ctx.source_keys.add(hit.source_key)
        meta = hit.raw_meta or {}
        rc = meta.get("review_count")
        if isinstance(rc, int) and rc > ctx.review_count:
            ctx.review_count = rc
        rt = meta.get("rating")
        if isinstance(rt, int | float):
            ctx.rating = float(rt) if ctx.rating is None else max(ctx.rating, float(rt))
        if meta.get("atol_holder"):
            ctx.membership["atol"] = True
        boost = meta.get("membership_boost") or {}
        if isinstance(boost, dict) and boost.get("aito"):
            ctx.membership["aito"] = True

    if fetch and lead.website:
        html = fetch_html(lead.website)
        if html:
            ctx.html = html.lower()
    return ctx


def compute_fit(lead: Lead, weights: ScoringWeights, *, fetch: bool = True) -> tuple[float, dict]:
    ctx = build_context(lead, fetch=fetch)
    signals = weights.signals or {}
    total_w = sum(signals.values()) or 1.0
    contributions: dict[str, dict] = {}
    acc = 0.0
    for name, w in signals.items():
        fn = STRENGTH_FUNCS.get(name)
        strength = fn(ctx) if fn else 0.0
        contribution = w * strength
        acc += contribution
        contributions[name] = {
            "weight": w,
            "strength": round(strength, 3),
            "contribution": round(contribution, 2),
        }
    fit = round(100.0 * acc / total_w, 1)
    breakdown = {
        "signals": contributions,
        "total_weight": total_w,
        "context": {
            "review_count": ctx.review_count,
            "rating": ctx.rating,
            "homepage_fetched": bool(ctx.html),
            "sources": sorted(ctx.source_keys),
        },
    }
    return fit, breakdown


def compute_final(
    *,
    fit: float | None,
    gap: float | None,
    reachability: float | None,
    weights: FinalWeights,
) -> float | None:
    """Blend the components that exist, normalised by their weights (§5)."""
    parts = [
        (weights.fit, fit),
        (weights.gap, gap),
        (weights.reachability, reachability),
    ]
    present = [(w, s) for w, s in parts if s is not None and w > 0]
    if not present:
        return None
    total_w = sum(w for w, _ in present)
    return round(sum(w * s for w, s in present) / total_w, 1)


def score_leads(
    db: Session,
    leads: list[Lead],
    weights: ScoringWeights,
    final_weights: FinalWeights,
    *,
    fetch: bool = True,
) -> int:
    """Score the given leads in place. Returns the count scored."""
    scored = 0
    for lead in leads:
        fit, breakdown = compute_fit(lead, weights, fetch=fetch)
        lead.fit_score = fit
        lead.score_breakdown = breakdown
        lead.final_score = compute_final(
            fit=fit,
            gap=lead.gap_score,
            reachability=lead.reachability_score,
            weights=final_weights,
        )
        # Advance QUALIFIED → SCORED; never downgrade a more-advanced lead.
        if lead.stage == LeadStage.QUALIFIED:
            lead.stage = LeadStage.SCORED
            if lead.status == LeadStatus.QUALIFIED:
                lead.status = LeadStatus.QUALIFIED  # CRM status unchanged by scoring
        db.add(
            ActivityLog(
                lead_id=lead.id,
                type=ActivityType.SCORED,
                detail={"fit": fit, "final": lead.final_score},
                created_at=datetime.now(UTC),
            )
        )
        scored += 1
    return scored


def execute_score_job(job_id: int) -> None:
    """Re-score every non-rejected lead in a lane (worker entrypoint)."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models.job import Job
    from app.models.lane import Lane

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
            from app.schemas.lane import LaneConfig

            config = LaneConfig.model_validate(lane.config or {})
            leads = list(
                db.scalars(
                    select(Lead).where(
                        Lead.lane_id == lane.id,
                        Lead.stage != LeadStage.REJECTED,
                    )
                ).all()
            )
            job.total = len(leads)
            db.commit()
            count = 0
            for lead in leads:
                score_leads(db, [lead], config.scoring, config.final_weights, fetch=True)
                count += 1
                job.progress = count
                if count % 5 == 0:
                    db.commit()
            db.commit()
            job.status = "succeeded"
            job.result = {"scored": count}
            job.message = f"Re-scored {count} leads"
            job.finished_at = datetime.now(UTC)
            db.commit()
        except Exception as exc:  # noqa: BLE001
            log.exception("score job %s failed", job_id)
            db.rollback()
            job = db.get(Job, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = datetime.now(UTC)
                db.commit()
