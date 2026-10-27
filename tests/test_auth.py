"""
Unit tests for Namma Payana UserStore and Auth REST API endpoints.
"""
import pytest
import tempfile
import os
from services.user_store import UserStore
from app import app

@pytest.fixture
def test_user_store():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db = f.name
    store = UserStore(db_path=temp_db)
    yield store
    if os.path.exists(temp_db):
        try:
            os.remove(temp_db)
        except Exception:
            pass

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    with app.test_client() as client:
        yield client
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["RATELIMIT_ENABLED"] = True

def test_user_creation_and_auth(test_user_store):
    user = test_user_store.create_user(
        username="ananya",
        email="ananya@karnataka.org",
        full_name="Ananya Hegde",
        password="secretpassword123",
        persona="Nature & Wildlife",
        home_city="Mangaluru"
    )
    assert user["id"] is not None
    assert user["username"] == "ananya"
    assert user["email"] == "ananya@karnataka.org"
    assert "password_hash" not in user

    # Authenticate with email
    auth_user = test_user_store.authenticate("ananya@karnataka.org", "secretpassword123")
    assert auth_user is not None
    assert auth_user["full_name"] == "Ananya Hegde"

    # Authenticate with username
    auth_user2 = test_user_store.authenticate("ananya", "secretpassword123")
    assert auth_user2 is not None

    # Invalid password
    bad = test_user_store.authenticate("ananya", "wrongpassword")
    assert bad is None

def test_duplicate_user_validation(test_user_store):
    test_user_store.create_user(
        username="sharath",
        email="sharath@payana.in",
        full_name="Sharath Rao",
        password="password123"
    )
    with pytest.raises(ValueError, match="Registration failed|already exists|taken"):
        test_user_store.create_user(
            username="sharath2",
            email="sharath@payana.in",
            full_name="Duplicate Email",
            password="password123"
        )

def test_api_auth_flow(client):
    import uuid
    uniq = uuid.uuid4().hex[:6]
    test_user = f"kavya_{uniq}"
    test_email = f"kavya_{uniq}@travel.in"

    # 1. Register new user
    reg_resp = client.post("/api/auth/register", json={
        "username": test_user,
        "email": test_email,
        "full_name": "Kavya Murthy",
        "password": "mypassword2026",
        "persona": "Heritage Explorer",
        "home_city": "Mysuru"
    })
    assert reg_resp.status_code == 201
    data = reg_resp.get_json()
    assert data["ok"] is True

    # 2. Get me endpoint while session is active
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.get_json()["data"]["email"] == test_email

    # 3. Logout
    logout_resp = client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    # 4. Me endpoint after logout should be 401
    me_resp2 = client.get("/api/auth/me")
    assert me_resp2.status_code == 401

    # 5. Login
    login_resp = client.post("/api/auth/login", json={
        "identifier": test_email,
        "password": "mypassword2026"
    })
    assert login_resp.status_code == 200
    assert login_resp.get_json()["data"]["full_name"] == "Kavya Murthy"

def test_unregistered_login_is_rejected(client):
    # Attempting to sign in with an unregistered identifier must fail with INVALID_CREDENTIALS
    res = client.post("/api/auth/login", json={
        "identifier": "nonexistent_person@travel.in",
        "password": "somepassword123"
    })
    assert res.status_code == 401
    data = res.get_json()
    assert data["ok"] is False
    assert data["error"]["code"] == "INVALID_CREDENTIALS"

def test_google_check_unregistered_is_rejected(client, monkeypatch):
    import time
    import jwt as pyjwt
    jwt_secret = "test_secret_32_chars_long_xxxxxx"
    monkeypatch.setattr("config.SUPABASE_JWT_SECRET", jwt_secret)
    token = pyjwt.encode(
        {"sub": "uid-unreg", "email": "unregistered_google_user@gmail.com", "email_verified": True, "aud": "authenticated", "exp": int(time.time()) + 3600},
        jwt_secret,
        algorithm="HS256",
    )
    res = client.post("/api/auth/google-check", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404
    data = res.get_json()
    assert data["ok"] is False
    assert data["registered"] is False
    assert data["error"]["code"] == "NOT_REGISTERED"

def test_google_check_registered_is_accepted(client, monkeypatch):
    import time
    import uuid
    import jwt as pyjwt
    jwt_secret = "test_secret_32_chars_long_xxxxxx"
    monkeypatch.setattr("config.SUPABASE_JWT_SECRET", jwt_secret)
    uniq = uuid.uuid4().hex[:6]
    email = f"google_verified_{uniq}@gmail.com"
    reg = client.post("/api/auth/register", json={
        "username": f"guser_{uniq}",
        "email": email,
        "full_name": "Google Traveler",
        "password": "password123"
    })
    assert reg.status_code == 201

    token = pyjwt.encode(
        {"sub": f"uid-{uniq}", "email": email, "email_verified": True, "aud": "authenticated", "exp": int(time.time()) + 3600},
        jwt_secret,
        algorithm="HS256",
    )
    res = client.post("/api/auth/google-check", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["registered"] is True
    assert data["data"]["email"] == email


