"""
Integration tests for Namma Payana Flask REST API endpoints and data persistence across restart.
"""
import pytest
import json
import os
from app import app
from services.trip_store import TripStore

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["data"]["status"] == "healthy"
    assert data["data"]["destinations_count"] >= 20

def test_get_destinations(client):
    res = client.get("/api/destinations")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["data"]["count"] >= 20

    # Filter by region
    res_reg = client.get("/api/destinations?region=North%20Karnataka")
    data_reg = res_reg.get_json()
    assert data_reg["ok"] is True
    assert all(d["region"] == "North Karnataka" for d in data_reg["data"]["destinations"])

def test_get_destination_detail(client):
    res = client.get("/api/destinations/mysuru_palace")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["data"]["id"] == "mysuru_palace"
    assert data["data"]["district"] == "Mysuru"

    res_missing = client.get("/api/destinations/unknown_place_123")
    assert res_missing.status_code == 404

def test_trip_generation_api(client):
    payload = {
        "start_city": "Bengaluru",
        "days": 3,
        "travellers": 2,
        "budget": {"amount": 8000, "scope": "total", "currency": "INR"},
        "style": "economical",
        "interests": ["heritage", "food"],
        "pace": "relaxed",
        "transport": "bus"
    }
    res = client.post("/api/trips/generate", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert "itinerary" in data["data"]
    assert "budget" in data["data"]
    assert "feasibility" in data["data"]
    assert data["data"]["itinerary"]["days_count"] == 3

def test_trip_validation_api(client):
    payload = {
        "dna": {
            "start_city": "Bengaluru",
            "days": 2,
            "travellers": 2,
            "budget": {"amount": 6000, "scope": "total", "currency": "INR"},
            "style": "economical"
        },
        "itinerary": {"days": [], "total_distance_km": 100.0}
    }
    res = client.post("/api/trips/validate", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert "budget" in data["data"]
    assert "feasibility" in data["data"]

def test_trip_save_and_persistence_across_instances(tmp_path):
    test_db = str(tmp_path / "test_persist.db")
    store1 = TripStore(db_path=test_db)

    dna = {
        "start_city": "Mysuru",
        "days": 2,
        "travellers": 1,
        "budget": {"amount": 5000, "scope": "total", "currency": "INR"},
        "style": "economical"
    }
    itin = {"days": []}
    cost = {"total_cost": 3200.0}

    saved = store1.save_trip(dna, itin, cost)
    trip_id = saved["id"]
    edit_token = saved["edit_token"]

    # Re-initialize store from disk (simulating restart)
    store2 = TripStore(db_path=test_db)
    loaded = store2.get_trip(trip_id)
    assert loaded is not None
    assert loaded["id"] == trip_id
    assert loaded["dna"]["start_city"] == "Mysuru"
    assert loaded["cost_summary"]["total_cost"] == 3200.0

    # Test duplication
    dup = store2.duplicate_trip(trip_id)
    assert dup["id"] != trip_id
    dup_loaded = store2.get_trip(dup["id"])
    assert dup_loaded["dna"]["start_city"] == "Mysuru"

    # Test deletion
    deleted = store2.delete_trip(trip_id, edit_token)
    assert deleted is True
    assert store2.get_trip(trip_id) is None

def test_phrases_api(client):
    res = client.get("/api/phrases?scenario=food")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["data"]["count"] > 0
    assert all(p["scenario"] == "food" for p in data["data"]["phrases"])

    # Search query
    res_search = client.get("/api/phrases?q=idli")
    data_search = res_search.get_json()
    assert data_search["ok"] is True
    assert data_search["data"]["count"] >= 1

def test_list_trips_api(client):
    res = client.get("/api/trips")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert "trips" in data["data"]
    assert "count" in data["data"]

