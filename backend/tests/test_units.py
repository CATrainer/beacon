from app.adapters import get_adapter
from app.schemas.lane import QualificationRules
from app.services.dedupe import compute_dedupe_key, extract_domain, normalize_name
from app.services.qualification import qualify


def test_normalize_name_strips_legal_suffixes():
    assert normalize_name("Bridgewater Dental Ltd") == "bridgewater dental"
    assert normalize_name("The Park Lane Clinic Limited") == "park lane clinic"
    assert normalize_name("A&B Co.") == "a b"


def test_extract_domain():
    assert extract_domain("https://www.Example.com/path") == "example.com"
    assert extract_domain("example.co.uk") == "example.co.uk"
    assert extract_domain("http://sub.example.com:8080") == "sub.example.com"
    assert extract_domain(None) is None
    assert extract_domain("") is None


def test_dedupe_key_prefers_domain():
    assert compute_dedupe_key("Foo Ltd", "foo.com") == "domain:foo.com"
    assert compute_dedupe_key("Foo Bar Ltd", None) == "name:foo bar"


def test_qualify_requires_website():
    rules = QualificationRules()
    r = qualify(company="X", website=None, domain=None, rules=rules, suppressed=set())
    assert not r.passed and "website" in r.reason.lower()


def test_qualify_blocklist():
    rules = QualificationRules(chain_blocklist=["mydentist"])
    r = qualify(
        company="MyDentist Manchester",
        website="https://mydentist.example.com",
        domain="mydentist.example.com",
        rules=rules,
        suppressed=set(),
    )
    assert not r.passed and "blocklist" in r.reason.lower()


def test_qualify_suppression():
    rules = QualificationRules()
    r = qualify(
        company="Foo",
        website="https://foo.com",
        domain="foo.com",
        rules=rules,
        suppressed={"foo.com"},
    )
    assert not r.passed and "suppression" in r.reason.lower()


def test_qualify_passes_clean_lead():
    rules = QualificationRules()
    r = qualify(
        company="Good Clinic",
        website="https://goodclinic.com",
        domain="goodclinic.com",
        rules=rules,
        suppressed=set(),
    )
    assert r.passed and r.reason is None


def test_adapter_fixture_fallback():
    cqc = get_adapter("cqc")
    cands = cqc.fetch({}, 50, {}, force_fixtures=True)
    assert len(cands) >= 5
    assert all(c.source_key == "cqc" for c in cands)
    assert all(c.raw_meta.get("fixture") for c in cands)


def test_manual_paste_entries():
    mp = get_adapter("manual_paste")
    cands = mp.fetch(
        {"entries": [{"company_name": "Acme", "website": "https://acme.com"}]}, 50, {}
    )
    assert len(cands) == 1
    assert cands[0].company_name == "Acme"
