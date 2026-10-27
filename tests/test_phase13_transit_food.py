"""
Phase 13 tests: transit hub and food place data files + API endpoints.
"""
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# File-level tests (no Flask client needed)
# ---------------------------------------------------------------------------

def test_transit_hubs_json_exists_or_stub():
    path = REPO / "data" / "transit_hubs.json"
    assert path.exists(), "data/transit_hubs.json must exist (stub is OK)"


def test_transit_hubs_json_structure():
    path = REPO / "data" / "transit_hubs.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "attribution" in data, "transit_hubs.json must have 'attribution'"
    assert "items" in data, "transit_hubs.json must have 'items'"
    assert isinstance(data["items"], list), "'items' must be a list"
    assert data.get("count") == len(data["items"]), "'count' must equal len(items)"


def test_food_json_exists_or_stub():
    path = REPO / "data" / "food.json"
    assert path.exists(), "data/food.json must exist (stub is OK)"


def test_food_json_structure():
    path = REPO / "data" / "food.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "attribution" in data, "food.json must have 'attribution'"
    assert "items" in data, "food.json must have 'items'"
    assert isinstance(data["items"], list), "'items' must be a list"
    assert data.get("count") == len(data["items"]), "'count' must equal len(items)"


# ---------------------------------------------------------------------------
# API endpoint tests (require Flask test client)
# ---------------------------------------------------------------------------

def test_get_transit_endpoint_returns_200(client):
    resp = client.get("/api/transit")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "data" in body
    assert "count" in body["data"]
    assert "items" in body["data"]
    assert "attribution" in body["data"]


def test_get_transit_near_filter(client):
    resp = client.get("/api/transit?near=mysuru_palace")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    for item in body["data"]["items"]:
        assert item.get("nearest_destination_id") == "mysuru_palace"


def test_get_food_endpoint_returns_200(client):
    resp = client.get("/api/food")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "data" in body
    assert "count" in body["data"]
    assert "items" in body["data"]
    assert "attribution" in body["data"]


def test_get_food_diet_filter(client):
    resp = client.get("/api/food?diet=veg")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    for item in body["data"]["items"]:
        assert item.get("diet") == "veg"
