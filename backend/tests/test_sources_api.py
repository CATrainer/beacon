from datetime import UTC, datetime

import pytest

from app.models.enums import LeadStage, LeadStatus
from app.models.lane import Lane
from app.models.lead import Lead


@pytest.fixture
def lane(db):
    lane = Lane(name="API Lane", description="", config={"sources": []})
    db.add(lane)
    db.commit()
    db.refresh(lane)
    return lane


def test_list_adapters(client, auth_headers):
    resp = client.get("/api/adapters", headers=auth_headers)
    assert resp.status_code == 200
    keys = {a["key"] for a in resp.json()}
    assert {"cqc", "google_places", "atol", "directory_ingest", "manual_paste"} <= keys


def test_trigger_source_run_creates_job(client, auth_headers, lane, monkeypatch):
    async def _fake_enqueue(job_id: int) -> bool:
        return True  # pretend Redis accepted it; no inline execution

    monkeypatch.setattr("app.api.sources.enqueue_source_job", _fake_enqueue)

    resp = client.post(
        f"/api/lanes/{lane.id}/source",
        json={"force_fixtures": True, "limit_per_source": 10},
        headers=auth_headers,
    )
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["type"] == "source_run"
    assert job["status"] == "queued"
    assert job["lane_id"] == lane.id

    got = client.get(f"/api/jobs/{job['id']}", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["id"] == job["id"]


def test_override_rejected_lead(client, auth_headers, db, lane):
    lead = Lead(
        lane_id=lane.id,
        company="Rejected Co",
        dedupe_key="name:rejected co",
        stage=LeadStage.REJECTED,
        status=LeadStatus.REJECTED,
        reject_reason="No website on record",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    resp = client.post(f"/api/leads/{lead.id}/override", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stage"] == "qualified"
    assert body["reject_overridden"] is True
    assert body["reject_reason"] is None


def test_override_non_rejected_conflicts(client, auth_headers, db, lane):
    lead = Lead(
        lane_id=lane.id,
        company="Fine Co",
        dedupe_key="name:fine co",
        stage=LeadStage.QUALIFIED,
        status=LeadStatus.QUALIFIED,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    resp = client.post(f"/api/leads/{lead.id}/override", headers=auth_headers)
    assert resp.status_code == 409


def test_lead_detail_includes_source_hits(client, auth_headers, db, lane):
    from app.models.lead import SourceHit

    lead = Lead(
        lane_id=lane.id,
        company="Detail Co",
        domain="detail.com",
        website="https://detail.com",
        dedupe_key="domain:detail.com",
        stage=LeadStage.QUALIFIED,
        status=LeadStatus.QUALIFIED,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    db.add(
        SourceHit(
            lead_id=lead.id,
            source_key="cqc",
            source_ref="1-1",
            raw_meta={"x": 1},
            fetched_at=datetime.now(UTC),
        )
    )
    db.commit()

    resp = client.get(f"/api/leads/{lead.id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["company"] == "Detail Co"
    assert len(body["source_hits"]) == 1
    assert body["source_hits"][0]["source_key"] == "cqc"
