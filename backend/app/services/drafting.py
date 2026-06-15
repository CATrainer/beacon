"""Email drafting (§8) — reused across the tool.

Three-touch sequence engineered for the paid-audit funnel: touch-1 is an
evidence hook + soft reply ask (no call, no price); touch-2 introduces the paid
audit + retainer discount and asks for a call via the Cal.com booking link (never
invented slots — live availability); touch-3 is a breakup. Constraints (§8):
60–110 words; first-name greeting; only real GEO-pre-check competitors (never
invented); plain text, no links except signature; British English; no exclamation
marks / banned phrases.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.models.lead import Lead
from app.services import ai

log = logging.getLogger(__name__)

_TITLES = {"dr", "mr", "mrs", "ms", "miss", "prof", "mx"}


def first_name_of(full: str | None) -> str:
    """First name with any leading title stripped (preserving case)."""
    if not full:
        return "there"
    parts = [p for p in full.split() if p.strip(".").lower() not in _TITLES]
    return parts[0] if parts else "there"

SIGNATURE = (
    "Caleb Trainer / Heuricity — engineers, not marketers / "
    "heuricity.com/ai-visibility / {cal_link}"
)

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "touch1": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
            "required": ["subject", "body"],
        },
        "touch2": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
            "required": ["subject", "body"],
        },
        "touch3": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
            "required": ["subject", "body"],
        },
    },
    "required": ["touch1", "touch2", "touch3"],
}

_SYSTEM = (
    "You write cold B2B outreach for Heuricity, which gets specialist firms cited "
    "in AI answers (GEO / AI visibility). Write a three-touch sequence engineered "
    "for REPLIES, not a hard sell.\n\n"
    "SEQUENCE STRATEGY (follow exactly):\n"
    "- touch-1: Hook with the SPECIFIC evidence (the real competitor names that "
    "appeared in AI answers while the prospect did not). One outcome line. Then a "
    "LOW-FRICTION reply ask — invite them to reply if they'd like a quick free "
    "rundown of where they show up versus those competitors. CRITICAL: touch-1 "
    "must contain NO meeting/call request and NO time slots and NO price and NO "
    "mention of the paid audit — its only call to action is inviting a reply.\n"
    "- touch-2 (sent +3 days, references the screenshot evidence): briefly "
    "introduce the paid GEO audit ({audit_price}) — it maps exactly where they "
    "appear vs competitors across ChatGPT/Gemini/Perplexity and the fixes — and "
    "note that audit clients get {audit_discount} ({retainer} retainer). Then ask "
    "for a short call and point them to the booking link so they pick a time that "
    "suits — write it as: grab a time at {cal_link}, or reply and I'll work around "
    "you. Do NOT invent specific dates/times.\n"
    "- touch-3 (sent +7 days): a short, gracious breakup.\n\n"
    "HARD CONSTRAINTS for every email:\n"
    "- 60–110 words; first-name greeting only; British English; plain text, no "
    "links except in the signature; no exclamation marks; never use 'I hope this "
    "finds you well' or 'quick question'.\n"
    "- NEVER invent or embellish evidence — use only the facts/competitors given. "
    "If no competitors were provided, describe the absence plainly without naming "
    "any.\n"
    "- End every email with exactly this signature line: {signature}\n"
    "Tone: a competent engineer sharing an observation, not a marketer."
)


def _competitors_from_geo(lead: Lead) -> list[str]:
    seen: list[str] = []
    for g in lead.geo_checks:
        for c in g.competitors or []:
            if c not in seen:
                seen.append(c)
    return seen[:5]


def draft_emails(lead: Lead) -> tuple[dict, float]:
    """Generate touch-1/2/3 for a lead. Returns (touches_dict, cost_usd)."""
    brief = lead.research_briefs[-1] if lead.research_briefs else None
    primary = next((c for c in lead.contacts if c.is_primary), None)
    dm_name = (brief.decision_maker_name if brief else None) or (
        primary.decision_maker_name if primary else None
    )
    first_name = first_name_of(dm_name)
    competitors = _competitors_from_geo(lead)
    cal_link = settings.cal_link or "[set your Cal.com link in CAL_LINK]"
    signature = SIGNATURE.format(cal_link=cal_link)
    has_evidence = bool(lead.evidence)

    high_ticket = brief.high_ticket_services if brief else []
    hook = brief.human_hook if brief else None

    user = (
        f"Prospect: {lead.company}\n"
        f"Decision-maker first name: {first_name}\n"
        f"Their high-ticket services: {', '.join(high_ticket) if high_ticket else 'unknown'}\n"
        f"Human hook (optional): {hook or 'none'}\n"
        f"Competitors that appeared in AI answers (real, from the pre-check): "
        f"{', '.join(competitors) if competitors else 'none captured'}\n"
        f"Screenshot evidence captured by operator: {'yes' if has_evidence else 'not yet'}\n"
        f"Booking link (use in touch-2 only): {cal_link}\n"
    )
    system = _SYSTEM.format(
        signature=signature,
        audit_price=settings.offer_audit_price,
        audit_discount=settings.offer_audit_discount,
        retainer=settings.offer_retainer,
        cal_link=cal_link,
    )
    return ai.complete_json(
        model=settings.model_high, system=system, user=user, schema=_SCHEMA, max_tokens=1500
    )
