"""
Unit tests for deterministic Itinerary Engine (constraints, avoid list, must-visit).
"""
import pytest
from services.itinerary import ItineraryEngine
from services.destination_service import destination_service
import config

def test_all_destination_ids_exist_in_dataset():
    dna = {
        "start_city": "Bengaluru",
        "days": 3,
        "travellers": 2,
        "pace": "balanced",
        "transport": "bus",
        "interests": ["heritage", "nature"]
    }
    res = ItineraryEngine.generate(dna)
    assert res["feasible"] is True
    assert len(res["days"]) == 3

    for day in res["days"]:
        for stop in day["stops"]:
            dest_id = stop["destination"]["id"]
            assert destination_service.destination_exists(dest_id)

def test_stops_per_day_within_pace_limits():
    for pace, max_stops in config.MAX_STOPS_PER_DAY.items():
        dna = {
            "start_city": "Mysuru",
            "days": 2,
            "travellers": 1,
            "pace": pace,
            "transport": "car",
            "interests": ["heritage"]
        }
        res = ItineraryEngine.generate(dna)
        for day in res["days"]:
            assert len(day["stops"]) <= max_stops

def test_avoid_list_is_strictly_respected():
    avoided_dest = "mysuru_palace"
    dna = {
        "start_city": "Bengaluru",
        "days": 3,
        "travellers": 2,
        "pace": "balanced",
        "avoid": [avoided_dest]
    }
    res = ItineraryEngine.generate(dna)
    for day in res["days"]:
        for stop in day["stops"]:
            assert stop["destination"]["id"] != avoided_dest

def test_must_visit_is_included():
    must_dest = "hampi_virupaksha"
    dna = {
        "start_city": "Hubballi",
        "days": 3,
        "travellers": 2,
        "pace": "balanced",
        "must_visit": [must_dest]
    }
    res = ItineraryEngine.generate(dna)
    all_stop_ids = [s["destination"]["id"] for d in res["days"] for s in d["stops"]]
    assert must_dest in all_stop_ids

def test_deterministic_output_for_same_input():
    dna = {
        "start_city": "Bengaluru",
        "days": 3,
        "travellers": 2,
        "pace": "relaxed",
        "transport": "bus",
        "interests": ["heritage", "food"]
    }
    run1 = ItineraryEngine.generate(dna)
    run2 = ItineraryEngine.generate(dna)

    stops1 = [s["destination"]["id"] for d in run1["days"] for s in d["stops"]]
    stops2 = [s["destination"]["id"] for d in run2["days"] for s in d["stops"]]
    assert stops1 == stops2
    assert run1["total_distance_km"] == run2["total_distance_km"]
