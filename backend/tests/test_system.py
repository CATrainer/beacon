def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_status_reports_integrations(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    # With an empty .env, optional integrations are off but the shape is stable.
    assert body["ai"]["anthropic"] is False
    assert body["sources"]["manual_paste"] is True
    assert body["sources"]["atol"] is True
    assert isinstance(body["geo_engines"], list)
