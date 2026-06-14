"""ATOL adapter — CAA ATOL-holder data (travel primary, §3).

The CAA publishes searchable ATOL-holder data via a data-download facility. The
majority of UK air-inclusive tour operators must hold an ATOL and have been
CAA-inspected, so this is a near-complete, pre-qualified universe of real
operators. There is no API key; point the lane's source at the published file via
``params.data_url``. Without a URL the adapter uses fixtures.
"""

from __future__ import annotations

import csv
import io
import logging

import httpx

from app.adapters.base import AdapterError, RawCandidate, SourceAdapter, register
from app.config import settings

log = logging.getLogger(__name__)

# Reasonable defaults; override per-lane via params if the published columns differ.
_NAME_COLS = ["Trading Name", "TradingName", "Trading name", "Company Name", "Name"]
_WEBSITE_COLS = ["Website", "Web", "URL", "Web Address"]
_LOCATION_COLS = ["Town", "City", "Location", "Post Town"]


def _first_col(row: dict, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in row and row[c]:
            return str(row[c]).strip()
    return None


@register
class ATOLAdapter(SourceAdapter):
    key = "atol"
    fixture_file = "atol.json"
    description = "CAA ATOL-holder data download (UK tour operators)."

    def available(self, source_params: dict) -> bool:
        # Live fetch only when a data URL is configured; otherwise fixtures.
        return bool(source_params.get("data_url"))

    def _fetch_live(self, source_params: dict, limit: int, lane_config: dict) -> list[RawCandidate]:
        data_url = source_params["data_url"]
        name_cols = source_params.get("name_columns") or _NAME_COLS
        website_cols = source_params.get("website_columns") or _WEBSITE_COLS
        location_cols = source_params.get("location_columns") or _LOCATION_COLS
        try:
            resp = httpx.get(
                data_url, headers={"User-Agent": settings.user_agent}, timeout=60.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AdapterError(f"ATOL download failed: {exc}") from exc

        reader = csv.DictReader(io.StringIO(resp.text))
        out: list[RawCandidate] = []
        for row in reader:
            if len(out) >= limit:
                break
            name = _first_col(row, name_cols)
            if not name:
                continue
            out.append(
                RawCandidate(
                    company_name=name,
                    source_key=self.key,
                    website=_first_col(row, website_cols),
                    location=_first_col(row, location_cols),
                    source_ref=_first_col(row, ["ATOL Number", "ATOL", "Licence Number"]),
                    raw_meta={"atol_holder": True},
                )
            )
        log.info("ATOL: %d candidates", len(out))
        return out
