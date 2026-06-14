"""Contact email resolution waterfall (§4).

Priority order, stop at first confident result:
1. From research (free, best): real emails the agent found on the site.
2. Pattern inference: derive the address pattern from a known personal address
   and construct the decision-maker's address.
3. Verification/enrichment API (backstop only, opt-in): verify candidates / fill
   gaps via the swappable EmailResolver.
4. None → "LinkedIn-first": store linkedin_url, no email.

Confidence is always surfaced (HIGH/MEDIUM/LOW). A blank email is fine; a bounced
email harms the sending domain — we never label an unverified guess as HIGH.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import ContactSource, EmailConfidence
from app.services.email_resolver import EmailResolver

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
ROLE_LOCALPARTS = {
    "info", "hello", "contact", "admin", "enquiries", "enquiry", "reception",
    "office", "team", "hi", "mail", "sales", "bookings", "appointments", "support",
}


@dataclass
class ResolvedContact:
    email: str | None
    email_confidence: EmailConfidence | None
    source: ContactSource
    decision_maker_name: str | None
    linkedin_url: str | None


def extract_emails(text: str) -> list[str]:
    """Deterministically pull real email addresses from page text/HTML."""
    seen: list[str] = []
    for m in _EMAIL_RE.findall(text or ""):
        e = m.lower().strip(".")
        # skip obvious asset filenames mistaken for emails
        if e.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
            continue
        if e not in seen:
            seen.append(e)
    return seen


def split_name(full: str | None) -> tuple[str | None, str | None]:
    if not full:
        return None, None
    parts = [p for p in re.sub(r"[^A-Za-z \-]", "", full).split() if p]
    # drop common titles
    parts = [p for p in parts if p.lower() not in {"dr", "mr", "mrs", "ms", "miss", "prof"}]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0].lower(), None
    return parts[0].lower(), parts[-1].lower()


def _local(email: str) -> str:
    return email.split("@", 1)[0]


def _is_role(email: str) -> bool:
    return _local(email) in ROLE_LOCALPARTS


def _matches_name(email: str, first: str | None, last: str | None) -> bool:
    local = _local(email)
    return bool((first and first in local) or (last and last in local))


def infer_pattern(sample_local: str, first: str | None, last: str | None) -> str | None:
    """Infer a pattern token from a known personal local-part."""
    if "." in sample_local:
        return "first.last"
    if first and sample_local == first:
        return "first"
    if first and last and sample_local == f"{first[0]}{last}":
        return "flast"
    if first and last and sample_local == f"{first}{last}":
        return "firstlast"
    return None


def build_email(pattern: str, first: str, last: str | None, domain: str) -> str | None:
    if pattern == "first":
        return f"{first}@{domain}"
    if not last:
        return None
    if pattern == "first.last":
        return f"{first}.{last}@{domain}"
    if pattern == "flast":
        return f"{first[0]}{last}@{domain}"
    if pattern == "firstlast":
        return f"{first}{last}@{domain}"
    return None


def resolve_contact(
    *,
    domain: str | None,
    decision_maker_name: str | None,
    emails_found: list[str],
    linkedin_url: str | None,
    resolver: EmailResolver,
) -> ResolvedContact:
    first, last = split_name(decision_maker_name)
    emails = [e for e in (emails_found or []) if "@" in e]
    same_domain = [e for e in emails if domain and e.endswith(f"@{domain}")]
    pool = same_domain or emails

    # 1. Published email that matches the decision-maker → best.
    for e in pool:
        if _matches_name(e, first, last):
            return ResolvedContact(e, EmailConfidence.HIGH, ContactSource.RESEARCH,
                                   decision_maker_name, linkedin_url)

    # 2. Pattern inference from a known personal address → build the DM's address.
    if first and same_domain:
        personal = next((e for e in same_domain if not _is_role(e)), None)
        if personal:
            # Structural guess from the sample's shape (we don't know whose it is).
            pattern = "first.last" if "." in _local(personal) else "first"
            built = build_email(pattern, first, last, domain)
            if built:
                if built in same_domain:
                    return ResolvedContact(built, EmailConfidence.HIGH, ContactSource.RESEARCH,
                                           decision_maker_name, linkedin_url)
                conf = EmailConfidence.MEDIUM
                if resolver.enabled:
                    v = resolver.verify(built)
                    if v == "high":
                        conf = EmailConfidence.HIGH
                    elif v == "low":
                        conf = EmailConfidence.LOW
                return ResolvedContact(built, conf, ContactSource.PATTERN,
                                       decision_maker_name, linkedin_url)

    # 3a. Any published (e.g. generic info@) real address → usable, HIGH.
    if pool:
        return ResolvedContact(pool[0], EmailConfidence.HIGH, ContactSource.RESEARCH,
                               decision_maker_name, linkedin_url)

    # 3b. Verification/enrichment API backstop (opt-in).
    if resolver.enabled and domain and first and last:
        found = resolver.find(domain, first, last)
        if found:
            conf = {
                "high": EmailConfidence.HIGH,
                "medium": EmailConfidence.MEDIUM,
                "low": EmailConfidence.LOW,
            }.get(found.confidence, EmailConfidence.LOW)
            return ResolvedContact(found.email, conf, ContactSource.VERIFICATION_API,
                                   decision_maker_name, linkedin_url)

    # 4. Nothing reliable → LinkedIn-first (blank email beats a bounced one).
    return ResolvedContact(None, None, ContactSource.LINKEDIN_FIRST,
                           decision_maker_name, linkedin_url)
