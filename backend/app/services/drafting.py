"""Email drafting (§8) — reused across the tool.

Enforces the design doc's constraints: 60–110 words; first-name greeting; opens
with the *specific* researched evidence (real competitors from the GEO pre-check
/ confirmed by screenshot, never invented); one outcome line; one ask with two
named time slots; plain text, no links except signature; British English; no
exclamation marks; banned phrases. Returns touch-1/2/3. Never fabricates evidence.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

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
    "in AI answers (GEO / AI visibility). Write three emails (touch-1, touch-2 at "
    "+3 days referencing the screenshot evidence, touch-3 a breakup at +7 days).\n\n"
    "HARD CONSTRAINTS for every email:\n"
    "- 60–110 words.\n"
    "- First-name greeting only.\n"
    "- Open with the SPECIFIC researched evidence provided (real competitor names "
    "from the GEO pre-check). NEVER invent or embellish evidence — use only the "
    "facts given. If no competitors were provided, describe the absence plainly "
    "without naming any.\n"
    "- One outcome line, e.g. 'we typically get specialist firms cited in AI "
    "answers for their core queries within 90 days'.\n"
    "- One ask with the two named time slots provided.\n"
    "- Plain text. No links except in the signature.\n"
    "- British English.\n"
    "- No exclamation marks. Do NOT use 'I hope this finds you well' or "
    "'quick question'.\n"
    "- End with exactly this signature line: {signature}\n"
    "Tone: a competent engineer sharing an observation, not a marketer."
)


def propose_call_slots(now: datetime | None = None) -> list[str]:
    """Two upcoming weekday slots, human-formatted for the ask."""
    now = now or datetime.now(UTC)
    slots: list[str] = []
    times = [(10, 0, "10:00"), (14, 0, "2pm")]
    d = now
    i = 0
    while len(slots) < 2:
        d = d + timedelta(days=1)
        if d.weekday() < 5:  # Mon–Fri
            hour, minute, label = times[i % 2]
            slots.append(f"{d.strftime('%A %d %B')} at {label}")
            i += 1
    return slots


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
    slots = propose_call_slots()
    signature = SIGNATURE.format(cal_link=settings.cal_link or "[Cal.com link]")
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
        f"Two call slots to offer: {slots[0]}; {slots[1]}\n"
    )
    system = _SYSTEM.format(signature=signature)
    return ai.complete_json(
        model=settings.model_high, system=system, user=user, schema=_SCHEMA, max_tokens=1500
    )
