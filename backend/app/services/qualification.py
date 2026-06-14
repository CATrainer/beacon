"""Stage 2 — hard qualification (rules, no AI, near-free). Kill before spend (§4).

Pure function so it's trivially testable. Each rejection returns a human reason
that's stored on the lead and shown in the UI; the operator can override.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.lane import QualificationRules
from app.services.dedupe import normalize_name


@dataclass
class QualificationResult:
    passed: bool
    reason: str | None = None


def qualify(
    *,
    company: str,
    website: str | None,
    domain: str | None,
    rules: QualificationRules,
    suppressed: set[str],
    incorporation_years: float | None = None,
) -> QualificationResult:
    """Apply the lane's Stage-2 rules. Returns pass/fail + reason."""

    # 1. Resolvable website — no site → can't optimise → reject.
    if rules.require_website and not (website and domain):
        return QualificationResult(False, "No website on record (can't optimise GEO presence)")

    # 2. Suppression / existing-client list (matched on domain).
    if domain and domain in suppressed:
        return QualificationResult(False, "On suppression / existing-client list")

    # 3. Obvious national chain / franchise (blocklist substring on name or domain).
    norm = normalize_name(company)
    hay = f"{norm} {domain or ''}".lower()
    for term in rules.chain_blocklist:
        t = term.strip().lower()
        if t and t in hay:
            return QualificationResult(False, f"Matches chain/franchise blocklist ('{term}')")

    # 4. Incorporated > N years, only when we actually know the age.
    if (
        rules.min_incorporation_years is not None
        and incorporation_years is not None
        and incorporation_years < rules.min_incorporation_years
    ):
        return QualificationResult(
            False,
            f"Incorporated < {rules.min_incorporation_years} years "
            f"({incorporation_years:.1f})",
        )

    return QualificationResult(True, None)
