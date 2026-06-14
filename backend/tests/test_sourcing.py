"""End-to-end Stage 1–2 pipeline test on fixtures (deterministic, no network)."""

from app.models.enums import JobType, LeadStage
from app.models.job import Job
from app.models.lane import Lane
from app.models.lead import Lead
from app.schemas.lane import LaneConfig, ScoringWeights, SourceConfig
from app.services import sourcing


def _clinics_lane(db):
    config = LaneConfig(
        sources=[
            SourceConfig(key="cqc", enabled=True, params={}),
            SourceConfig(key="google_places", enabled=True, params={"search_terms": ["x"]}),
            SourceConfig(key="manual_paste", enabled=True, params={}),
        ],
        scoring=ScoringWeights(signals={"review_count": 20}),
    )
    lane = Lane(name="Clinics Test", description="", config=config.model_dump())
    db.add(lane)
    db.commit()
    db.refresh(lane)
    return lane


def test_full_sourcing_pipeline_on_fixtures(db):
    lane = _clinics_lane(db)
    job = Job(type=JobType.SOURCE_RUN, lane_id=lane.id, params={"force_fixtures": True})
    db.add(job)
    db.commit()

    result = sourcing._run(db, job)

    # CQC fixture (6) + Places fixture (5) = 11 candidates; 3 domains overlap.
    assert result["candidates"] == 11
    assert result["created"] == 8
    assert result["merged"] == 3
    # Every lead has a website except "Steel City" (no site) → 1 rejection.
    assert result["qualified"] == 7
    assert result["rejected"] == 1

    leads = db.query(Lead).filter(Lead.lane_id == lane.id).all()
    assert len(leads) == 8

    # Merge check: the shared domain lead carries hits from BOTH sources.
    bridgewater = next(
        x for x in leads if x.domain == "bridgewaterdental.example.com"
    )
    keys = {h.source_key for h in bridgewater.source_hits}
    assert keys == {"cqc", "google_places"}
    # Survivors are scored in the same run, so the stage advances past QUALIFIED.
    assert bridgewater.stage == LeadStage.SCORED
    assert bridgewater.fit_score is not None

    # The websiteless lead is rejected with a reason.
    steel = next(x for x in leads if "steel city" in x.company.lower())
    assert steel.stage == LeadStage.REJECTED
    assert steel.reject_reason and "website" in steel.reject_reason.lower()


def test_rerun_is_idempotent_on_dedupe_key(db):
    lane = _clinics_lane(db)
    for _ in range(2):
        job = Job(type=JobType.SOURCE_RUN, lane_id=lane.id, params={"force_fixtures": True})
        db.add(job)
        db.commit()
        sourcing._run(db, job)

    # Same unique companies — no duplicates created on the second run.
    leads = db.query(Lead).filter(Lead.lane_id == lane.id).all()
    assert len(leads) == 8
