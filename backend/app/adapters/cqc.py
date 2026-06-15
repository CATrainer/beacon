"""CQC adapter — the clinics goldmine (§3).

The Care Quality Commission publishes every regulated location in England via an
authenticated REST API. CQC registration means the entity is real, regulated,
located and operating — higher signal than Companies House. We list locations,
then pull each location's detail for its website + address + service types, and
keep those matching the lane's configured service types (e.g. Dentist / Clinic).

Note: CQC records carry a website where the provider published one, but NOT email
addresses — emails come later from the research agent (§3/§4a). Data is under the
Open Government Licence; attribute CQC when used.
"""

from __future__ import annotations

import logging

from app.adapters.base import AdapterError, RawCandidate, SourceAdapter, register
from app.config import settings
from app.services.http import get_json

log = logging.getLogger(__name__)

_BASE = "https://api.service.cqc.org.uk/public/v1"


@register
class CQCAdapter(SourceAdapter):
    key = "cqc"
    fixture_file = "cqc.json"
    description = "CQC-regulated locations (dentists & clinics, England)."

    def available(self, source_params: dict) -> bool:
        return settings.cqc_enabled

    def _headers(self) -> dict:
        return {"Ocp-Apim-Subscription-Key": settings.cqc_subscription_key}

    def _matches(self, detail: dict, wanted: list[str]) -> bool:
        if not wanted:
            return True
        wanted_lc = {w.lower() for w in wanted}
        haystack: list[str] = []
        for st in detail.get("gacServiceTypes", []) or []:
            haystack.append(str(st.get("description", "")).lower())
            haystack.append(str(st.get("name", "")).lower())
        haystack.append(str(detail.get("type", "")).lower())
        return any(w in h for w in wanted_lc for h in haystack if h)

    def _fetch_live(
        self, source_params: dict, limit: int, lane_config: dict, cursor: dict
    ) -> list[RawCandidate]:
        wanted = source_params.get("service_types", []) or []
        out: list[RawCandidate] = []
        # Resume from the saved page so each run pulls new records (incremental).
        page = int(cursor.get("next_page", 1))
        per_page = 200
        # Bound detail calls so a run can't fan out unboundedly (rate-limited 1/s).
        max_details = max(limit * 6, 60)
        details_done = 0
        total_pages = None

        while len(out) < limit and details_done < max_details:
            try:
                listing = get_json(
                    f"{_BASE}/locations",
                    params={"page": page, "perPage": per_page},
                    headers=self._headers(),
                )
            except Exception as exc:  # noqa: BLE001
                raise AdapterError(f"CQC list page {page} failed: {exc}") from exc

            locations = listing.get("locations", [])
            if not locations:
                page = 0  # past the end (or stale cursor) → wrap to 1 next run
                break

            for loc in locations:
                if len(out) >= limit or details_done >= max_details:
                    break
                location_id = loc.get("locationId")
                if not location_id:
                    continue
                details_done += 1
                try:
                    detail = get_json(
                        f"{_BASE}/locations/{location_id}", headers=self._headers()
                    )
                except Exception as exc:  # noqa: BLE001
                    log.info("CQC detail %s failed: %s", location_id, exc)
                    continue

                if not self._matches(detail, wanted):
                    continue

                town = detail.get("postalAddressTownCity") or detail.get("region")
                postcode = detail.get("postalCode")
                addr_parts = [
                    detail.get("postalAddressLine1"),
                    detail.get("postalAddressLine2"),
                    town,
                    postcode,
                ]
                address = ", ".join(p for p in addr_parts if p)
                gac = [st.get("description") for st in (detail.get("gacServiceTypes") or [])]
                acts = [ra.get("name") for ra in (detail.get("regulatedActivities") or [])]

                out.append(
                    RawCandidate(
                        company_name=detail.get("name") or loc.get("locationName") or "Unknown",
                        source_key=self.key,
                        website=detail.get("website"),
                        address=address or None,
                        location=town,
                        source_ref=location_id,
                        raw_meta={
                            "provider_id": detail.get("providerId"),
                            "gac_service_types": gac,
                            "regulated_activities": acts,
                            "postcode": postcode,
                        },
                    )
                )

            total_pages = listing.get("totalPages")
            if total_pages and page >= total_pages:
                page = 0  # will wrap to 1 below — start over next run
                break
            page += 1

        # Save resume point for the next run; wrap to page 1 when the register ends.
        cursor["next_page"] = page if page >= 1 else 1
        if total_pages:
            cursor["total_pages"] = total_pages
        log.info(
            "CQC: %d candidates after scanning %d details; next_page=%s",
            len(out), details_done, cursor["next_page"],
        )
        return out
