from app.models.enums import ContactSource, EmailConfidence, LeadStage
from app.models.lane import Lane
from app.models.lead import Lead, SourceHit
from app.schemas.lane import FinalWeights
from app.services import ai, research


def test_candidate_page_urls():
    urls = research.candidate_page_urls("clinic.com")
    assert urls[0] == "https://clinic.com"
    assert "https://clinic.com/about" in urls
    assert "https://clinic.com/contact" in urls


def test_synthesize_brief_uses_ai(monkeypatch):
    canned = {
        "summary": "A premium dental clinic.",
        "specialisms": "implants",
        "high_ticket_services": ["dental implants"],
        "decision_maker_name": "Jane Smith",
        "decision_maker_role": "Principal Dentist",
        "human_hook": "Opened a second location",
        "marketing_sophistication": "high",
        "linkedin_url": None,
    }
    monkeypatch.setattr(ai, "complete_json", lambda **kw: (canned, 0.02))
    data, cost = research.synthesize_brief(
        "Clinic", "https://clinic.com", {"https://clinic.com": "<html>hi</html>"}, ["Jane Smith"]
    )
    assert data["decision_maker_name"] == "Jane Smith"
    assert cost == 0.02


def test_research_lead_integration(db, monkeypatch):
    lane = Lane(name="R Lane", config={"sources": []})
    db.add(lane)
    db.commit()
    db.refresh(lane)

    lead = Lead(
        lane_id=lane.id,
        company="Detail Co",
        website="https://detailco.com",
        domain="detailco.com",
        dedupe_key="domain:detailco.com",
        stage=LeadStage.SCORED,
        fit_score=50.0,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    db.add(
        SourceHit(
            lead_id=lead.id,
            source_key="companies_house",
            raw_meta={"directors": ["Jane Smith"]},
            fetched_at=research.datetime.now(research.UTC),
        )
    )
    db.commit()
    db.refresh(lead)

    # Avoid network: fake page fetch with an email + linkedin in the HTML.
    html = (
        "<html>Contact us at info@detailco.com. "
        '<a href="https://linkedin.com/company/detailco">us</a></html>'
    )
    monkeypatch.setattr(research, "gather_pages", lambda website: {"https://detailco.com": html})

    cost = research.research_lead(db, lead, FinalWeights())
    db.commit()
    db.refresh(lead)

    # Brief created with deterministically-extracted facts.
    assert lead.research_briefs
    brief = lead.research_briefs[-1]
    assert "info@detailco.com" in brief.emails_found
    assert "linkedin.com/company/detailco" in (brief.linkedin_url or "")

    # Contact resolved from the published email → HIGH/RESEARCH.
    primary = next(c for c in lead.contacts if c.is_primary)
    assert primary.email == "info@detailco.com"
    assert primary.email_confidence == EmailConfidence.HIGH
    assert primary.source == ContactSource.RESEARCH

    # Stage advanced; reachability set; final recomputed.
    assert lead.stage == LeadStage.ENRICHED
    assert lead.reachability_score == 90.0
    assert lead.final_score is not None
    assert cost == 0.0  # anthropic disabled in tests → no LLM spend
