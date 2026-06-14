"""System endpoints: health and integration-availability status.

The status endpoint lets the UI honestly show which integrations are live vs.
awaiting a key — the backbone of graceful degradation (§2/§4b/§9).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


@router.get("/status")
def integration_status() -> dict:
    """Which optional integrations are configured. Nothing here is required to run."""
    return {
        "env": settings.app_env,
        "ai": {
            "anthropic": settings.anthropic_enabled,
            "models": {
                "default": settings.model_default,
                "high": settings.model_high,
                "cheap": settings.model_cheap,
            },
        },
        "sources": {
            "cqc": settings.cqc_enabled,
            "google_places": settings.google_places_enabled,
            "companies_house": settings.companies_house_enabled,
            "atol": True,  # public data download — no key required
            "directory_ingest": settings.anthropic_enabled,  # needs LLM extraction
            "manual_paste": True,
        },
        "geo_engines": settings.geo_engines_available(),
        "email_resolver": settings.email_resolver_enabled,
        "gmail": settings.gmail_enabled,
        "booking": bool(settings.cal_link),
    }
