"""
Phase 0B — Authentication Security Tests.
Each test reproduces a specific attack vector and verifies the fix.
Tests are ordered by vulnerability number.

IMPORTANT: The client fixture sets WTF_CSRF_ENABLED=False because Flask-WTF 1.3
does not disable CSRF enforcement when TESTING=True — only WTF_CSRF_ENABLED=False
disables the before_request hook that checks CSRF on all POST requests.

RATELIMIT_ENABLED=False is set in the standard fixture so that other tests do not
consume the per-IP quota. The rate-limit test manages its own TESTING/RATELIMIT
config flags.
"""
import os
import time
import uuid

import jwt as pyjwt
import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    with app.test_client() as c:
        yield c
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["RATELIMIT_ENABLED"] = True


# ── VULN 1: google-check without valid token ──────────────────────────────────

def test_google_check_no_token_returns_401(client, monkeypatch):
    """Calling google-check with no Authorization header must return 401."""
    monkeypatch.setattr("config.SUPABASE_JWT_SECRET", "test_secret_32_chars_long_xxxxxx")
    res = client.post("/api/auth/google-check", json={})
    assert res.status_code == 401
    data = res.get_json()
    assert data["ok"] is False
    assert data["error"]["code"] in ("MISSING_TOKEN", "UNAUTHORIZED", "SERVICE_UNAVAILABLE")


def test_google_check_missing_jwt_secret_returns_503(client, monkeypatch):
    """google-check must return 503 when SUPABASE_JWT_SECRET is not configured."""
    monkeypatch.setattr("config.SUPABASE_JWT_SECRET", "")
    res = client.post(
        "/api/auth/google-check",
        headers={"Authorization": "Bearer sometoken"},
        json={}
    )
    assert res.status_code == 503
    data = res.get_json()
    assert data["ok"] is False
    assert data["error"]["code"] in ("AUTH_NOT_CONFIGURED", "SERVICE_UNAVAILABLE")


def test_google_check_forged_token_rejected(client, monkeypatch):
    """A JWT signed with a wrong secret must be rejected with 401."""
    monkeypatch.setattr("config.SUPABASE_JWT_SECRET", "correct_secret_32_chars_long_xxx")
    forged = pyjwt.encode(
        {
            "sub": "uid-abc",
            "email": "victim@example.com",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        "wrong_secret_key_32_chars_xxxxxxx",
        algorithm="HS256",
    )
    res = client.post(
        "/api/auth/google-check",
        headers={"Authorization": f"Bearer {forged}"},
        json={}
    )
    assert res.status_code == 401
    data = res.get_json()
    assert data["ok"] is False
    assert data["error"]["code"] == "INVALID_TOKEN"


# ── VULN 2: Bearer user-id rejected by /api/auth/me ──────────────────────────

def test_bearer_user_id_rejected_by_me(client):
    """
    GET /api/auth/me with a UUID in the Bearer header must return 401.
    Previously, this acted as a password-free login.
    """
    fake_user_id = str(uuid.uuid4())
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {fake_user_id}"})
    assert res.status_code == 401
    data = res.get_json()
    assert data["ok"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"


# ── VULN 3: Demo user absent when ENABLE_DEMO_USER not set ───────────────────

def test_demo_user_absent_without_enable_flag(monkeypatch, tmp_path):
    """Demo user must NOT be seeded when ENABLE_DEMO_USER is unset."""
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("ENABLE_DEMO_USER", raising=False)
    from services.user_store import UserStore
    store = UserStore(db_path=str(tmp_path / "test.db"))
    store.init_db()
    user = store.get_user_by_email("demo@nammapayana.in")
    assert user is None, "Demo user must not exist when ENABLE_DEMO_USER is not set to '1'"


def test_demo_user_absent_in_production(monkeypatch, tmp_path):
    """Demo user must NEVER be seeded when FLASK_ENV=production."""
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("ENABLE_DEMO_USER", "1")
    from services.user_store import UserStore
    store = UserStore(db_path=str(tmp_path / "test.db"))
    store.init_db()
    user = store.get_user_by_email("demo@nammapayana.in")
    assert user is None, "Demo user must not exist in production even if ENABLE_DEMO_USER=1"


# ── VULN 4: Enumeration responses are identical ───────────────────────────────

def test_login_unregistered_and_wrong_password_same_response(client):
    """
    Login with unregistered email and login with wrong password must return
    identical status code and error code (no enumeration).
    """
    res_unreg = client.post("/api/auth/login", json={
        "identifier": "does_not_exist_9999@test.com",
        "password": "somepassword123"
    })
    uniq = uuid.uuid4().hex[:6]
    client.post("/api/auth/register", json={
        "username": f"enum_test_{uniq}",
        "email": f"enum_{uniq}@test.com",
        "full_name": "Enum Test User",
        "password": "strongpassword99",
    })
    res_wrong_pwd = client.post("/api/auth/login", json={
        "identifier": f"enum_{uniq}@test.com",
        "password": "completely_wrong_password",
    })
    assert res_unreg.status_code == res_wrong_pwd.status_code == 401
    assert res_unreg.get_json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert res_wrong_pwd.get_json()["error"]["code"] == "INVALID_CREDENTIALS"


# ── VULN 5: Rate limiting triggers 429 ───────────────────────────────────────

def test_rate_limit_triggers_on_login(client):
    """
    Sending repeated login requests from the same IP must eventually trigger a 429.
    (limit is 5/minute; TESTING must be False and RATELIMIT_ENABLED must be True)
    """
    from app import limiter
    app.config["TESTING"] = False
    app.config["RATELIMIT_ENABLED"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        responses = []
        for _ in range(7):
            r = client.post("/api/auth/login", json={
                "identifier": "bruteforce_rl@test.com",
                "password": "attempt"
            })
            responses.append(r.status_code)
        assert 429 in responses, f"Expected a 429, got: {responses}"
        # Verify the 429 envelope
        r429 = client.post("/api/auth/login", json={
            "identifier": "bruteforce_rl@test.com", "password": "x"
        })
        if r429.status_code == 429:
            data = r429.get_json()
            assert data["ok"] is False
            assert data["error"]["code"] == "RATE_LIMITED"
    finally:
        # Reset limiter counters so subsequent tests are not affected
        try:
            limiter.reset()
        except Exception:
            pass
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["RATELIMIT_ENABLED"] = False


# ── VULN 7: Session cookie flags ─────────────────────────────────────────────

def test_session_cookie_has_httponly_flag(client):
    """The session cookie configuration must have HttpOnly flag enabled."""
    # The Flask test client may not expose Set-Cookie headers directly.
    # Verify the app config — the authoritative source.
    assert app.config.get("SESSION_COOKIE_HTTPONLY") is True, \
        "SESSION_COOKIE_HTTPONLY must be True in app config"
    assert app.config.get("SESSION_COOKIE_SAMESITE") in ("Lax", "Strict"), \
        "SESSION_COOKIE_SAMESITE must be Lax or Strict"


# ── VULN 8: CSRF token endpoint works ────────────────────────────────────────

def test_csrf_token_endpoint_returns_token(client):
    """The /api/csrf-token endpoint must return a valid token string."""
    res = client.get("/api/csrf-token")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert "csrf_token" in data["data"]
    assert len(data["data"]["csrf_token"]) > 10


# ── VULN 10: password_hash never returned ────────────────────────────────────

def test_password_hash_never_in_api_response(client):
    """No auth API response must ever include password_hash."""
    uniq = uuid.uuid4().hex[:6]
    reg_res = client.post("/api/auth/register", json={
        "username": f"hashcheck_{uniq}",
        "email": f"hash_{uniq}@test.com",
        "full_name": "Hash Check User",
        "password": "strongpassword99",
    })
    assert reg_res.status_code == 201
    assert "password_hash" not in reg_res.get_json().get("data", {})

    login_res = client.post("/api/auth/login", json={
        "identifier": f"hash_{uniq}@test.com",
        "password": "strongpassword99",
    })
    assert login_res.status_code == 200
    assert "password_hash" not in login_res.get_json().get("data", {})

    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert "password_hash" not in me_res.get_json().get("data", {})


# ── VULN 6: Password strength enforced via REST endpoint ─────────────────────

def test_csrf_enforced_on_login_when_enabled(client):
    """POST /api/auth/login without X-CSRFToken must return 400 or 403 when CSRF is enabled."""
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["RATELIMIT_ENABLED"] = False
    try:
        res = client.post(
            "/api/auth/login",
            json={"identifier": "anyone@test.com", "password": "doesnotmatter"},
            content_type="application/json"
        )
        assert res.status_code in (400, 403), (
            f"Expected 400 or 403 when CSRF token is missing, got {res.status_code}"
        )
    finally:
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["RATELIMIT_ENABLED"] = False


# ── VULN 6: Password strength enforced via REST endpoint ─────────────────────

def test_weak_password_rejected_at_register_endpoint(client):
    """
    POST /api/auth/register with a short password must return 400 VALIDATION_FAILED.
    This tests the integration path: auth_register() -> create_user() -> validate_password_strength().
    """
    uniq = uuid.uuid4().hex[:6]
    # Short password (< 10 chars) — should be rejected
    res_short = client.post("/api/auth/register", json={
        "username": f"wptest_{uniq}",
        "email": f"wptest_{uniq}@test.com",
        "full_name": "Weak Password Test",
        "password": "short",
    })
    assert res_short.status_code == 400
    data_short = res_short.get_json()
    assert data_short["ok"] is False
    assert data_short["error"]["code"] == "VALIDATION_FAILED"

    # Common password — should be rejected
    res_common = client.post("/api/auth/register", json={
        "username": f"wptest2_{uniq}",
        "email": f"wptest2_{uniq}@test.com",
        "full_name": "Common Password Test",
        "password": "1234567890",
    })
    assert res_common.status_code == 400
    data_common = res_common.get_json()
    assert data_common["ok"] is False
    assert data_common["error"]["code"] == "VALIDATION_FAILED"
