"""
Replanner service for Namma Payana.
Handles structured modifications and rule-based natural language parsing.
Computes an explicit diff (added, removed, kept, cost_delta, explanation) and re-evaluates feasibility.
"""
import re
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from services.itinerary import ItineraryEngine
from services.budget import BudgetEngine
from services.feasibility import FeasibilityEngine
from services.destination_service import destination_service

class ReplannerService:
    @staticmethod
    def parse_instruction(instruction: str, current_dna: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Rule-based intent parser for natural language user modifications.
        Returns (dna_updates, clarification_question_or_none).
        """
        text = instruction.strip().lower()
        updates: Dict[str, Any] = {}

        # 1. Budget adjustments: e.g. "cut budget by 1500", "reduce budget by 1000", "increase budget by 2000"
        budget_cut_match = re.search(r'(?:cut|reduce|decrease|lower)\s+(?:the\s+)?budget\s+by\s+(?:rs\.?|₹)?\s*(\d+)', text)
        if budget_cut_match:
            cut_amt = Decimal(budget_cut_match.group(1))
            current_amt = Decimal(str(current_dna.get("budget", {}).get("amount", "5000")))
            new_amt = max(Decimal("500"), current_amt - cut_amt)
            updates["budget"] = {
                "amount": float(new_amt),
                "scope": current_dna.get("budget", {}).get("scope", "total"),
                "currency": "INR"
            }
            # Also switch to a cheaper style when cutting budget to help stay within it
            current_style = current_dna.get("style", "moderate")
            if current_style == "luxury":
                updates["style"] = "moderate"
            elif current_style == "moderate":
                updates["style"] = "economical"

        budget_add_match = re.search(r'(?:add|increase|raise|boost)\s+(?:the\s+)?budget\s+by\s+(?:rs\.?|₹)?\s*(\d+)', text)
        if budget_add_match:
            add_amt = Decimal(budget_add_match.group(1))
            current_amt = Decimal(str(current_dna.get("budget", {}).get("amount", "5000")))
            new_amt = current_amt + add_amt
            updates["budget"] = {
                "amount": float(new_amt),
                "scope": current_dna.get("budget", {}).get("scope", "total"),
                "currency": "INR"
            }

        # 2. Pace modifications: e.g. "make it more relaxed", "relaxed pace", "packed pace"
        if "more relaxed" in text or "relax" in text or "slow down" in text:
            updates["pace"] = "relaxed"
        elif "packed" in text or "fast" in text or "more stops" in text:
            updates["pace"] = "packed"
        elif "balanced" in text or "moderate pace" in text:
            updates["pace"] = "balanced"

        # 3. Add or remove interests
        if "add food" in text or "food experience" in text or "culinary" in text or "food stop" in text:
            cur_interests = list(current_dna.get("interests", []))
            if "food" not in cur_interests:
                cur_interests.append("food")
            updates["interests"] = cur_interests
            # BUG 5: Bengaluru-specific food destination distance warning
            start_city = str(current_dna.get("start_city", "")).lower()
            if "bengaluru" in start_city or "bangalore" in start_city:
                updates["_food_suggestion"] = (
                    "Food destinations (Udupi, Mangaluru) are best reached from Mangaluru or "
                    "Shivamogga as start cities. Consider starting from there for a food-focused trip."
                )

        if "add heritage" in text or "history" in text:
            cur_interests = list(current_dna.get("interests", []))
            if "heritage" not in cur_interests:
                cur_interests.append("heritage")
            updates["interests"] = cur_interests

        if "add nature" in text or "nature destination" in text or "waterfall" in text:
            cur_interests = list(current_dna.get("interests", []))
            if "nature" not in cur_interests:
                cur_interests.append("nature")
            updates["interests"] = cur_interests

        if "add coastal" in text or "coastal destination" in text or "beach" in text:
            cur_interests = list(current_dna.get("interests", []))
            if "coastal" not in cur_interests:
                cur_interests.append("coastal")
            updates["interests"] = cur_interests

        if "add adventure" in text or "trek" in text or "wildlife" in text:
            cur_interests = list(current_dna.get("interests", []))
            if "adventure" not in cur_interests:
                cur_interests.append("adventure")
            updates["interests"] = cur_interests

        # 4. Exclude destination
        exclude_match = re.search(r'(?:exclude|remove|drop|skip|avoid)\s+([a-zA-Z\s]+)', text)
        if exclude_match:
            target = exclude_match.group(1).strip()
            # Match destination
            all_dests = destination_service.get_all()
            matched = next((d for d in all_dests if target in d["name_en"].lower() or target in d["id"]), None)
            if matched:
                cur_avoid = list(current_dna.get("avoid", []))
                if matched["id"] not in cur_avoid:
                    cur_avoid.append(matched["id"])
                updates["avoid"] = cur_avoid

        # If nothing matched and text is non-empty, ask a clarifying question
        if not updates and len(text) > 3:
            return {}, f"Could not determine adjustment from '{instruction}'. Would you like to adjust budget (e.g., 'cut budget by 1000'), change pace ('more relaxed'), or add an interest ('add food experience')?"

        return updates, None

    @classmethod
    def replan(
        cls,
        current_dna: Dict[str, Any],
        previous_itinerary: Dict[str, Any],
        previous_budget: Dict[str, Any],
        structured_changes: Optional[Dict[str, Any]] = None,
        natural_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        new_dna = dict(current_dna)
        clarification = None

        # 1. Apply natural language instruction if present
        food_suggestion = None
        if natural_instruction:
            nl_updates, clarification = cls.parse_instruction(natural_instruction, new_dna)
            if clarification:
                return {
                    "ok": False,
                    "clarification_needed": True,
                    "question": clarification
                }
            food_suggestion = nl_updates.pop("_food_suggestion", None)
            new_dna.update(nl_updates)

        # 2. Apply structured changes
        if structured_changes:
            for k, v in structured_changes.items():
                if k == "budget" and isinstance(v, dict):
                    new_dna["budget"] = dict(new_dna.get("budget", {}))
                    new_dna["budget"].update(v)
                else:
                    new_dna[k] = v

        # 3. Re-run Itinerary Engine
        new_itinerary = ItineraryEngine.generate(new_dna)

        # Flatten stops for budget calculation
        flat_stops = []
        for d in new_itinerary.get("days", []):
            flat_stops.extend(d.get("stops", []))

        # 4. Re-run Budget and Feasibility
        new_budget = BudgetEngine.calculate_budget(
            new_dna, flat_stops, new_itinerary.get("total_distance_km", 0.0)
        )
        new_feasibility = FeasibilityEngine.evaluate(new_dna, new_budget, new_itinerary)

        # 5. Compute Diff
        old_stop_ids = set()
        for d in previous_itinerary.get("days", []):
            for s in d.get("stops", []):
                old_stop_ids.add(s["destination"]["id"])

        new_stop_ids = set()
        for d in new_itinerary.get("days", []):
            for s in d.get("stops", []):
                new_stop_ids.add(s["destination"]["id"])

        added_ids = list(new_stop_ids - old_stop_ids)
        removed_ids = list(old_stop_ids - new_stop_ids)
        kept_ids = list(old_stop_ids.intersection(new_stop_ids))

        added_stops = [destination_service.get_by_id(aid) for aid in added_ids if destination_service.get_by_id(aid)]
        removed_stops = [destination_service.get_by_id(rid) for rid in removed_ids if destination_service.get_by_id(rid)]

        prev_cost = Decimal(str(previous_budget.get("total_cost", 0.0)))
        curr_cost = Decimal(str(new_budget.get("total_cost", 0.0)))
        cost_delta = float(curr_cost - prev_cost)

        explanation_parts = []
        if natural_instruction:
            explanation_parts.append(f"Applied instruction: '{natural_instruction}'.")
        if cost_delta != 0:
            direction = "increased" if cost_delta > 0 else "reduced"
            explanation_parts.append(f"Estimated expenses {direction} by ₹{abs(cost_delta):,.0f}.")
        if added_ids:
            explanation_parts.append(f"Added {len(added_ids)} destination(s).")
        if removed_ids:
            explanation_parts.append(f"Removed {len(removed_ids)} destination(s).")

        explanation = " ".join(explanation_parts) or "Itinerary recalculated with updated parameters."

        return {
            "ok": True,
            "dna": new_dna,
            "itinerary": new_itinerary,
            "budget": new_budget,
            "feasibility": new_feasibility,
            "food_suggestion": food_suggestion,
            "diff": {
                "added": added_stops,
                "removed": removed_stops,
                "kept_count": len(kept_ids),
                "cost_delta": cost_delta,
                "explanation": explanation
            }
        }
