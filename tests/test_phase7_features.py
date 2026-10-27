import pytest, pathlib, json
REPO = pathlib.Path(__file__).parent.parent

# Use the shared client fixture from conftest.py

def test_share_link_requires_ownership(client):
    """Cannot get share link for a non-existent trip."""
    import uuid
    fake_id = str(uuid.uuid4())
    resp = client.post(f"/api/trips/{fake_id}/share", json={})
    assert resp.status_code in (404, 403)

def test_shared_trip_not_found_returns_404(client):
    resp = client.get("/api/shared/nonexistent-token-xyz")
    assert resp.status_code == 404

def test_ics_export_not_found_returns_404(client):
    import uuid
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/trips/{fake_id}/export/ics")
    assert resp.status_code == 404

def test_ics_export_valid_trip(client):
    """Save a trip then export as ICS — verify calendar format."""
    import json
    # Generate a trip first
    dna = {
        "start_city": "Bengaluru", "days": 2, "travellers": 1,
        "budget": {"amount": 8000, "scope": "total", "currency": "INR"},
        "style": "economical", "interests": ["heritage"], "pace": "balanced",
        "transport": "bus", "accessibility": [], "must_visit": [], "avoid": [],
        "diet": "vegetarian", "stay": "budget", "start_date": "2026-10-15"
    }
    gen = client.post("/api/trips/generate", json=dna)
    assert gen.status_code == 200
    trip_data = gen.get_json()["data"]

    # Save the trip
    save = client.post("/api/trips/save", json={
        "dna": trip_data["dna"],
        "itinerary": trip_data["itinerary"],
        "cost_summary": trip_data["budget"]
    })
    assert save.status_code == 201
    trip_id = save.get_json()["data"]["id"]

    # Export ICS
    ics_resp = client.get(f"/api/trips/{trip_id}/export/ics")
    assert ics_resp.status_code == 200
    ics_text = ics_resp.data.decode()
    assert "BEGIN:VCALENDAR" in ics_text
    assert "BEGIN:VEVENT" in ics_text
    assert "END:VCALENDAR" in ics_text

def test_safety_info_on_selected_destinations():
    dests = json.loads((REPO / "data" / "destinations.json").read_text(encoding="utf-8"))
    safety_dests = {"jog_falls", "kudremukh_peak", "dandeli_wildlife", "gokarna_beach", "hampi_virupaksha"}
    found = {d["id"] for d in dests if "safety_info" in d}
    assert safety_dests.issubset(found), f"Missing safety_info on: {safety_dests - found}"

def test_html_has_lang_attribute():
    html = (REPO / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'lang="en"' in html or "lang='en'" in html

def test_html_toast_has_aria_live():
    html = (REPO / "templates" / "index.html").read_text(encoding="utf-8")
    assert "aria-live" in html
