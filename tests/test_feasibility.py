"""
Unit tests for transparent Feasibility Engine scoring and hard constraint enforcement.
"""
import pytest
from services.feasibility import FeasibilityEngine

def test_over_budget_forces_infeasible_status():
    dna = {"pace": "balanced", "interests": []}
    budget = {
        "total_budget": 5000.0,
        "total_cost": 6500.0,
        "is_over_budget": True,
        "budget_gap": 1500.0,
        "unknown_costs_count": 0
    }
    itinerary = {"days": [], "total_distance_km": 100.0}

    res = FeasibilityEngine.evaluate(dna, budget, itinerary)
    assert res["status"] == "infeasible"
    assert any("exceed your budget" in issue for issue in res["issues"])
    assert any("Increase total budget by at least ₹1,500" in sug for sug in res["suggestions"])

def test_within_budget_and_reasonable_schedule():
    dna = {"pace": "balanced", "interests": ["heritage"]}
    budget = {
        "total_budget": 15000.0,
        "total_cost": 8000.0,
        "is_over_budget": False,
        "budget_gap": 0.0,
        "unknown_costs_count": 0
    }
    itinerary = {
        "days": [
            {
                "day_number": 1,
                "total_active_hours": 6.0,
                "travel_hours": 2.0,
                "stops": [
                    {
                        "destination": {
                            "id": "mysuru_palace",
                            "categories": ["heritage"],
                            "verification_status": "verified"
                        }
                    }
                ]
            }
        ],
        "total_distance_km": 150.0
    }

    res = FeasibilityEngine.evaluate(dna, budget, itinerary)
    assert res["status"] == "feasible"
    assert res["score"] >= 75.0

def test_feasibility_components_sum():
    dna = {"pace": "balanced", "interests": []}
    budget = {
        "total_budget": 10000.0,
        "total_cost": 7000.0,
        "is_over_budget": False,
        "budget_gap": 0.0,
        "unknown_costs_count": 0
    }
    itinerary = {"days": [], "total_distance_km": 50.0}

    res = FeasibilityEngine.evaluate(dna, budget, itinerary)
    comp_sum = sum(c["score"] for c in res["components"])
    assert round(comp_sum, 1) == pytest.approx(res["score"], 0.1)
