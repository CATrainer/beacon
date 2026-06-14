from app.models.enums import GeoHookType, LeadStage
from app.models.lane import Lane
from app.models.lead import GeoCheck, Lead
from app.schemas.lane import FinalWeights, GeoConfig, LaneConfig
from app.services import geo


def test_severity_and_hook():
    sev, hook = geo.severity_and_hook(named=False, recommended=False)
    assert hook == GeoHookType.ABSENCE and sev == 90.0
    sev, hook = geo.severity_and_hook(named=True, recommended=False)
    assert hook == GeoHookType.WEAK_PRESENCE and sev == 60.0
    sev, hook = geo.severity_and_hook(named=True, recommended=True)
    assert hook == GeoHookType.NO_GAP and sev == 10.0


def _lane_and_lead(db):
    config = LaneConfig(
        geo=GeoConfig(query_templates=["best {service} in {location}", "top clinic {location}"]),
        final_weights=FinalWeights(),
    )
    lane = Lane(name="GEO Lane", config=config.model_dump())
    db.add(lane)
    db.commit()
    db.refresh(lane)
    lead = Lead(
        lane_id=lane.id,
        company="Acme Clinic",
        domain="acme.com",
        website="https://acme.com",
        location="Leeds",
        dedupe_key="domain:acme.com",
        stage=LeadStage.ENRICHED,
        fit_score=70.0,
        reachability_score=90.0,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lane, lead, config


def test_build_queries_fills_templates(db):
    _, lead, config = _lane_and_lead(db)
    qs = geo.build_queries(lead, config)
    assert "best  in Leeds" in qs[0]  # no service known → blank
    assert "top clinic Leeds" in qs[1]


def test_geo_check_fixture_sets_gap_score(db):
    _, lead, config = _lane_and_lead(db)
    cost = geo.geo_check_lead(db, lead, config, force_fixtures=True)
    db.commit()
    db.refresh(lead)

    rows = db.query(GeoCheck).filter(GeoCheck.lead_id == lead.id).all()
    assert len(rows) == 2  # 1 fixture "engine" × 2 queries
    assert all(r.engine == "fixture" for r in rows)
    assert lead.gap_score == 90.0  # absence
    assert rows[0].hook_type == GeoHookType.ABSENCE
    # final now blends fit + gap + reachability
    assert lead.final_score is not None
    assert cost == 0.0


def test_geo_check_no_engines_is_noop(db):
    _, lead, config = _lane_and_lead(db)
    cost = geo.geo_check_lead(db, lead, config, force_fixtures=False)
    db.commit()
    db.refresh(lead)
    rows = db.query(GeoCheck).filter(GeoCheck.lead_id == lead.id).all()
    assert len(rows) == 1 and rows[0].engine == "none"
    assert lead.gap_score is None  # untouched — no fabricated gap
    assert cost == 0.0
