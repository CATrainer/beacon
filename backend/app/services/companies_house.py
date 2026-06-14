"""Companies House — secondary *enrichment*, not discovery (§3).

SIC-based discovery is unreliable, so CH is used only to enrich a lead already
found via CQC/ATOL/Places: match on company name (+ postcode when available) and
pull officers as decision-maker candidates. Entirely best-effort — any failure
returns empty and never blocks sourcing.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_BASE = "https://api.company-information.service.gov.uk"
_TIMEOUT = httpx.Timeout(15.0, connect=8.0)


def available() -> bool:
    return settings.companies_house_enabled


def _auth() -> tuple[str, str]:
    # CH uses HTTP Basic with the API key as username and an empty password.
    return (settings.companies_house_api_key, "")


def director_candidates(company_name: str, postcode: str | None = None) -> dict:
    """Return {'company_number', 'directors': [names]} for the best name match.

    Empty dict if disabled, no match, or any error.
    """
    if not available() or not company_name:
        return {}
    try:
        search = httpx.get(
            f"{_BASE}/search/companies",
            params={"q": company_name, "items_per_page": 5},
            auth=_auth(),
            headers={"User-Agent": settings.user_agent},
            timeout=_TIMEOUT,
        )
        search.raise_for_status()
        items = search.json().get("items", [])
    except httpx.HTTPError as exc:
        log.info("CH search failed for %r: %s", company_name, exc)
        return {}

    if not items:
        return {}

    # Prefer a postcode match when we have one; else take the top hit.
    chosen = items[0]
    if postcode:
        pc = postcode.replace(" ", "").lower()
        for it in items:
            addr = (it.get("address") or {}).get("postal_code", "")
            if addr and addr.replace(" ", "").lower() == pc:
                chosen = it
                break

    number = chosen.get("company_number")
    if not number:
        return {}

    try:
        officers_resp = httpx.get(
            f"{_BASE}/company/{number}/officers",
            params={"register_type": "directors"},
            auth=_auth(),
            headers={"User-Agent": settings.user_agent},
            timeout=_TIMEOUT,
        )
        officers_resp.raise_for_status()
        officers = officers_resp.json().get("items", [])
    except httpx.HTTPError as exc:
        log.info("CH officers failed for %s: %s", number, exc)
        return {"company_number": number, "directors": []}

    directors = [
        o.get("name")
        for o in officers
        if "director" in (o.get("officer_role") or "").lower() and not o.get("resigned_on")
    ]
    return {"company_number": number, "directors": [d for d in directors if d]}
