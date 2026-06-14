"""Google Places adapter — best source for wealth/size signals (§3).

Text search per term × town. Pulls website, rating, review count and address —
the rating/review-count signals feed Stage-3 scoring. Catches private aesthetic
clinics that may register under broader CQC categories; cross-referenced with CQC
on domain/name during dedupe.
"""

from __future__ import annotations

import logging

from app.adapters.base import AdapterError, RawCandidate, SourceAdapter, register
from app.config import settings
from app.services.http import post_json

log = logging.getLogger(__name__)

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.primaryTypeDisplayName",
    ]
)


@register
class GooglePlacesAdapter(SourceAdapter):
    key = "google_places"
    fixture_file = "google_places.json"
    description = "Google Places text search — wealth/size signals (reviews, rating)."

    def available(self, source_params: dict) -> bool:
        return settings.google_places_enabled

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.google_places_api_key,
            "X-Goog-FieldMask": _FIELD_MASK,
        }

    def _fetch_live(self, source_params: dict, limit: int, lane_config: dict) -> list[RawCandidate]:
        terms = source_params.get("search_terms", []) or []
        towns = lane_config.get("town_list", []) or [None]
        if not terms:
            raise AdapterError("google_places: no search_terms configured for this lane")

        seen: set[str] = set()
        out: list[RawCandidate] = []

        for term in terms:
            for town in towns:
                if len(out) >= limit:
                    return out
                query = f"{term} in {town}" if town else term
                try:
                    data = post_json(
                        _SEARCH_URL,
                        json_body={"textQuery": query, "regionCode": "GB", "maxResultCount": 20},
                        headers=self._headers(),
                    )
                except Exception as exc:  # noqa: BLE001
                    raise AdapterError(f"places search '{query}' failed: {exc}") from exc

                for place in data.get("places", []):
                    place_id = place.get("id")
                    if not place_id or place_id in seen:
                        continue
                    seen.add(place_id)
                    name = (place.get("displayName") or {}).get("text") or "Unknown"
                    out.append(
                        RawCandidate(
                            company_name=name,
                            source_key=self.key,
                            website=place.get("websiteUri"),
                            address=place.get("formattedAddress"),
                            location=town,
                            source_ref=place_id,
                            raw_meta={
                                "rating": place.get("rating"),
                                "review_count": place.get("userRatingCount"),
                                "primary_type": (place.get("primaryTypeDisplayName") or {}).get(
                                    "text"
                                ),
                                "search_query": query,
                            },
                        )
                    )
                    if len(out) >= limit:
                        return out
        log.info("google_places: %d candidates", len(out))
        return out
