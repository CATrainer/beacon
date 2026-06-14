"""Top-level API router aggregating all sub-routers under /api."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import auth, crm, integrations, jobs, lanes, leads, prep, sources

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(lanes.router)
api_router.include_router(leads.router)
api_router.include_router(sources.router)
api_router.include_router(prep.router)
api_router.include_router(crm.router)
api_router.include_router(integrations.router)
api_router.include_router(jobs.router)
