"""EmailResolver — swappable verification/enrichment backstop (§4, non-goal §12).

This is the *backstop only* step of the contact waterfall: used to verify
candidates and fill gaps, never as the primary engine. The provider is abstract
so it can be swapped (Hunter / a verification API / etc.) and is disabled by
default (it costs money — operator opts in via settings).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

log = logging.getLogger(__name__)


@dataclass
class EmailFinding:
    email: str
    confidence: str  # "high" | "medium" | "low"


class EmailResolver:
    enabled: bool = False

    def find(self, domain: str, first: str | None, last: str | None) -> EmailFinding | None:
        return None

    def verify(self, email: str) -> str | None:
        """Return a confidence string if the address looks deliverable, else None."""
        return None


class NullResolver(EmailResolver):
    """Used when no verification provider is configured."""

    enabled = False


class HunterResolver(EmailResolver):
    """Hunter.io backend (email-finder + email-verifier)."""

    enabled = True
    _BASE = "https://api.hunter.io/v2"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    def find(self, domain: str, first: str | None, last: str | None) -> EmailFinding | None:
        if not (first and last):
            return None
        try:
            r = httpx.get(
                f"{self._BASE}/email-finder",
                params={"domain": domain, "first_name": first, "last_name": last,
                        "api_key": self._key},
                timeout=20.0,
            )
            r.raise_for_status()
            data = r.json().get("data", {})
        except httpx.HTTPError as exc:
            log.info("hunter find failed for %s: %s", domain, exc)
            return None
        email = data.get("email")
        if not email:
            return None
        score = data.get("score") or 0
        conf = "high" if score >= 90 else "medium" if score >= 60 else "low"
        return EmailFinding(email=email, confidence=conf)

    def verify(self, email: str) -> str | None:
        try:
            r = httpx.get(
                f"{self._BASE}/email-verifier",
                params={"email": email, "api_key": self._key},
                timeout=20.0,
            )
            r.raise_for_status()
            data = r.json().get("data", {})
        except httpx.HTTPError as exc:
            log.info("hunter verify failed for %s: %s", email, exc)
            return None
        status = data.get("status")
        if status == "valid":
            return "high"
        if status in {"accept_all", "webmail", "unknown"}:
            return "medium"
        return "low"


def get_email_resolver() -> EmailResolver:
    if settings.email_resolver_enabled and settings.email_resolver_provider.lower() == "hunter":
        return HunterResolver(settings.hunter_api_key)
    return NullResolver()
