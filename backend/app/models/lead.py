"""Lead and all per-lead child records (§10 data model).

One company == one Lead, deduped on normalised name + domain. Multiple source
hits merge their fields onto the single lead (§3).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import (
    ActivityType,
    ContactSource,
    EmailConfidence,
    EmailStatus,
    GeoHookType,
    LeadStage,
    LeadStatus,
)
from app.models.types import JSONB


def _enum(enum_cls, name: str):
    """VARCHAR-backed enum column (no native PG type — see enums.py)."""
    return SAEnum(enum_cls, native_enum=False, length=40, name=name, validate_strings=True)


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    lane_id: Mapped[int] = mapped_column(
        ForeignKey("lanes.id", ondelete="CASCADE"), index=True, nullable=False
    )

    company: Mapped[str] = mapped_column(String(300), nullable=False)
    website: Mapped[str | None] = mapped_column(String(500))
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    location: Mapped[str | None] = mapped_column(String(300))

    stage: Mapped[LeadStage] = mapped_column(
        _enum(LeadStage, "lead_stage"), default=LeadStage.SOURCED, index=True, nullable=False
    )
    status: Mapped[LeadStatus] = mapped_column(
        _enum(LeadStatus, "lead_status"), default=LeadStatus.SOURCED, index=True, nullable=False
    )
    reject_reason: Mapped[str | None] = mapped_column(String(500))
    reject_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Scores (0–100). Sub-scores live in JSONB so the UI can explain "why".
    fit_score: Mapped[float | None] = mapped_column(Float)
    gap_score: Mapped[float | None] = mapped_column(Float)
    reachability_score: Mapped[float | None] = mapped_column(Float)
    final_score: Mapped[float | None] = mapped_column(Float, index=True)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    notes: Mapped[str | None] = mapped_column(Text)

    # Normalised key for dedupe: f"{norm_name}|{domain}".
    dedupe_key: Mapped[str] = mapped_column(String(560), index=True, nullable=False)

    lane: Mapped[Lane] = relationship(back_populates="leads")  # noqa: F821
    source_hits: Mapped[list[SourceHit]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
    research_briefs: Mapped[list[ResearchBrief]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", order_by="ResearchBrief.created_at"
    )
    geo_checks: Mapped[list[GeoCheck]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
    contacts: Mapped[list[Contact]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
    emails: Mapped[list[Email]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", order_by="Email.touch_no"
    )
    activities: Mapped[list[ActivityLog]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="ActivityLog.created_at.desc()",
    )

    __table_args__ = (
        UniqueConstraint("lane_id", "dedupe_key", name="uq_lead_lane_dedupe"),
    )


class SourceHit(Base):
    __tablename__ = "source_hits"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_key: Mapped[str] = mapped_column(String(60), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(300))
    raw_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    lead: Mapped[Lead] = relationship(back_populates="source_hits")


class ResearchBrief(Base):
    __tablename__ = "research_briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text)
    specialisms: Mapped[str | None] = mapped_column(Text)
    high_ticket_services: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    decision_maker_name: Mapped[str | None] = mapped_column(String(200))
    decision_maker_role: Mapped[str | None] = mapped_column(String(200))
    human_hook: Mapped[str | None] = mapped_column(Text)
    marketing_sophistication: Mapped[str | None] = mapped_column(Text)
    emails_found: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    pages_fetched: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(80))
    cost_usd: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    lead: Mapped[Lead] = relationship(back_populates="research_briefs")


class GeoCheck(Base):
    __tablename__ = "geo_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    engine: Mapped[str] = mapped_column(String(40), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    prospect_named: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prospect_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    competitors: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    cited_sources: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    hook_type: Mapped[GeoHookType | None] = mapped_column(_enum(GeoHookType, "geo_hook_type"))
    severity: Mapped[float | None] = mapped_column(Float)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    lead: Mapped[Lead] = relationship(back_populates="geo_checks")


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str | None] = mapped_column(String(320))
    email_confidence: Mapped[EmailConfidence | None] = mapped_column(
        _enum(EmailConfidence, "email_confidence")
    )
    source: Mapped[ContactSource | None] = mapped_column(_enum(ContactSource, "contact_source"))
    decision_maker_name: Mapped[str | None] = mapped_column(String(200))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    lead: Mapped[Lead] = relationship(back_populates="contacts")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    engine: Mapped[str | None] = mapped_column(String(40))
    screenshot_path: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    lead: Mapped[Lead] = relationship(back_populates="evidence")


class Email(Base, TimestampMixin):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    touch_no: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3
    subject: Mapped[str | None] = mapped_column(String(400))
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[EmailStatus] = mapped_column(
        _enum(EmailStatus, "email_status"), default=EmailStatus.DRAFT, index=True, nullable=False
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gmail_thread_id: Mapped[str | None] = mapped_column(String(120))
    gmail_draft_id: Mapped[str | None] = mapped_column(String(120))

    lead: Mapped[Lead] = relationship(back_populates="emails")


class Suppression(Base):
    __tablename__ = "suppression"

    id: Mapped[int] = mapped_column(primary_key=True)
    # An email address or a bare domain. Checked at send time (§9).
    email_or_domain: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[ActivityType] = mapped_column(_enum(ActivityType, "activity_type"), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    lead: Mapped[Lead] = relationship(back_populates="activities")
