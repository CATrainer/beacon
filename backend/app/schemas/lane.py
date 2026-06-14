"""Lane schemas, including the validated ``LaneConfig`` shape.

The config is what makes a Lane *data, not code*: sources, qualification rules,
scoring weights, the final-score blend, the GEO query templates, and the town
list. The operator edits all of it in the UI.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SourceConfig(BaseModel):
    """One configured source adapter for the lane."""

    key: str = Field(description="Adapter registry key, e.g. 'cqc', 'google_places'.")
    enabled: bool = True
    # Adapter-specific params: search_terms, directory_urls, sic_codes, service_types, etc.
    params: dict = Field(default_factory=dict)


class QualificationRules(BaseModel):
    """Stage-2 hard qualification rules (§4). Cheap, no AI."""

    require_website: bool = True
    min_incorporation_years: int | None = 2
    chain_blocklist: list[str] = Field(default_factory=list)
    max_locations: int | None = None  # over this → downgrade, not kill


class ScoringWeights(BaseModel):
    """Stage-3 fit/wealth signal weights (§3 / §5).

    ``signals`` maps a signal key (e.g. 'high_ticket_services', 'review_count')
    to a weight. Sub-scores are stored per lead so the UI can show *why*.
    """

    model_config = ConfigDict(extra="allow")
    signals: dict[str, float] = Field(default_factory=dict)


class FinalWeights(BaseModel):
    """Blend for the final lead score = fit × gap × reachability (§5)."""

    fit: float = 0.5
    gap: float = 0.3
    reachability: float = 0.2


class GeoConfig(BaseModel):
    """Stage-4b buyer-intent query templates. Placeholders: {company}, {location}, {service}."""

    query_templates: list[str] = Field(default_factory=list)


class LaneConfig(BaseModel):
    """Full validated config blob stored on ``lanes.config``."""

    model_config = ConfigDict(extra="forbid")

    sources: list[SourceConfig] = Field(default_factory=list)
    qualification: QualificationRules = Field(default_factory=QualificationRules)
    scoring: ScoringWeights = Field(default_factory=ScoringWeights)
    final_weights: FinalWeights = Field(default_factory=FinalWeights)
    geo: GeoConfig = Field(default_factory=GeoConfig)
    town_list: list[str] = Field(default_factory=list)


class LaneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    is_active: bool = True
    config: LaneConfig = Field(default_factory=LaneConfig)


class LaneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    is_active: bool | None = None
    config: LaneConfig | None = None


class LaneOut(BaseModel):
    id: int
    name: str
    description: str
    is_active: bool
    config: LaneConfig
    lead_count: int = 0

    model_config = {"from_attributes": True}
