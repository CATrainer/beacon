"""Normalisation & dedupe-key logic.

One company == one Lead, deduped across all sources on normalised company name +
website domain (§3). Domain is the strongest signal, so the key prefers it and
falls back to the normalised name when no site is known yet.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Common UK company-name legal suffixes / noise to strip before comparison.
_LEGAL_SUFFIXES = {
    "ltd",
    "limited",
    "llp",
    "plc",
    "llc",
    "inc",
    "co",
    "company",
    "uk",
    "the",
}
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation and legal suffixes, collapse whitespace."""
    lowered = name.lower().strip()
    # drop ampersand-style joiners and punctuation → spaces
    cleaned = _NON_ALNUM.sub(" ", lowered)
    tokens = [t for t in cleaned.split() if t and t not in _LEGAL_SUFFIXES]
    return " ".join(tokens)


def extract_domain(website: str | None) -> str | None:
    """Return the bare registrable host (lowercased, no www, no path) or None."""
    if not website:
        return None
    candidate = website.strip()
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = f"http://{candidate}"
    host = urlparse(candidate).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    host = host.split(":")[0]  # strip any port
    return host or None


def compute_dedupe_key(name: str, domain: str | None) -> str:
    """Stable per-lane dedupe key. Prefer domain; fall back to normalised name."""
    if domain:
        return f"domain:{domain}"
    return f"name:{normalize_name(name)}"
