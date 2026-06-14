def test_login_success_and_me(client, user):
    resp = client.post(
        "/api/auth/login",
        data={"username": "caleb@heuricity.com", "password": "password123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "caleb@heuricity.com"


def test_login_wrong_password(client, user):
    resp = client.post(
        "/api/auth/login",
        data={"username": "caleb@heuricity.com", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/lanes").status_code == 401
    assert client.get("/api/auth/me").status_code == 401
