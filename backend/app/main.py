"""FastAPI application entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import system
from app.api.router import api_router
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="Beacon",
    description="Heuricity's internal lead engine & GEO-audit CRM.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /api/health and /api/status (no auth) + the authed API surface.
app.include_router(system.router, prefix="/api")
app.include_router(api_router)


@app.get("/")
def root() -> dict:
    return {"name": "Beacon", "version": __version__, "docs": "/docs"}
