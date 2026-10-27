"""
Phase 1 Security Tests.
Covers: non-dict body rejection, JourneyDNA list validators, translate length cap,
UUID trip_id validation, CSP header with nonce, X-XSS-Protection absent, HSTS absent in non-production.
"""
import os
import pytest

from app import app
from services.validation import JourneyDNA
from pydantic import ValidationError


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    with app.test_client() as c:
        yield c
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["RATELIMIT_ENABLED"] = True


def test_generate_trip_list_body_returns_400(client):
    """POST /api/trips/generate with a JSON array body must return 400 INVALID_BODY."""
    res = client.post("/api/trips/generate", json=[1, 2, 3])
    assert res.status_code == 400
    data = res.get_json()
    assert data["ok"] is False
    assert data["error"]["code"] == "INVALID_BODY"


def test_auth_login_list_body_returns_400(client):
    """POST /api/auth/login with a JSON array body must return 400 INVALID_BODY."""
    res = client.post("/api/auth/login", json=[1, 2, 3])
    assert res.status_code == 400
    data = res.get_json()
    assert data["ok"] is False
    assert data["error"]["code"] == "INVALID_BODY"


def test_journey_dna_rejects_oversized_interests():
    """JourneyDNA with 11 interests must raise ValidationError."""
    with pytest.raises(ValidationError):
        JourneyDNA(
            start_city="Bengaluru",
            days=2,
            travellers=1,
            budget={"amount": "5000", "scope": "total"},
            interests=["item"] * 11,
        )


def test_journey_dna_rejects_bad_start_date():
    """JourneyDNA with start_date='not-a-date' must raise ValidationError."""
    with pytest.raises(ValidationError):
        JourneyDNA(
            start_city="Bengaluru",
            days=2,
            travellers=1,
            budget={"amount": "5000", "scope": "total"},
            start_date="not-a-date",
        )


def test_translate_text_too_long_returns_400(client):
    """POST /api/translate with text > 300 chars must return 400 TEXT_TOO_LONG."""
    long_text = "a" * 301
    res = client.post("/api/translate", json={"text": long_text})
    assert res.status_code == 400
    data = res.get_json()
    assert data["ok"] is False
    assert data["error"]["code"] == "TEXT_TOO_LONG"


def test_invalid_trip_id_returns_400(client):
    """GET /api/trips/not-a-uuid must return 400 INVALID_ID."""
    res = client.get("/api/trips/not-a-uuid")
    assert res.status_code == 400
    data = res.get_json()
    assert data["ok"] is False
    assert data["error"]["code"] == "INVALID_ID"


def test_csp_header_present(client):
    """GET / must return a Content-Security-Policy header containing a nonce- value."""
    res = client.get("/")
    assert res.status_code == 200
    assert "Content-Security-Policy" in res.headers
    assert "nonce-" in res.headers["Content-Security-Policy"]


def test_x_xss_protection_absent(client):
    """GET / must NOT return an X-XSS-Protection header."""
    res = client.get("/")
    assert "X-XSS-Protection" not in res.headers


def test_hsts_absent_in_non_production(client, monkeypatch):
    """GET / in non-production must NOT return Strict-Transport-Security."""
    monkeypatch.setenv("FLASK_ENV", "development")
    res = client.get("/")
    assert "Strict-Transport-Security" not in res.headers
