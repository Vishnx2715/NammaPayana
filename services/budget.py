"""
Deterministic Budget Engine for Namma Payana.
Uses Decimal arithmetic for exact currency computation without floating-point errors.
Every cost line explicitly states its basis (user_entered, sourced, estimated, unknown).
"""
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Literal, Any
import config
import json as _json
import os as _os


def _load_stays() -> dict:
    """Load stays.json keyed by nearest_destination_id. Silent on missing file."""
    _stays_path = _os.path.join(_os.path.dirname(__file__), "..", "data", "stays.json")
    try:
        with open(_stays_path, encoding="utf-8") as _f:
            _data = _json.load(_f)
        return {
            item["nearest_destination_id"]: item
            for item in _data.get("items", [])
            if item.get("nearest_destination_id")
        }
    except Exception:
        return {}


_stays_by_dest: dict = _load_stays()

@dataclass
class CostLine:
    category: str
    amount: Optional[Decimal]      # None = unknown
    basis: Literal["user_entered", "sourced", "estimated", "unknown"]
    assumption: str             # human-readable explanation of computation
    source_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "amount": float(self.amount) if self.amount is not None else None,
            "amount_raw": str(self.amount) if self.amount is not None else None,
            "basis": self.basis,
            "assumption": self.assumption,
            "source_url": self.source_url,
        }

class BudgetEngine:
    @staticmethod
    def calculate_budget(
        dna_dict: Dict[str, Any],
        itinerary_stops: List[Dict[str, Any]],
        total_distance_km: float = 0.0,
    ) -> Dict[str, Any]:
        days = int(dna_dict.get("days", 1))
        travellers = int(dna_dict.get("travellers", 1))
        style = str(dna_dict.get("style", "economical")).lower()
        if style not in config.DAILY_RATES:
            style = "economical"

        transport_mode = str(dna_dict.get("transport", "bus")).lower()
        if transport_mode not in config.TRANSPORT_COST_PER_KM:
            transport_mode = "bus"

        budget_info = dna_dict.get("budget", {})
        raw_budget_amount = Decimal(str(budget_info.get("amount", "0")))
        if raw_budget_amount <= 0:
            raise ValueError("Budget must be strictly greater than 0")

        scope = budget_info.get("scope", "total")
        currency = budget_info.get("currency", "INR")

        if scope == "per_person":
            total_user_budget = (raw_budget_amount * Decimal(travellers)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
            per_person_budget = raw_budget_amount.quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
        else:
            total_user_budget = raw_budget_amount.quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
            per_person_budget = (raw_budget_amount / Decimal(travellers)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

        cost_lines: List[CostLine] = []
        rates = config.DAILY_RATES[style]

        # 1. Transport (intercity & regional transit)
        km_dec = Decimal(str(round(total_distance_km, 1)))
        km_rate = config.TRANSPORT_COST_PER_KM[transport_mode]
        if transport_mode == "car":
            # Car is rented/hired per vehicle
            trans_cost = (km_dec * km_rate).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
            assumption = f"Private car hired at approx ₹{km_rate}/km for {km_dec} estimated km."
        else:
            # Bus / Train is per person
            trans_cost = (km_dec * km_rate * Decimal(travellers)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
            assumption = f"{transport_mode.capitalize()} fare at ₹{km_rate}/km × {km_dec} km × {travellers} traveller(s)."

        cost_lines.append(CostLine(
            category="transport",
            amount=trans_cost,
            basis="estimated",
            assumption=assumption,
            source_url="https://ksrtc.in" if transport_mode == "bus" else None
        ))

        # 2. Accommodation (nights = days - 1, minimum 1 if overnight trip)
        nights = max(1, days - 1) if days > 1 else 0
        if nights > 0:
            stay_rate = rates["stay_per_person"]
            stay_total = (stay_rate * Decimal(nights) * Decimal(travellers)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
            stay_note = f"{style.capitalize()} stay estimate: ₹{stay_rate}/person/night × {nights} night(s) × {travellers} traveller(s)."
            if _stays_by_dest:
                stay_note += " (OSM stays data available — use /api/food?near=<dest_id> for options)"
            cost_lines.append(CostLine(
                category="accommodation",
                amount=stay_total,
                basis="estimated",
                assumption=stay_note,
                source_url=None
            ))

        # 3. Food & Beverages
        food_rate = rates["food_per_person"]
        food_total = (food_rate * Decimal(days) * Decimal(travellers)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
        cost_lines.append(CostLine(
            category="food",
            amount=food_total,
            basis="estimated",
            assumption=f"{style.capitalize()} daily meal allowance: ₹{food_rate}/person/day × {days} day(s) × {travellers} traveller(s).",
            source_url=None
        ))

        # 4. Local Travel (intra-city auto/transit)
        local_rate = rates["local_transit"]
        local_total = (local_rate * Decimal(days) * Decimal(travellers)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
        cost_lines.append(CostLine(
            category="local_travel",
            amount=local_total,
            basis="estimated",
            assumption=f"Local intra-city hops: ₹{local_rate}/person/day × {days} day(s) × {travellers} traveller(s).",
            source_url=None
        ))

        # 5. Entry Tickets (from verified destination records)
        tickets_total = Decimal("0")
        unknown_tickets_count = 0
        for stop in itinerary_stops:
            dest = stop.get("destination", {})
            fee_info = dest.get("entry_fee_inr", {})
            fee_val = fee_info.get("value")
            fee_basis = fee_info.get("basis", "unknown")
            source_url = fee_info.get("source_url")

            if fee_val is None or fee_basis == "unknown":
                unknown_tickets_count += 1
                cost_lines.append(CostLine(
                    category="entry_tickets",
                    amount=None,
                    basis="unknown",
                    assumption=f"Entry fee for {dest.get('name_en', 'Destination')} is unverified or variable.",
                    source_url=source_url
                ))
            else:
                dest_ticket_cost = (Decimal(str(fee_val)) * Decimal(travellers)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
                tickets_total += dest_ticket_cost
                cost_lines.append(CostLine(
                    category="entry_tickets",
                    amount=dest_ticket_cost,
                    basis=fee_basis if fee_basis in ["sourced", "estimated", "user_entered"] else "sourced",
                    assumption=f"Ticket fee for {dest.get('name_en')}: ₹{fee_val} × {travellers} traveller(s).",
                    source_url=source_url
                ))

        # 6. Emergency Reserve (default 10% on known subtotal)
        known_subtotal = Decimal("0")
        unknown_count = 0
        for line in cost_lines:
            if line.amount is not None:
                known_subtotal += line.amount
            else:
                unknown_count += 1

        reserve_cost = (known_subtotal * config.DEFAULT_EMERGENCY_RESERVE_PCT).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
        cost_lines.append(CostLine(
            category="emergency_reserve",
            amount=reserve_cost,
            basis="estimated",
            assumption=f"Safety buffer: 10% contingency on known expenses.",
            source_url=None
        ))

        total_known_cost = (known_subtotal + reserve_cost).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
        per_person_cost = (total_known_cost / Decimal(travellers)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
        cost_per_day = (total_known_cost / Decimal(days)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
        remaining_budget = (total_user_budget - total_known_cost).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

        is_over_budget = remaining_budget < Decimal("0")
        budget_gap = (-remaining_budget) if is_over_budget else Decimal("0")

        # Category rollups for summary graphs
        category_totals: Dict[str, float] = {}
        for line in cost_lines:
            cat = line.category
            if line.amount is not None:
                category_totals[cat] = category_totals.get(cat, 0.0) + float(line.amount)

        # Alternative comfortable / economical comparison
        alt_style = "moderate" if style == "economical" else "economical"
        alt_rates = config.DAILY_RATES[alt_style]
        alt_stay = alt_rates["stay_per_person"] * Decimal(nights) * Decimal(travellers)
        alt_food = alt_rates["food_per_person"] * Decimal(days) * Decimal(travellers)
        alt_local = alt_rates["local_transit"] * Decimal(days) * Decimal(travellers)
        alt_base = trans_cost + alt_stay + alt_food + alt_local + tickets_total
        alt_total = (alt_base * (Decimal("1") + config.DEFAULT_EMERGENCY_RESERVE_PCT)).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

        return {
            "total_budget": float(total_user_budget),
            "per_person_budget": float(per_person_budget),
            "currency": currency,
            "total_cost": float(total_known_cost),
            "cost_label": "minimum known cost" if unknown_count > 0 else "estimated total cost",
            "per_person_cost": float(per_person_cost),
            "cost_per_day": float(cost_per_day),
            "remaining_budget": float(remaining_budget),
            "is_over_budget": is_over_budget,
            "budget_gap": float(budget_gap),
            "unknown_costs_count": unknown_count,
            "cost_lines": [c.to_dict() for c in cost_lines],
            "category_totals": category_totals,
            "comparison": {
                "current_style": style,
                "current_total": float(total_known_cost),
                "alternative_style": alt_style,
                "alternative_total": float(alt_total),
            }
        }

    @staticmethod
    def export_as_csv(budget_result: Dict[str, Any]) -> str:
        lines = [
            "Category,Amount (INR),Basis,Assumption,Source",
        ]
        for item in budget_result.get("cost_lines", []):
            amt = str(item.get("amount")) if item.get("amount") is not None else "Estimate unavailable"
            cat = item.get("category", "")
            basis = item.get("basis", "")
            assumption = f'"{item.get("assumption", "").replace(chr(34), chr(39))}"'
            src = item.get("source_url") or ""
            lines.append(f"{cat},{amt},{basis},{assumption},{src}")
        lines.append(f"TOTAL KNOWN COST,{budget_result.get('total_cost', 0)},estimated,-,-")
        lines.append(f"TOTAL BUDGET,{budget_result.get('total_budget', 0)},user_entered,-,-")
        lines.append(f"REMAINING,{budget_result.get('remaining_budget', 0)},computed,-,-")
        return "\n".join(lines)
