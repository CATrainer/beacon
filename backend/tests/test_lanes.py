def test_lane_crud_flow(client, auth_headers):
    # Create
    payload = {
        "name": "Test Lane",
        "description": "A lane for tests",
        "config": {
            "sources": [{"key": "manual_paste", "enabled": True, "params": {}}],
            "qualification": {"require_website": True, "min_incorporation_years": 2},
            "scoring": {"signals": {"review_count": 20}},
            "final_weights": {"fit": 0.5, "gap": 0.3, "reachability": 0.2},
            "geo": {"query_templates": ["best {service} in {location}"]},
            "town_list": ["Leeds"],
        },
    }
    created = client.post("/api/lanes", json=payload, headers=auth_headers)
    assert created.status_code == 201, created.text
    lane = created.json()
    assert lane["name"] == "Test Lane"
    assert lane["config"]["scoring"]["signals"]["review_count"] == 20
    lane_id = lane["id"]

    # Duplicate name rejected
    dup = client.post("/api/lanes", json=payload, headers=auth_headers)
    assert dup.status_code == 409

    # List
    listed = client.get("/api/lanes", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["id"] == lane_id for item in listed.json())

    # Update config
    upd = client.patch(
        f"/api/lanes/{lane_id}",
        json={"description": "updated", "config": {**payload["config"], "town_list": ["York"]}},
        headers=auth_headers,
    )
    assert upd.status_code == 200
    assert upd.json()["description"] == "updated"
    assert upd.json()["config"]["town_list"] == ["York"]

    # Delete (no leads attached)
    deleted = client.delete(f"/api/lanes/{lane_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/lanes/{lane_id}", headers=auth_headers).status_code == 404


def test_lane_config_rejects_unknown_keys(client, auth_headers):
    bad = {
        "name": "Bad Lane",
        "config": {"sources": [], "nonsense_field": 1},
    }
    resp = client.post("/api/lanes", json=bad, headers=auth_headers)
    assert resp.status_code == 422  # LaneConfig has extra="forbid"


def test_empty_queue(client, auth_headers):
    resp = client.get("/api/leads", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
