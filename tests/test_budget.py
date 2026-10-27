"""
Unit tests for deterministic Budget Engine (Decimal arithmetic, reserve, over-budget flagging).
"""
import pytest
from decimal import Decimal
from services.budget import BudgetEngine, CostLine

def test_positive_budget_required():
    dna = {
        "days": 3,
        "travellers": 2,
        "budget": {"amount": 0, "scope": "total", "currency": "INR"},
        "style": "economical"
    }
    with pytest.raises(ValueError, match="Budget must be strictly greater than 0"):
        BudgetEngine.calculate_budget(dna, [])

def test_negative_budget_rejected():
    dna = {
        "days": 3,
        "travellers": 2,
        "budget": {"amount": -1000, "scope": "total", "currency": "INR"},
        "style": "economical"
    }
    with pytest.raises(ValueError, match="Budget must be strictly greater than 0"):
        BudgetEngine.calculate_budget(dna, [])

def test_decimal_exactness_and_per_person_scope():
    dna_total = {
        "days": 2,
        "travellers": 4,
        "budget": {"amount": 8000, "scope": "total", "currency": "INR"},
        "style": "economical",
        "transport": "bus"
    }
    res_total = BudgetEngine.calculate_budget(dna_total, [], total_distance_km=100.0)
    assert res_total["total_budget"] == 8000.0
    assert res_total["per_person_budget"] == 2000.0

    dna_pp = {
        "days": 2,
        "travellers": 4,
        "budget": {"amount": 2500, "scope": "per_person", "currency": "INR"},
        "style": "economical",
        "transport": "bus"
    }
    res_pp = BudgetEngine.calculate_budget(dna_pp, [], total_distance_km=100.0)
    assert res_pp["total_budget"] == 10000.0
    assert res_pp["per_person_budget"] == 2500.0

def test_unknown_costs_not_summed_to_zero_and_flagged():
    stops = [
        {
            "destination": {
                "id": "mystery_spot",
                "name_en": "Mystery Spot",
                "entry_fee_inr": {"value": None, "basis": "unknown"}
            }
        }
    ]
    dna = {
        "days": 1,
        "travellers": 1,
        "budget": {"amount": 5000, "scope": "total", "currency": "INR"},
        "style": "economical"
    }
    res = BudgetEngine.calculate_budget(dna, stops, total_distance_km=0.0)
    assert res["unknown_costs_count"] == 1
    assert res["cost_label"] == "minimum known cost"

    # Verify that unknown lines have None amount and aren't coerced to 0.0 blindly
    unknown_lines = [c for c in res["cost_lines"] if c["basis"] == "unknown"]
    assert len(unknown_lines) == 1
    assert unknown_lines[0]["amount"] is None

def test_emergency_reserve_ten_percent():
    dna = {
        "days": 1,
        "travellers": 1,
        "budget": {"amount": 5000, "scope": "total", "currency": "INR"},
        "style": "economical",
        "transport": "bus"
    }
    # For 1 day, 1 traveller, economical:
    # Food: 400
    # Local: 200
    # Transport (0 km): 0
    # Accommodation (0 nights for 1 day): 0
    # Subtotal = 600
    # Reserve = 10% of 600 = 60
    # Total = 660
    res = BudgetEngine.calculate_budget(dna, [], total_distance_km=0.0)
    reserve_line = next(c for c in res["cost_lines"] if c["category"] == "emergency_reserve")
    assert reserve_line["amount"] == 60.0
    assert res["total_cost"] == 660.0

def test_over_budget_flagging():
    dna = {
        "days": 5,
        "travellers": 3,
        "budget": {"amount": 1000, "scope": "total", "currency": "INR"},
        "style": "luxury",
        "transport": "car"
    }
    res = BudgetEngine.calculate_budget(dna, [], total_distance_km=300.0)
    assert res["is_over_budget"] is True
    assert res["budget_gap"] > 0
    assert res["remaining_budget"] < 0
