"""Model package — import every model so Alembic autogenerate sees full metadata."""

from app.models.base import Base
from app.models.integration import AppSetting, OAuthCredential
from app.models.job import Job
from app.models.lane import Lane
from app.models.lead import (
    ActivityLog,
    Contact,
    Email,
    Evidence,
    GeoCheck,
    Lead,
    ResearchBrief,
    SourceCursor,
    SourceHit,
    Suppression,
)
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Job",
    "OAuthCredential",
    "AppSetting",
    "Lane",
    "Lead",
    "SourceHit",
    "ResearchBrief",
    "GeoCheck",
    "Contact",
    "Evidence",
    "Email",
    "Suppression",
    "SourceCursor",
    "ActivityLog",
]
