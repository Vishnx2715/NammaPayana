import pytest

def test_get_profile_requires_login(client):
    resp = client.get("/api/auth/profile")
    assert resp.status_code == 401

def test_update_profile_requires_login(client):
    resp = client.patch("/api/auth/profile", json={"full_name": "Test"})
    assert resp.status_code == 401

def test_delete_account_requires_login(client):
    resp = client.delete("/api/auth/account", json={"password": "test"})
    assert resp.status_code == 401

def test_export_data_requires_login(client):
    resp = client.get("/api/auth/export")
    assert resp.status_code == 401

def test_profile_update_and_export_flow(client):
    """Full flow: register → update profile → export → verify data."""
    import uuid
    unique = uuid.uuid4().hex[:8]
    username = f"proftest{unique}"
    email = f"proftest{unique}@example.com"
    # Register
    r = client.post("/api/auth/register", json={
        "username": username, "email": email,
        "password": "securepassword99", "full_name": "Profile User"
    })
    assert r.status_code == 201
    # Login
    client.post("/api/auth/login", json={
        "identifier": email, "password": "securepassword99"
    })
    # Get profile
    resp = client.get("/api/auth/profile")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["full_name"] == "Profile User"
    # Update profile
    upd = client.patch("/api/auth/profile", json={"full_name": "Updated Name", "home_city": "Mysuru"})
    assert upd.status_code == 200
    assert upd.get_json()["data"]["full_name"] == "Updated Name"
    # Export
    exp = client.get("/api/auth/export")
    assert exp.status_code == 200
    data = exp.get_json()["data"]
    assert "user" in data
    assert "trips" in data
    assert "exported_at" in data

def test_safety_endpoint_returns_data(client):
    """Destinations with safety_info should return it via /safety endpoint."""
    resp = client.get("/api/destinations/jog_falls/safety")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["destination_id"] == "jog_falls"
    assert "emergency_number" in data
    assert "disclaimer" in data

def test_safety_endpoint_404_for_missing(client):
    resp = client.get("/api/destinations/nonexistent_dest/safety")
    assert resp.status_code == 404

def test_architecture_md_has_auth_section():
    import pathlib
    arch = (pathlib.Path(__file__).parent.parent / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "Authentication Architecture" in arch or "authentication" in arch.lower()
