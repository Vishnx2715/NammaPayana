"""
Unit tests for input validation, schema boundaries, and security constraints.
"""
import pytest
from pydantic import ValidationError
from services.validation import JourneyDNA, DestinationRecord

def test_valid_journey_dna():
    dna = JourneyDNA(
        start_city="Bengaluru",
        days=3,
        travellers=2,
        budget={"amount": 8000, "scope": "total", "currency": "INR"},
        style="economical",
        interests=["heritage", "food"],
        pace="relaxed"
    )
    assert dna.days == 3
    assert dna.travellers == 2
    assert dna.budget.amount == 8000

def test_days_bounds():
    # Days = 0 should fail
    with pytest.raises(ValidationError):
        JourneyDNA(
            start_city="Bengaluru",
            days=0,
            travellers=2,
            budget={"amount": 5000}
        )

    # Days > 14 should fail
    with pytest.raises(ValidationError):
        JourneyDNA(
            start_city="Bengaluru",
            days=15,
            travellers=2,
            budget={"amount": 5000}
        )

def test_travellers_bounds():
    # Travellers = 0 should fail
    with pytest.raises(ValidationError):
        JourneyDNA(
            start_city="Bengaluru",
            days=3,
            travellers=0,
            budget={"amount": 5000}
        )

def test_non_numeric_or_negative_budget():
    with pytest.raises(ValidationError):
        JourneyDNA(
            start_city="Bengaluru",
            days=3,
            travellers=2,
            budget={"amount": -500}
        )

    with pytest.raises(ValidationError):
        JourneyDNA(
            start_city="Bengaluru",
            days=3,
            travellers=2,
            budget={"amount": "not_a_number"}
        )

def test_empty_start_city():
    with pytest.raises(ValidationError):
        JourneyDNA(
            start_city="   ",
            days=3,
            travellers=2,
            budget={"amount": 5000}
        )

def test_destination_coordinates_bounding_box():
    valid_data = {
        "id": "test_spot",
        "name_en": "Test Spot",
        "name_kn": "ಟೆಸ್ಟ್ ಸ್ಪಾಟ್",
        "lat": 13.0,
        "lng": 75.0,
        "district": "Hassan",
        "region": "South Karnataka",
        "categories": ["heritage"],
        "description": "Valid test spot",
        "visit_hours": 2.0,
        "entry_fee_inr": {"value": 0, "basis": "sourced"},
        "accessibility_notes": {"value": "None", "verified": True},
        "best_season": {"value": "All year"},
        "image": {"file": "test.jpg"},
        "sources": ["https://karnatakatourism.org"],
        "verification_status": "verified",
        "dataset_version": "1.0"
    }
    # Should succeed inside Karnataka
    record = DestinationRecord(**valid_data)
    assert record.lat == 13.0

    # Outside bounds (e.g. Delhi lat 28.6) should fail
    invalid_data = dict(valid_data)
    invalid_data["lat"] = 28.6
    with pytest.raises(ValidationError):
        DestinationRecord(**invalid_data)
