"""Stage 4b — GEO gap pre-check (triage, NOT the deliverable) (§4b).

Runs the lane's buyer-intent queries through the engine APIs (Perplexity sonar,
OpenAI web-search, Gemini grounding), degrading gracefully when a key is missing.
For each answer it detects whether the prospect is named/recommended, who the
competitors are, and what sources are cited, then derives a gap severity + hook
type that feeds ranking.

IMPORTANT: engine-API results approximate but do NOT equal the consumer
ChatGPT/Gemini/Perplexity apps. This stage is for ranking and hook detection
only. The real evidence (screenshots) is produced by the operator in the consumer
apps during prep (§6). A "no-gap" pre-check downgrades a lead; a stark gap
promotes it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import ActivityType, GeoHookType, LeadStage
from app.models.lead import ActivityLog, GeoCheck, Lead
from app.services import ai
from app.services.scoring import compute_final

log = logging.getLogger(__name__)

GEO_DISCLAIMER = (
    "Engine-API results approximate but do not equal the consumer ChatGPT/Gemini/"
    "Perplexity apps. This is triage for ranking & hook detection only — the real "
    "evidence is the screenshots you capture in the consumer apps during prep."
)

PER_LEAD_ESTIMATE_USD = 0.04  # rough: a few engine + extraction calls per lead


# --------------------------------------------------------------------------- #
# Engines
# --------------------------------------------------------------------------- #
class GeoEngine:
    name = ""

    def available(self) -> bool:
        raise NotImplementedError

    def query(self, prompt: str) -> tuple[str, list] | None:
        """Return (answer_text, citations) or None on failure."""
        raise NotImplementedError


class PerplexityEngine(GeoEngine):
    name = "perplexity"

    def available(self) -> bool:
        return bool(settings.perplexity_api_key)

    def query(self, prompt: str) -> tuple[str, list] | None:
        try:
            r = httpx.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {settings.perplexity_api_key}"},
                json={"model": "sonar", "messages": [{"role": "user", "content": prompt}]},
                timeout=40.0,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:
            log.info("perplexity query failed: %s", exc)
            return None
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        citations = data.get("citations", []) or []
        return answer, citations


class OpenAIEngine(GeoEngine):
    name = "openai"

    def available(self) -> bool:
        return bool(settings.openai_api_key)

    def query(self, prompt: str) -> tuple[str, list] | None:
        try:
            r = httpx.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"model": "gpt-4o", "tools": [{"type": "web_search"}], "input": prompt},
                timeout=60.0,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:
            log.info("openai query failed: %s", exc)
            return None
        # Responses API: prefer output_text; fall back to walking output items.
        answer = data.get("output_text", "")
        citations: list = []
        if not answer:
            for item in data.get("output", []):
                for block in item.get("content", []):
                    if block.get("type") in ("output_text", "text"):
                        answer += block.get("text", "")
                    for ann in block.get("annotations", []) or []:
                        if ann.get("url"):
                            citations.append(ann["url"])
        return answer, citations


class GeminiEngine(GeoEngine):
    name = "gemini"

    def available(self) -> bool:
        return bool(settings.gemini_api_key)

    def query(self, prompt: str) -> tuple[str, list] | None:
        try:
            r = httpx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-2.0-flash:generateContent",
                params={"key": settings.gemini_api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "tools": [{"google_search": {}}],
                },
                timeout=60.0,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:
            log.info("gemini query failed: %s", exc)
            return None
        answer = ""
        citations: list = []
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                answer += part.get("text", "")
            meta = cand.get("groundingMetadata", {})
            for chunk in meta.get("groundingChunks", []) or []:
                uri = chunk.get("web", {}).get("uri")
                if uri:
                    citations.append(uri)
        return answer, citations


ENGINES: list[GeoEngine] = [PerplexityEngine(), OpenAIEngine(), GeminiEngine()]


# --------------------------------------------------------------------------- #
# Analysis & aggregation
# --------------------------------------------------------------------------- #
_ANALYZE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "prospect_named": {"type": "boolean"},
        "prospect_recommended": {"type": "boolean"},
        "competitors": {"type": "array", "items": {"type": "string"}},
        "cited_sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["prospect_named", "prospect_recommended", "competitors", "cited_sources"],
}


def _analyze(prospect: str, query: str, answer: str, citations: list) -> tuple[dict, float]:
    system = (
        "You analyse an AI search engine's answer to a buyer-intent query. Determine "
        "whether the named prospect business appears in the answer (prospect_named), "
        "whether it is positively recommended (prospect_recommended), list competitor "
        "businesses mentioned (competitors), and list cited sources (cited_sources). "
        "Use ONLY the answer text and citations provided."
    )
    user = (
        f"Prospect business: {prospect}\nQuery: {query}\n\n"
        f"Answer:\n{answer[:6000]}\n\nCitations: {citations}"
    )
    return ai.complete_json(
        model=settings.model_cheap, system=system, user=user, schema=_ANALYZE_SCHEMA, max_tokens=800
    )


def severity_and_hook(named: bool, recommended: bool) -> tuple[float, GeoHookType]:
    if not named:
        return 90.0, GeoHookType.ABSENCE           # not present → biggest opportunity
    if named and not recommended:
        return 60.0, GeoHookType.WEAK_PRESENCE     # present but not recommended
    return 10.0, GeoHookType.NO_GAP                # named & recommended → little to sell


def build_queries(lead: Lead, config) -> list[str]:
    """Fill the lane's buyer-intent templates for this lead."""
    service = ""
    if lead.research_briefs:
        services = lead.research_briefs[-1].high_ticket_services or []
        if services:
            service = str(services[0])
    location = lead.location or ""
    out: list[str] = []
    for tmpl in config.geo.query_templates:
        q = tmpl.replace("{company}", lead.company)
        q = q.replace("{location}", location).replace("{service}", service)
        out.append(q.strip())
    return out[:4]


def geo_check_lead(db: Session, lead: Lead, config, *, force_fixtures: bool = False) -> float:
    """Run the GEO pre-check for one lead. Returns cost_usd; sets lead.gap_score."""
    queries = build_queries(lead, config)
    engines = [e for e in ENGINES if e.available()]
    now = datetime.now(UTC)
    cost = 0.0
    severities: list[float] = []

    # Replace any prior GEO checks for this lead — re-runs supersede, not stack.
    db.execute(delete(GeoCheck).where(GeoCheck.lead_id == lead.id))

    if not engines and not force_fixtures:
        # Graceful no-op: record that no engine is configured; leave gap_score alone.
        db.add(
            GeoCheck(
                lead_id=lead.id, engine="none",
                query="(no GEO engines configured)",
                competitors=[], cited_sources=[], raw={"skipped": True}, checked_at=now,
            )
        )
        db.add(ActivityLog(
            lead_id=lead.id, type=ActivityType.GEO_CHECKED,
            detail={"skipped": "no engines configured"}, created_at=now,
        ))
        return 0.0

    use_fixture = force_fixtures or not engines
    engine_names = ["fixture"] if use_fixture else [e.name for e in engines]

    for ename in engine_names:
        engine = None if use_fixture else next(e for e in engines if e.name == ename)
        for q in queries:
            if use_fixture:
                res = {
                    "prospect_named": False,
                    "prospect_recommended": False,
                    "competitors": ["Example Competitor A", "Example Competitor B"],
                    "cited_sources": [],
                }
                raw = {"fixture": True}
                c = 0.0
            else:
                qr = engine.query(q)
                if qr is None:
                    continue
                answer, citations = qr
                res, c = _analyze(lead.company, q, answer, citations)
                raw = {"answer": answer[:2000], "citations": citations}
                cost += c

            sev, hook = severity_and_hook(res["prospect_named"], res["prospect_recommended"])
            severities.append(sev)
            db.add(
                GeoCheck(
                    lead_id=lead.id,
                    engine=ename,
                    query=q,
                    prospect_named=res["prospect_named"],
                    prospect_recommended=res["prospect_recommended"],
                    competitors=res["competitors"],
                    cited_sources=res["cited_sources"],
                    hook_type=hook,
                    severity=sev,
                    raw=raw,
                    cost_usd=c,
                    checked_at=now,
                )
            )

    if severities:
        lead.gap_score = round(sum(severities) / len(severities), 1)
        lead.final_score = compute_final(
            fit=lead.fit_score,
            gap=lead.gap_score,
            reachability=lead.reachability_score,
            weights=config.final_weights,
        )

    db.add(ActivityLog(
        lead_id=lead.id, type=ActivityType.GEO_CHECKED,
        detail={"gap_score": lead.gap_score, "fixture": use_fixture, "cost_usd": round(cost, 6)},
        created_at=now,
    ))
    return cost


def select_geo_targets(db: Session, lane_id: int, top_n: int) -> list[Lead]:
    return list(
        db.scalars(
            select(Lead)
            .where(Lead.lane_id == lane_id, Lead.stage != LeadStage.REJECTED)
            .order_by(Lead.final_score.desc().nullslast())
            .limit(top_n)
        ).all()
    )


def execute_geo_job(job_id: int) -> None:
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
            force_fixtures = bool(params.get("force_fixtures", False))
            lead_ids = params.get("lead_ids")
            if lead_ids:
                leads = [db.get(Lead, lid) for lid in lead_ids]
                leads = [x for x in leads if x is not None and x.lane_id == lane.id]
            else:
                top_n = int(params.get("top_n", settings.research_top_n_default))
                leads = select_geo_targets(db, lane.id, top_n)

            job.total = len(leads)
            db.commit()
            total_cost = 0.0
            for i, lead in enumerate(leads):
                try:
                    total_cost += geo_check_lead(db, lead, config, force_fixtures=force_fixtures)
                except Exception:  # noqa: BLE001
                    log.exception("geo check failed for lead %s", lead.id)
                    db.rollback()
                job.progress = i + 1
                job.message = f"GEO-checked {i + 1}/{len(leads)} (${total_cost:.2f})"
                db.commit()

            job.status = "succeeded"
            job.result = {"checked": len(leads), "total_cost_usd": round(total_cost, 4)}
            job.message = f"GEO-checked {len(leads)} leads — est. ${total_cost:.2f}"
            job.finished_at = datetime.now(UTC)
            db.commit()
        except Exception as exc:  # noqa: BLE001
            log.exception("geo job %s failed", job_id)
            db.rollback()
            job = db.get(Job, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = datetime.now(UTC)
                db.commit()
