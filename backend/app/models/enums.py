"""Enumerations used across the data model.

Stored as VARCHAR + CHECK constraint (``native_enum=False``) rather than native
Postgres enums, so adding a value is an ordinary column migration rather than an
``ALTER TYPE``. Values are lowercase strings.
"""

from __future__ import annotations

from enum import StrEnum


class LeadStage(StrEnum):
    """Position in the cheap-first funnel (§2 of the design doc)."""

    SOURCED = "sourced"        # Stage 1 — raw candidate ingested
    QUALIFIED = "qualified"    # Stage 2 — passed hard qualification
    SCORED = "scored"          # Stage 3 — fit/wealth scored
    ENRICHED = "enriched"      # Stage 4 — research + GEO pre-check done
    READY = "ready"            # Stage 5 — in the ranked queue / prepped
    REJECTED = "rejected"      # Killed at Stage 2 (reason stored)


class LeadStatus(StrEnum):
    """CRM pipeline status (§7). Independent of funnel stage."""

    SOURCED = "sourced"
    QUALIFIED = "qualified"
    RESEARCHED = "researched"
    PREPPED = "prepped"
    QUEUED = "queued"
    SENT = "sent"
    REPLIED = "replied"
    CALL_BOOKED = "call_booked"
    AUDIT_SOLD = "audit_sold"
    DELIVERED = "delivered"
    RETAINER = "retainer"
    LOST = "lost"
    REJECTED = "rejected"
    SUPPRESSED = "suppressed"


class EmailConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EmailStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    REPLIED = "replied"
    CANCELLED = "cancelled"


class GeoHookType(StrEnum):
    ABSENCE = "absence"
    MISREPRESENTATION = "misrepresentation"
    WEAK_PRESENCE = "weak_presence"
    NO_GAP = "no_gap"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobType(StrEnum):
    SOURCE_RUN = "source_run"
    SCORE = "score"               # Slice 3 — re-score a lane
    RESEARCH = "research"          # Slice 4
    GEO_CHECK = "geo_check"        # Slice 5
    SEND = "send"                 # Slice 7 — process the send queue


class ContactSource(StrEnum):
    RESEARCH = "research"           # found on the site by the research agent
    PATTERN = "pattern"            # inferred from a known address pattern
    VERIFICATION_API = "verification_api"  # filled/verified by EmailResolver
    MANUAL = "manual"
    LINKEDIN_FIRST = "linkedin_first"


class ActivityType(StrEnum):
    LEAD_CREATED = "lead_created"
    SOURCE_HIT_ADDED = "source_hit_added"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    OVERRIDDEN = "overridden"
    SCORED = "scored"
    RESEARCHED = "researched"
    GEO_CHECKED = "geo_checked"
    CONTACT_RESOLVED = "contact_resolved"
    EVIDENCE_UPLOADED = "evidence_uploaded"
    EMAIL_DRAFTED = "email_drafted"
    EMAIL_QUEUED = "email_queued"
    EMAIL_SENT = "email_sent"
    REPLY_DETECTED = "reply_detected"
    CALL_BOOKED = "call_booked"
    STAGE_CHANGED = "stage_changed"
    STATUS_CHANGED = "status_changed"
    NOTE = "note"
