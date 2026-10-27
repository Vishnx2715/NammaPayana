"""
Unit tests for the Replanner Service: intent parsing, diff calculation, and partial updates.
"""
import pytest
from services.itinerary import ItineraryEngine
from services.budget import BudgetEngine
from services.replanner import ReplannerService

def test_replanner_budget_cut():
    dna = {
        "start_city": "Bengaluru",
        "days": 3,
        "travellers": 2,
        "budget": {"amount": 8000, "scope": "total", "currency": "INR"},
        "style": "economical",
        "pace": "relaxed",
        "transport": "bus"
    }
    itin = ItineraryEngine.generate(dna)
    flat_stops = [s for d in itin["days"] for s in d["stops"]]
    budget = BudgetEngine.calculate_budget(dna, flat_stops, itin["total_distance_km"])

    replan_res = ReplannerService.replan(
        current_dna=dna,
        previous_itinerary=itin,
        previous_budget=budget,
        natural_instruction="cut budget by 1500"
    )

    assert replan_res["ok"] is True
    assert replan_res["dna"]["budget"]["amount"] == 6500.0
    assert "diff" in replan_res
    assert "explanation" in replan_res["diff"]

def test_replanner_ambiguous_instruction_asks_clarification():
    dna = {
        "start_city": "Bengaluru",
        "days": 2,
        "travellers": 1,
        "budget": {"amount": 5000, "scope": "total", "currency": "INR"},
        "style": "economical"
    }
    itin = ItineraryEngine.generate(dna)
    budget = BudgetEngine.calculate_budget(dna, [], 50.0)

    replan_res = ReplannerService.replan(
        current_dna=dna,
        previous_itinerary=itin,
        previous_budget=budget,
        natural_instruction="something completely random that cannot be parsed xyz"
    )

    assert replan_res["ok"] is False
    assert replan_res.get("clarification_needed") is True
    assert "question" in replan_res
