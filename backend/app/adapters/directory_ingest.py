"""Directory-ingest adapter — the "any web list becomes a source" pressure valve.

Operator supplies URLs (member lists, association directories, "best X in town"
listicles). We fetch each page (robots-respected, rate-limited) and use a cheap
LLM call to extract company names + websites + locations as strict JSON. This is
how the top-of-funnel keeps growing without code changes (§3).
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from app.adapters.base import RawCandidate, SourceAdapter, register
from app.config import settings
from app.services import ai
from app.services.http import fetch_html

log = logging.getLogger(__name__)

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "company_name": {"type": "string"},
                    "website": {"type": ["string", "null"]},
                    "location": {"type": ["string", "null"]},
                },
                "required": ["company_name", "website", "location"],
            },
        }
    },
    "required": ["companies"],
}

_SYSTEM = (
    "You extract a clean list of companies from a directory or listicle web page. "
    "Return only real businesses listed on the page (not nav links, ads, or the "
    "site's own brand). For each, give company_name, website (absolute URL or null), "
    "and location (town/city or null). Do not invent entries."
)


@register
class DirectoryIngestAdapter(SourceAdapter):
    key = "directory_ingest"
    fixture_file = "directory_ingest.json"
    description = "Ingest any member list / directory / listicle URL via LLM extraction."

    def available(self, source_params: dict) -> bool:
        return settings.anthropic_enabled and bool(source_params.get("urls"))

    def _page_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        # Cap to keep token cost bounded; directories are link-dense near the top.
        return text[:20000]

    def _fetch_live(
        self, source_params: dict, limit: int, lane_config: dict, cursor: dict
    ) -> list[RawCandidate]:
        urls = source_params.get("urls", []) or []
        membership_boost = source_params.get("membership_boost", {})
        out: list[RawCandidate] = []

        for url in urls:
            if len(out) >= limit:
                break
            html = fetch_html(url)
            if not html:
                log.info("directory_ingest: could not fetch %s (robots or error)", url)
                continue
            data, cost = ai.complete_json(
                model=settings.model_cheap,
                system=_SYSTEM,
                user=f"Page URL: {url}\n\nPage text:\n{self._page_text(html)}",
                schema=_SCHEMA,
                max_tokens=4096,
            )
            for c in data.get("companies", []):
                if len(out) >= limit:
                    break
                name = (c.get("company_name") or "").strip()
                if not name:
                    continue
                out.append(
                    RawCandidate(
                        company_name=name,
                        source_key=self.key,
                        website=c.get("website"),
                        location=c.get("location"),
                        source_ref=url,
                        raw_meta={
                            "directory_url": url,
                            "membership_boost": membership_boost,
                            "extraction_cost_usd": round(cost, 6),
                        },
                    )
                )
        log.info("directory_ingest: %d candidates from %d urls", len(out), len(urls))
        return out
