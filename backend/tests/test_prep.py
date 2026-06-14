from datetime import UTC, datetime

import pytest

from app.config import settings
from app.models.enums import EmailStatus, LeadStage, LeadStatus
from app.models.lane import Lane
from app.models.lead import Email, GeoCheck, Lead, ResearchBrief
from app.schemas.lane import GeoConfig, LaneConfig
from app.services import ai
from app.services.drafting import draft_emails, first_name_of, propose_call_slots

CANNED = {
    "touch1": {"subject": "Your AI visibility", "body": "Hi Jane, ... within 90 days. Caleb"},
    "touch2": {"subject": "Following up", "body": "Hi Jane, re the screenshot ... Caleb"},
    "touch3": {"subject": "Closing the loop", "body": "Hi Jane, last note ... Caleb"},
}


def test_first_name_strips_titles():
    assert first_name_of("Dr Jabir Kazi") == "Jabir"
    assert first_name_of("Jane Smith") == "Jane"
    assert first_name_of("Prof. Alan Turing") == "Alan"
    assert first_name_of(None) == "there"


def test_propose_call_slots_two_weekdays():
    slots = propose_call_slots()
    assert len(slots) == 2
    assert all("at" in s for s in slots)


@pytest.fixture
def prepped_lead(db):
    lane = Lane(
        name="Prep Lane",
        config=LaneConfig(
            geo=GeoConfig(query_templates=["best {service} in {location}"]),
        ).model_dump(),
    )
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
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    db.add(ResearchBrief(
        lead_id=lead.id,
        decision_maker_name="Jane Smith",
        high_ticket_services=["dental implants"],
        emails_found=[],
        linkedin_url=None,
        pages_fetched=[],
        created_at=datetime.now(UTC),
    ))
    db.add(GeoCheck(
        lead_id=lead.id, engine="fixture", query="best dental implants in Leeds",
        competitors=["Rival Dental", "City Smiles"], cited_sources=[],
        checked_at=datetime.now(UTC),
    ))
    db.commit()
    db.refresh(lead)
    return lane, lead


def test_draft_emails_uses_ai(db, prepped_lead, monkeypatch):
    _, lead = prepped_lead
    monkeypatch.setattr(ai, "complete_json", lambda **kw: (CANNED, 0.05))
    touches, cost = draft_emails(lead)
    assert set(touches) == {"touch1", "touch2", "touch3"}
    assert cost == 0.05


def test_audit_queries_endpoint(client, auth_headers, prepped_lead):
    _, lead = prepped_lead
    r = client.get(f"/api/leads/{lead.id}/audit-queries", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["queries"] == ["best dental implants in Leeds"]
    assert "ChatGPT" in body["engines"]


def test_evidence_upload_and_detail(client, auth_headers, prepped_lead, monkeypatch, tmp_path):
    _, lead = prepped_lead
    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    r = client.post(
        f"/api/leads/{lead.id}/evidence",
        data={"query": "best dental implants in Leeds", "engine": "ChatGPT"},
        files={"file": ("shot.png", b"\x89PNG\r\n", "image/png")},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["screenshot_path"].startswith(f"/uploads/{lead.id}/")

    detail = client.get(f"/api/leads/{lead.id}", headers=auth_headers).json()
    assert len(detail["evidence"]) == 1


def test_draft_patch_and_approve_flow(client, auth_headers, db, prepped_lead, monkeypatch):
    _, lead = prepped_lead
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")  # re-enable for this test
    monkeypatch.setattr(ai, "complete_json", lambda **kw: (CANNED, 0.05))

    # Generate drafts
    r = client.post(f"/api/leads/{lead.id}/draft", headers=auth_headers)
    assert r.status_code == 200, r.text
    emails = r.json()
    assert [e["touch_no"] for e in emails] == [1, 2, 3]
    touch1_id = emails[0]["id"]

    # Edit touch-1 inline
    upd = client.patch(
        f"/api/emails/{touch1_id}",
        json={"body": "Hi Jane, edited body. Caleb"},
        headers=auth_headers,
    )
    assert upd.status_code == 200
    assert upd.json()["body"] == "Hi Jane, edited body. Caleb"

    # Approve → queued
    appr = client.post(f"/api/leads/{lead.id}/approve", headers=auth_headers)
    assert appr.status_code == 200
    assert appr.json()["status"] == "queued"

    db.expire_all()
    refreshed = db.get(Lead, lead.id)
    assert refreshed.status == LeadStatus.QUEUED
    assert refreshed.stage == LeadStage.READY


def test_approve_requires_touch1(client, auth_headers, prepped_lead):
    _, lead = prepped_lead
    r = client.post(f"/api/leads/{lead.id}/approve", headers=auth_headers)
    assert r.status_code == 409


def test_cannot_edit_non_draft_email(client, auth_headers, db, prepped_lead):
    _, lead = prepped_lead
    email = Email(lead_id=lead.id, touch_no=1, subject="s", body="b", status=EmailStatus.SENT)
    db.add(email)
    db.commit()
    db.refresh(email)
    r = client.patch(f"/api/emails/{email.id}", json={"body": "x"}, headers=auth_headers)
    assert r.status_code == 409
