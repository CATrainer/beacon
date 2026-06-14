"""Top-level API router aggregating all sub-routers under /api."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import auth, lanes, leads

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(lanes.router)
api_router.include_router(leads.router)
