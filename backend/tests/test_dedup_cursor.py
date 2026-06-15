"""Dedup hardening + incremental-sourcing cursor tests."""

from datetime import UTC, datetime

from app.adapters import RawCandidate, get_adapter
from app.adapters import cqc as cqc_mod
from app.adapters import google_places as gp
from app.models.lane import Lane
from app.models.lead import Lead, SourceHit
from app.services import sourcing


def _lane(db):
    lane = Lane(name="Dedup Lane", config={"sources": []})
    db.add(lane)
    db.commit()
    db.refresh(lane)
    return lane


def _ingest(db, lane, company, website, source="cqc"):
    cand = RawCandidate(company_name=company, source_key=source, website=website)
    return sourcing._ingest_candidate(db, lane.id, cand, {}, {"created": 0, "merged": 0})


def test_name_only_then_domain_upgrades_same_lead(db):
    lane = _lane(db)
    # First sighting: no website → name-keyed lead.
    _ingest(db, lane, "Acme Dental Ltd", None)
    db.commit()
    # Later sighting from another source WITH a website → must upgrade, not duplicate.
    _ingest(db, lane, "Acme Dental", "https://acmedental.co.uk", source="google_places")
    db.commit()

    leads = db.query(Lead).filter(Lead.lane_id == lane.id).all()
    assert len(leads) == 1
    assert leads[0].domain == "acmedental.co.uk"
    assert leads[0].dedupe_key == "domain:acmedental.co.uk"


def test_domain_then_no_website_same_company_merges(db):
    lane = _lane(db)
    _ingest(db, lane, "Bright Smiles", "https://brightsmiles.co.uk")
    db.commit()
    # A no-website hit for the same company folds into the domain lead.
    _ingest(db, lane, "Bright Smiles Ltd", None, source="manual_paste")
    db.commit()
    assert db.query(Lead).filter(Lead.lane_id == lane.id).count() == 1


def test_fold_pre_existing_split(db):
    """A historical split (domain lead + separate name-only lead) is folded."""
    lane = _lane(db)
    dom = Lead(
        lane_id=lane.id, company="Clinic", domain="clinic.com", website="https://clinic.com",
        norm_name="clinic", dedupe_key="domain:clinic.com",
    )
    name_only = Lead(
        lane_id=lane.id, company="Clinic", norm_name="clinic", dedupe_key="name:clinic"
    )
    db.add_all([dom, name_only])
    db.commit()
    db.add(SourceHit(lead_id=name_only.id, source_key="cqc", raw_meta={},
                     fetched_at=datetime.now(UTC)))
    db.commit()

    # Ingesting a domain hit resolves to the domain lead and folds the name-only one.
    _ingest(db, lane, "Clinic", "https://clinic.com")
    db.commit()
    leads = db.query(Lead).filter(Lead.lane_id == lane.id).all()
    assert len(leads) == 1
    # The folded lead's source hit was reassigned to the survivor.
    assert db.query(SourceHit).filter(SourceHit.lead_id == leads[0].id).count() >= 1


def test_places_cursor_advances(monkeypatch):
    calls: list[str] = []

    def fake_post(url, *, json_body, headers):
        calls.append(json_body["textQuery"])
        return {"places": [{"id": f"p{len(calls)}", "displayName": {"text": "X"},
                            "websiteUri": "https://x.com"}]}

    monkeypatch.setattr(gp, "post_json", fake_post)
    adapter = get_adapter("google_places")
    cur: dict = {}
    lane_cfg = {"town_list": ["Leeds", "York"]}
    adapter._fetch_live({"search_terms": ["dentist"]}, 1, lane_cfg, cur)
    assert cur["combo_index"] == 1  # advanced past the first combo
    adapter._fetch_live({"search_terms": ["dentist"]}, 1, lane_cfg, cur)
    assert calls == ["dentist in Leeds", "dentist in York"]
    assert cur["combo_index"] == 0  # wrapped around


def test_cqc_cursor_advances(monkeypatch):
    def fake_get(url, *, params=None, headers=None):
        if url.endswith("/locations"):
            page = params["page"]
            return {"locations": [{"locationId": f"1-{page}-1"}], "totalPages": 10}
        return {"name": "Clinic", "website": "https://c.com",
                "gacServiceTypes": [{"description": "Dentist"}]}

    monkeypatch.setattr(cqc_mod, "get_json", fake_get)
    adapter = get_adapter("cqc")
    cur: dict = {}
    out = adapter._fetch_live({"service_types": ["Dentist"]}, 5, {}, cur)
    assert len(out) == 5
    assert cur["next_page"] == 6  # consumed pages 1–5, resume at 6
