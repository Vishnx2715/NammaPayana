"""
Unit tests for AI fallback behavior and verification guarantees.
Ensures engine never trusts unverified AI outputs and seamlessly falls back.
"""
import pytest
from services.ai_planner import AIPlannerService, NullLLMProvider
from services.destination_service import destination_service

def test_ai_fallback_on_null_or_failing_provider():
    # Null provider raises exception; planner must smoothly fallback to deterministic engine
    service = AIPlannerService(provider=NullLLMProvider())

    dna = {
        "start_city": "Bengaluru",
        "days": 2,
        "travellers": 2,
        "budget": {"amount": 6000, "scope": "total", "currency": "INR"},
        "style": "economical",
        "pace": "balanced"
    }

    result = service.generate_plan(dna)
    assert result["itinerary"]["feasible"] is True
    assert result["ai_meta"]["used_ai"] is False
    assert "using rule-based planner" in result["ai_meta"]["notice"]

def test_every_destination_in_plan_is_in_verified_dataset():
    service = AIPlannerService()
    dna = {
        "start_city": "Mysuru",
        "days": 3,
        "travellers": 2,
        "budget": {"amount": 9000, "scope": "total", "currency": "INR"},
        "style": "economical"
    }
    result = service.generate_plan(dna)
    for day in result["itinerary"]["days"]:
        for stop in day["stops"]:
            dest_id = stop["destination"]["id"]
            assert destination_service.destination_exists(dest_id)
            assert destination_service.get_by_id(dest_id) is not None
