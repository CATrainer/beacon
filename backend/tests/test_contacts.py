from app.models.enums import ContactSource, EmailConfidence
from app.services.contacts import extract_emails, resolve_contact, split_name
from app.services.email_resolver import NullResolver

R = NullResolver()


def test_extract_emails_filters_assets():
    text = "Reach us at Info@Clinic.com or hello@clinic.com. logo@2x.png ignored"
    emails = extract_emails(text)
    assert "info@clinic.com" in emails
    assert "hello@clinic.com" in emails
    assert all(not e.endswith(".png") for e in emails)


def test_split_name():
    assert split_name("Dr Jane Smith") == ("jane", "smith")
    assert split_name("Jane") == ("jane", None)
    assert split_name(None) == (None, None)


def test_published_email_matching_dm_is_high():
    rc = resolve_contact(
        domain="clinic.com",
        decision_maker_name="Jane Smith",
        emails_found=["info@clinic.com", "jane.smith@clinic.com"],
        linkedin_url=None,
        resolver=R,
    )
    assert rc.email == "jane.smith@clinic.com"
    assert rc.email_confidence == EmailConfidence.HIGH
    assert rc.source == ContactSource.RESEARCH


def test_generic_published_email_is_high():
    rc = resolve_contact(
        domain="clinic.com",
        decision_maker_name=None,
        emails_found=["info@clinic.com"],
        linkedin_url=None,
        resolver=R,
    )
    assert rc.email == "info@clinic.com"
    assert rc.email_confidence == EmailConfidence.HIGH
    assert rc.source == ContactSource.RESEARCH


def test_pattern_inference_medium_when_built_not_published():
    # Personal sample on the domain + DM name → infer pattern, build DM address.
    rc = resolve_contact(
        domain="clinic.com",
        decision_maker_name="Mark Owner",
        emails_found=["alice.jones@clinic.com"],
        linkedin_url=None,
        resolver=R,
    )
    assert rc.source == ContactSource.PATTERN
    assert rc.email == "mark.owner@clinic.com"
    assert rc.email_confidence == EmailConfidence.MEDIUM


def test_no_email_falls_back_to_linkedin_first():
    rc = resolve_contact(
        domain="clinic.com",
        decision_maker_name="Jane Smith",
        emails_found=[],
        linkedin_url="https://linkedin.com/in/janesmith",
        resolver=R,
    )
    assert rc.email is None
    assert rc.email_confidence is None
    assert rc.source == ContactSource.LINKEDIN_FIRST
    assert rc.linkedin_url == "https://linkedin.com/in/janesmith"
