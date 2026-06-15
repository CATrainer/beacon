"""Manual-paste adapter — operator pastes names/URLs directly (§3). Always useful.

Entries are passed via ``params.entries`` (the API's manual-add endpoint fills
this), each ``{company_name, website?, location?}``. No fixtures: with no entries
it simply yields nothing.
"""

from __future__ import annotations

from app.adapters.base import RawCandidate, SourceAdapter, register


@register
class ManualPasteAdapter(SourceAdapter):
    key = "manual_paste"
    fixture_file = ""
    description = "Operator-pasted company names / URLs."

    def available(self, source_params: dict) -> bool:
        return True  # data is supplied directly; never needs fixtures

    def _fetch_live(
        self, source_params: dict, limit: int, lane_config: dict, cursor: dict
    ) -> list[RawCandidate]:
        entries = source_params.get("entries", []) or []
        out: list[RawCandidate] = []
        for e in entries[:limit]:
            name = (e.get("company_name") or "").strip()
            if not name:
                continue
            out.append(
                RawCandidate(
                    company_name=name,
                    source_key=self.key,
                    website=e.get("website"),
                    location=e.get("location"),
                    raw_meta={"manual": True},
                )
            )
        return out
