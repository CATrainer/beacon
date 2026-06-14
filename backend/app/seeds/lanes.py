"""Default Clinics & Travel lane configurations (§3).

These encode the design doc's verified top-of-funnel sources and lane-weighted
signals. They are starting points — the operator tunes everything in the UI.
"""

from __future__ import annotations

from app.schemas.lane import (
    FinalWeights,
    GeoConfig,
    LaneConfig,
    QualificationRules,
    ScoringWeights,
    SourceConfig,
)

CLINICS_LANE = {
    "name": "Clinics",
    "description": "Private dental, aesthetic, and cosmetic-medical clinics (England).",
    "config": LaneConfig(
        sources=[
            SourceConfig(
                key="cqc",
                enabled=True,
                params={
                    # Isolate dentists & clinics by regulated activity / service type.
                    "service_types": ["Dentist", "Clinic"],
                    "regulated_activities": ["Treatment of disease, disorder or injury"],
                },
            ),
            SourceConfig(
                key="google_places",
                enabled=True,
                params={
                    "search_terms": [
                        "dental clinic",
                        "dental implants",
                        "Invisalign provider",
                        "aesthetic clinic",
                        "cosmetic clinic",
                    ]
                },
            ),
            SourceConfig(key="companies_house", enabled=True, params={}),  # director enrichment
            SourceConfig(key="directory_ingest", enabled=True, params={"urls": []}),
            SourceConfig(key="manual_paste", enabled=True, params={}),
        ],
        qualification=QualificationRules(
            require_website=True,
            min_incorporation_years=2,
            chain_blocklist=["mydentist", "bupa dental", "{my}dentist", "portman dental"],
            max_locations=None,
        ),
        scoring=ScoringWeights(
            signals={
                "high_ticket_services": 30,   # implants / Invisalign / aesthetics keyword scan
                "review_count": 20,            # size proxy
                "rating": 10,                  # >=4.0
                "multiple_locations": 10,
                "booking_funnel": 15,          # marketing-spend signal
                "blog": 5,
                "tracked_ads": 10,
            }
        ),
        final_weights=FinalWeights(fit=0.5, gap=0.3, reachability=0.2),
        geo=GeoConfig(
            query_templates=[
                "best dentist for {service} in {location}",
                "where can I get {service} in {location}",
                "top rated {service} clinic near {location}",
            ]
        ),
        town_list=[
            "Manchester",
            "Leeds",
            "Birmingham",
            "Bristol",
            "Liverpool",
            "Sheffield",
        ],
    ).model_dump(),
}

TRAVEL_LANE = {
    "name": "Travel",
    "description": "Specialist / luxury tour operators (UK).",
    "config": LaneConfig(
        sources=[
            SourceConfig(key="atol", enabled=True, params={}),  # CAA ATOL data download
            SourceConfig(
                key="directory_ingest",
                enabled=True,
                params={
                    # AITO member directory — highest-signal for specialist/luxury.
                    "urls": ["https://www.aito.com/find-a-specialist-tour-operator"],
                    "membership_boost": {"aito": 15},
                },
            ),
            SourceConfig(key="google_places", enabled=True, params={"search_terms": []}),
            SourceConfig(key="companies_house", enabled=True, params={}),
            SourceConfig(key="manual_paste", enabled=True, params={}),
        ],
        qualification=QualificationRules(
            require_website=True,
            min_incorporation_years=2,
            chain_blocklist=["tui", "jet2holidays", "on the beach", "loveholidays"],
            max_locations=None,
        ),
        scoring=ScoringWeights(
            signals={
                "premium_positioning": 30,      # tailor-made, not budget/package
                "membership_aito": 20,          # specialist/luxury fit boost
                "membership_atol_abta": 10,
                "bespoke_language": 20,
                "review_signals": 20,
            }
        ),
        final_weights=FinalWeights(fit=0.5, gap=0.3, reachability=0.2),
        geo=GeoConfig(
            query_templates=[
                "best luxury {destination} tour operator",
                "specialist {destination} travel company UK",
                "tailor-made {destination} holidays",
            ]
        ),
        town_list=[],
    ).model_dump(),
}

DEFAULT_LANES = [CLINICS_LANE, TRAVEL_LANE]
