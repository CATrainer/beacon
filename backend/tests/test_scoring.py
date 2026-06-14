from app.models.enums import JobType, LeadStage
from app.models.job import Job
from app.models.lane import Lane
from app.models.lead import Lead, SourceHit
from app.schemas.lane import FinalWeights, LaneConfig, ScoringWeights, SourceConfig
from app.services import sourcing
from app.services.scoring import compute_final, compute_fit


def test_compute_final_blend():
    # Only fit present → final == fit.
    assert compute_final(fit=80.0, gap=None, reachability=None, weights=FinalWeights()) == 80.0
    # fit + gap with default weights (0.5 / 0.3): (0.5*80 + 0.3*40) / 0.8 = 65.0
    assert compute_final(fit=80.0, gap=40.0, reachability=None, weights=FinalWeights()) == 65.0
    # nothing present → None
    assert compute_final(fit=None, gap=None, reachability=None, weights=FinalWeights()) is None


def _lead_with_reviews(rating: float, count: int) -> Lead:
    lead = Lead(company="X", website=None, dedupe_key="name:x")
    lead.source_hits = [
        SourceHit(source_key="google_places", raw_meta={"rating": rating, "review_count": count})
    ]
    return lead


def test_compute_fit_rewards_reviews_and_rating():
    weights = ScoringWeights(signals={"review_count": 20, "rating": 10})
    high, _ = compute_fit(_lead_with_reviews(4.8, 412), weights, fetch=False)
    low, _ = compute_fit(_lead_with_reviews(3.4, 22), weights, fetch=False)
    assert high > low
    assert 0 <= low <= 100 and 0 <= high <= 100


def test_compute_fit_breakdown_shape():
    weights = ScoringWeights(signals={"review_count": 20, "rating": 10})
    fit, breakdown = compute_fit(_lead_with_reviews(4.5, 100), weights, fetch=False)
    assert "signals" in breakdown
    assert set(breakdown["signals"]) == {"review_count", "rating"}
    for sig in breakdown["signals"].values():
        assert {"weight", "strength", "contribution"} <= set(sig)
    assert breakdown["context"]["review_count"] == 100


def test_sourcing_scores_qualified_leads(db):
    config = LaneConfig(
        sources=[
            SourceConfig(key="cqc", enabled=True, params={}),
            SourceConfig(key="google_places", enabled=True, params={"search_terms": ["x"]}),
        ],
        scoring=ScoringWeights(signals={"review_count": 20, "rating": 10}),
        final_weights=FinalWeights(),
    )
    lane = Lane(name="Score Lane", config=config.model_dump())
    db.add(lane)
    db.commit()
    db.refresh(lane)

    job = Job(type=JobType.SOURCE_RUN, lane_id=lane.id, params={"force_fixtures": True})
    db.add(job)
    db.commit()
    result = sourcing._run(db, job)

    assert result["scored"] == result["qualified"]

    scored = (
        db.query(Lead)
        .filter(Lead.lane_id == lane.id, Lead.stage == LeadStage.SCORED)
        .all()
    )
    assert scored, "expected some scored leads"
    for lead in scored:
        assert lead.fit_score is not None
        # Only fit exists at this stage → final == fit.
        assert lead.final_score == lead.fit_score

    # The high-review Places lead outscores the low-review one.
    by_domain = {x.domain: x for x in scored}
    quay = by_domain.get("quaystreetskin.example.com")   # 4.9 / 526
    budget = by_domain.get("budgetsmiles.example.com")    # 3.4 / 22
    assert quay and budget
    assert quay.fit_score > budget.fit_score
