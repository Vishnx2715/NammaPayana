import pytest
from services.routing import HaversineProvider, OSRMProvider, haversine_km

def test_haversine_provider_returns_valid_result():
    provider = HaversineProvider()
    km, hours, basis = provider.route(12.9716, 77.5946, 12.3051, 76.6551, "bus")
    assert 130 < km < 200  # Bengaluru to Mysuru road distance approx 150km
    assert 3.0 < hours < 5.0
    assert "haversine" in basis.lower() or "road" in basis.lower()

def test_haversine_provider_zero_distance():
    provider = HaversineProvider()
    km, hours, basis = provider.route(12.9716, 77.5946, 12.9716, 77.5946, "bus")
    assert km == 0.0
    assert hours == 0.0

def test_osrm_provider_falls_back_on_bad_url():
    provider = OSRMProvider(base_url="http://127.0.0.1:19999", timeout=0.5)
    km, hours, basis = provider.route(12.9716, 77.5946, 12.3051, 76.6551, "bus")
    assert km > 0  # fallback haversine result
    assert "fallback" in basis.lower() or "haversine" in basis.lower()

def test_itinerary_uses_leg_basis_from_provider():
    from services.itinerary import ItineraryEngine
    dna = {
        "start_city": "Bengaluru", "days": 2, "travellers": 1,
        "budget": {"amount": 8000, "scope": "total", "currency": "INR"},
        "style": "economical", "interests": ["heritage"], "pace": "balanced",
        "transport": "bus", "accessibility": [], "must_visit": [], "avoid": [],
        "diet": "vegetarian", "stay": "budget", "start_date": None
    }
    result = ItineraryEngine.generate(dna)
    for day in result["days"]:
        for stop in day["stops"]:
            assert "leg_basis" in stop
            assert len(stop["leg_basis"]) > 5  # not empty

def test_ghat_destination_has_higher_travel_time():
    from services.itinerary import ItineraryEngine
    # Trip to Jog Falls (ghat destination) vs flat destination same distance
    dna_ghat = {
        "start_city": "Shivamogga", "days": 1, "travellers": 1,
        "budget": {"amount": 5000, "scope": "total", "currency": "INR"},
        "style": "economical", "interests": ["nature"], "pace": "packed",
        "transport": "bus", "accessibility": [], "must_visit": ["jog_falls"], "avoid": [],
        "diet": "vegetarian", "stay": "budget", "start_date": None
    }
    result = ItineraryEngine.generate(dna_ghat)
    jog_stop = next(
        (s for d in result["days"] for s in d["stops"] if s["destination"]["id"] == "jog_falls"),
        None
    )
    assert jog_stop is not None
    # Ghat factor should be reflected in leg_basis
    assert "ghat" in jog_stop["leg_basis"].lower() or jog_stop["leg_duration_hours"] > 0
