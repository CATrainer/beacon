import pytest
from sqlalchemy import select

from app.models.enums import (
    ContactSource,
    EmailConfidence,
    EmailStatus,
    JobType,
    LeadStage,
    LeadStatus,
)
from app.models.job import Job
from app.models.lane import Lane
from app.models.lead import Contact, Email, Lead, Suppression
from app.services import sending


@pytest.fixture
def lane(db):
    lane = Lane(name="Send Lane", config={"sources": []})
    db.add(lane)
    db.commit()
    db.refresh(lane)
    return lane


def _queued_lead(db, lane, *, domain="acme.com", email="dm@acme.com",
                 confidence=EmailConfidence.HIGH):
    lead = Lead(
        lane_id=lane.id,
        company="Acme",
        domain=domain,
        website=f"https://{domain}",
        dedupe_key=f"domain:{domain}",
        stage=LeadStage.READY,
        status=LeadStatus.QUEUED,
        final_score=80.0,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    db.add(Email(lead_id=lead.id, touch_no=1, subject="s", body="b", status=EmailStatus.QUEUED))
    if email is not None:
        db.add(Contact(
            lead_id=lead.id, email=email, email_confidence=confidence,
            source=ContactSource.RESEARCH, is_primary=True,
        ))
    db.commit()
    db.refresh(lead)
    return lead


def _send_job(db):
    job = Job(type=JobType.SEND, params={"ignore_window": True})
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_send_creates_simulated_draft(db, lane):
    lead = _queued_lead(db, lane)
    counts = sending._run(db, _send_job(db))
    db.commit()
    db.refresh(lead)
    assert counts["drafted"] == 1
    assert counts["simulated"] is True
    email = db.scalar(select(Email).where(Email.lead_id == lead.id))
    assert email.status == EmailStatus.SENT
    assert email.gmail_draft_id.startswith("sim_")
    assert lead.status == LeadStatus.SENT


def test_send_skips_suppressed(db, lane):
    lead = _queued_lead(db, lane, domain="blocked.com", email="dm@blocked.com")
    db.add(Suppression(email_or_domain="blocked.com", reason="opt-out",
                       created_at=sending._now()))
    db.commit()
    counts = sending._run(db, _send_job(db))
    db.commit()
    db.refresh(lead)
    assert counts["suppressed"] == 1
    assert counts["drafted"] == 0
    assert lead.status == LeadStatus.SUPPRESSED


def test_send_skips_no_email(db, lane):
    _queued_lead(db, lane, email=None)
    counts = sending._run(db, _send_job(db))
    assert counts["no_email"] == 1 and counts["drafted"] == 0


def test_send_skips_low_confidence(db, lane):
    lead = _queued_lead(db, lane, confidence=EmailConfidence.LOW)
    counts = sending._run(db, _send_job(db))
    db.commit()
    email = db.scalar(select(Email).where(Email.lead_id == lead.id))
    assert counts["drafted"] == 0
    assert email.status == EmailStatus.QUEUED  # left for verification, not drafted


def test_suppression_api(client, auth_headers):
    created = client.post(
        "/api/suppression", json={"email_or_domain": "Spam.com", "reason": "junk"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    assert created.json()["email_or_domain"] == "spam.com"  # normalised
    dup = client.post(
        "/api/suppression", json={"email_or_domain": "spam.com"}, headers=auth_headers
    )
    assert dup.status_code == 409
    listed = client.get("/api/suppression", headers=auth_headers).json()
    assert any(s["email_or_domain"] == "spam.com" for s in listed)
    sid = created.json()["id"]
    assert client.delete(f"/api/suppression/{sid}", headers=auth_headers).status_code == 204


def test_sending_settings_api(client, auth_headers):
    got = client.get("/api/settings/sending", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["mode"] == "gmail_draft"
    upd = client.put(
        "/api/settings/sending", json={"daily_cap": 5, "identity": "x@heuricity.com"},
        headers=auth_headers,
    )
    assert upd.status_code == 200
    assert upd.json()["daily_cap"] == 5
    assert client.get("/api/settings/sending", headers=auth_headers).json()["daily_cap"] == 5


def test_pipeline_and_status_and_activity(client, auth_headers, db, lane):
    lead = _queued_lead(db, lane)
    pipe = client.get("/api/pipeline", headers=auth_headers).json()
    assert pipe["counts"].get("queued", 0) >= 1

    upd = client.patch(
        f"/api/leads/{lead.id}/status", json={"status": "call_booked", "note": "great call"},
        headers=auth_headers,
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "call_booked"

    acts = client.get(f"/api/leads/{lead.id}/activity", headers=auth_headers).json()
    assert any(a["type"] == "status_changed" for a in acts)


def test_gmail_status(client, auth_headers):
    r = client.get("/api/integrations/gmail/status", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is False
    assert body["configured"] is False  # no GMAIL_CLIENT_ID in tests
