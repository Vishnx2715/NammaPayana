"""
Phase 1 FEAT-002 — Trip Ownership Tests.
Tests store-level ownership logic and the /api/trips/claim HTTP endpoint.
"""
import pytest
import uuid

from app import app
from services.trip_store import TripStore


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    return TripStore(db_path=str(tmp_path / "test.db"))


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    with app.test_client() as c:
        yield c
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["RATELIMIT_ENABLED"] = True


# ── Helpers ───────────────────────────────────────────────────────────────────

_DNA = {
    "start_city": "Bengaluru",
    "days": 2,
    "travellers": 2,
    "budget": {"amount": 6000, "scope": "total", "currency": "INR"},
    "style": "economical",
}


def _make_trip(store, user_id=None):
    return store.save_trip(dna=_DNA, itinerary={}, cost_summary={}, user_id=user_id)


# ── Store-level tests ─────────────────────────────────────────────────────────

def test_save_stamps_user_id_when_logged_in(store):
    """save_trip with a user_id should stamp that user_id on the stored row."""
    saved = _make_trip(store, user_id="uid-1")
    loaded = store.get_trip(saved["id"])
    assert loaded["user_id"] == "uid-1"


def test_save_guest_trip_has_no_user_id(store):
    """save_trip without a user_id should leave user_id as None."""
    saved = _make_trip(store)
    loaded = store.get_trip(saved["id"])
    assert loaded["user_id"] is None


def test_delete_trip_requires_owner_or_edit_token(store):
    """delete_trip with no user_id and no edit_token must raise PermissionError."""
    saved = _make_trip(store)
    with pytest.raises(PermissionError):
        store.delete_trip(saved["id"], edit_token="", user_id=None)


def test_owner_can_delete_without_edit_token(store):
    """The owning user can delete a trip without providing an edit_token."""
    saved = _make_trip(store, user_id="uid-owner")
    result = store.delete_trip(saved["id"], edit_token="", user_id="uid-owner")
    assert result is True
    assert store.get_trip(saved["id"]) is None


def test_other_user_cannot_delete_trip(store):
    """A different user_id must not be able to delete another user's trip."""
    saved = _make_trip(store, user_id="uid-owner")
    with pytest.raises(PermissionError):
        store.delete_trip(saved["id"], edit_token="", user_id="uid-other")


def test_claim_guest_trips_on_login(store):
    """claim_trips should stamp user_id on guest trips matching the given edit tokens."""
    saved = _make_trip(store)  # guest trip
    token = saved["edit_token"]

    count = store.claim_trips(edit_tokens=[token], user_id="uid-claimer")
    assert count == 1

    loaded = store.get_trip(saved["id"])
    assert loaded["user_id"] == "uid-claimer"


# ── HTTP-level test for /api/trips/claim ─────────────────────────────────────

def test_claim_endpoint_requires_login(client):
    """POST /api/trips/claim without a session must return 401."""
    res = client.post("/api/trips/claim", json={"edit_tokens": []})
    assert res.status_code == 401
    data = res.get_json()
    assert data["ok"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_claim_endpoint_returns_claimed_count(client):
    """POST /api/trips/claim with a valid session must return {ok: true, data: {claimed: N}}."""
    # Inject a session directly to avoid hitting rate-limited auth endpoints
    # that prior tests in the suite may have exhausted.
    fake_user_id = str(uuid.uuid4())
    with client.session_transaction() as sess:
        sess["user_id"] = fake_user_id

    res = client.post("/api/trips/claim", json={"edit_tokens": ["nonexistent-token"]})
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert "claimed" in data["data"]
    assert data["data"]["claimed"] == 0  # nonexistent token claims nothing
