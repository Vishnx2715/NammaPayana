"""
Deterministic Feasibility Engine for Namma Payana.
Transparent 0-100 scoring based on:
  - Budget Fit (30%)
  - Schedule Fit (25%)
  - Route Efficiency (15%)
  - Preference Alignment (20%)
  - Data Confidence (10%)
Hard constraints (over budget, day over capacity) automatically force status='infeasible'.
"""
from typing import Dict, List, Any
import datetime as _dt
import config

class FeasibilityEngine:
    @staticmethod
    def evaluate(
        dna: Dict[str, Any],
        budget_result: Dict[str, Any],
        itinerary: Dict[str, Any],
    ) -> Dict[str, Any]:
        issues: List[str] = []
        suggestions: List[str] = []
        hard_failure = False

        # --- 1. Budget Fit (30 pts) ---
        budget_score = 0.0
        total_budget = budget_result.get("total_budget", 0.0)
        total_cost = budget_result.get("total_cost", 0.0)
        budget_gap = budget_result.get("budget_gap", 0.0)
        is_over_budget = budget_result.get("is_over_budget", False)

        if is_over_budget:
            budget_score = 0.0
            hard_failure = True
            issues.append(f"Estimated expenses (₹{total_cost:,.0f}) exceed your budget (₹{total_budget:,.0f}) by ₹{budget_gap:,.0f}.")
            suggestions.append(f"Increase total budget by at least ₹{budget_gap:,.0f} to cover current selections.")
            suggestions.append("Switch travel style to 'economical' or reduce trip duration by 1 day.")
        else:
            # When cost is within budget:
            usage_ratio = total_cost / total_budget if total_budget > 0 else 1.0
            if usage_ratio <= 0.85:
                budget_score = 30.0  # Safe comfortable cushion
            else:
                # 0.85 to 1.0 is tight
                budget_score = 30.0 * max(0.0, (1.0 - (usage_ratio - 0.85) * 4))
                issues.append(f"Budget is tight: using {usage_ratio*100:.1f}% of allocated funds.")
                suggestions.append("Keep a small buffer for unexpected local travel or seasonal ticket changes.")

        # --- 2. Schedule Fit (25 pts) ---
        schedule_score = 25.0
        days = itinerary.get("days", [])
        pace = dna.get("pace", "balanced")
        max_active = config.MAX_ACTIVE_HOURS.get(pace, 9.0)
        max_travel = config.MAX_TRAVEL_HOURS_PER_DAY.get(pace, 4.5)
        max_stops = config.MAX_STOPS_PER_DAY.get(pace, 3)

        day_capacity_failures = 0
        for day in days:
            day_num = day.get("day_number", 1)
            active_hrs = day.get("total_active_hours", 0.0)
            travel_hrs = day.get("travel_hours", 0.0)
            stops_count = len(day.get("stops", []))

            if active_hrs > max_active:
                day_capacity_failures += 1
                issues.append(f"Day {day_num} active hours ({active_hrs:.1f}h) exceed {pace} limit ({max_active}h).")
            if travel_hrs > max_travel:
                day_capacity_failures += 1
                issues.append(f"Day {day_num} transit time ({travel_hrs:.1f}h) exceeds maximum comfortable limit ({max_travel}h).")
            if stops_count > max_stops:
                day_capacity_failures += 1
                issues.append(f"Day {day_num} has {stops_count} stops (recommended max for {pace} pace is {max_stops}).")

        if day_capacity_failures > 0:
            # Only mark hard failure if there are serious violations (not minor overruns)
            serious_failures = 0
            for day in days:
                day_num = day.get("day_number", 1)
                active_hrs = day.get("total_active_hours", 0.0)
                travel_hrs = day.get("travel_hours", 0.0)
                # Hard fail only when significantly over limit (>20% overage)
                if active_hrs > max_active * 1.20:
                    serious_failures += 1
                if travel_hrs > max_travel * 1.20:
                    serious_failures += 1
            if serious_failures > 0:
                hard_failure = True
            penalty = min(25.0, day_capacity_failures * 8.0)
            schedule_score = max(0.0, 25.0 - penalty)
            suggestions.append("Consider switching pace from 'relaxed' to 'balanced', or dropping 1 distant stop.")

        # P14-1: Opening hours and closed_days enforcement
        start_date_str = dna.get("start_date")
        if start_date_str:
            try:
                _base_date = _dt.date.fromisoformat(start_date_str)
            except (ValueError, AttributeError):
                _base_date = None

            if _base_date:
                for day in days:
                    day_num = day.get("day_number", 1)
                    day_date = _base_date + _dt.timedelta(days=day_num - 1)
                    day_name = day_date.strftime("%A")  # e.g. "Friday"

                    for stop in day.get("stops", []):
                        dest = stop.get("destination", {})
                        dest_name = dest.get("name_en", dest.get("id", "Unknown"))

                        # closed_days check
                        closed_days = dest.get("closed_days")
                        if isinstance(closed_days, list) and day_name in closed_days:
                            issues.append(
                                f"{dest_name} is closed on {day_name}s (Day {day_num}). "
                                f"Consider rescheduling this stop."
                            )
                            schedule_score = max(0.0, schedule_score - 5.0)

                        # opening_hours check
                        oh = dest.get("opening_hours")
                        arrival_str = stop.get("arrival_hour_str")
                        if oh and arrival_str and isinstance(oh, str) and "-" in oh:
                            parts = oh.split("-")
                            if len(parts) == 2:
                                try:
                                    open_h, open_m = (int(x) for x in parts[0].strip().split(":"))
                                    close_h, close_m = (int(x) for x in parts[1].strip().split(":"))
                                    arr_h, arr_m = (int(x) for x in arrival_str.split(":"))
                                    # Skip midnight-spanning ranges (e.g. "20:00-06:00") —
                                    # close_h < open_h means the range crosses midnight and
                                    # cannot be evaluated correctly without date context.
                                    if close_h < open_h:
                                        pass
                                    else:
                                        open_mins = open_h * 60 + open_m
                                        close_mins = close_h * 60 + close_m
                                        arr_mins = arr_h * 60 + arr_m
                                        if arr_mins < open_mins:
                                            issues.append(
                                                f"{dest_name} opens at {parts[0].strip()} but arrival is {arrival_str} on Day {day_num}."
                                            )
                                        elif arr_mins >= close_mins:
                                            issues.append(
                                                f"{dest_name} closes at {parts[1].strip()} but arrival is {arrival_str} on Day {day_num}."
                                            )
                                except (ValueError, AttributeError):
                                    pass

        # --- 3. Route Efficiency (15 pts) ---
        route_score = 15.0
        total_dist_km = itinerary.get("total_distance_km", 0.0)
        num_days = max(1, len(days))
        avg_km_per_day = total_dist_km / num_days

        if avg_km_per_day > 250:
            route_score = max(5.0, 15.0 - ((avg_km_per_day - 250) / 30.0))
            issues.append(f"Long travel legs: average {avg_km_per_day:.0f} km/day on road.")
            suggestions.append("Cluster destinations in one geographic zone (e.g., Coastal or Malnad only).")
        elif avg_km_per_day > 160:
            route_score = 12.0
        else:
            route_score = 15.0

        # --- 4. Preference Alignment (20 pts) ---
        pref_score = 20.0
        user_interests = set(i.lower() for i in dna.get("interests", []))
        all_matched_categories = set()
        must_visits = set(dna.get("must_visit", []))
        visited_ids = set()

        for day in days:
            for stop in day.get("stops", []):
                d = stop.get("destination", {})
                visited_ids.add(d.get("id"))
                for c in d.get("categories", []):
                    all_matched_categories.add(c.lower())

        if user_interests:
            overlap = user_interests.intersection(all_matched_categories)
            match_pct = len(overlap) / len(user_interests)
            pref_score = 20.0 * match_pct
            if match_pct < 0.6:
                issues.append("Some chosen travel interests were not covered due to regional routing constraints.")
                suggestions.append("Add 1 extra day to reach distinct interest clusters (e.g. Heritage vs Coastal).")

        unvisited_musts = must_visits - visited_ids
        if unvisited_musts:
            issues.append(f"Must-visit destinations could not fit within time limit: {', '.join(unvisited_musts)}.")
            suggestions.append("Prioritize must-visits by choosing a start city closer to them.")

        # --- 5. Data Confidence (10 pts) ---
        data_score = 10.0
        unknown_costs = budget_result.get("unknown_costs_count", 0)
        unverified_stops = 0
        for day in days:
            for stop in day.get("stops", []):
                d = stop.get("destination", {})
                if d.get("verification_status") != "verified":
                    unverified_stops += 1

        penalties = (unknown_costs * 1.5) + (unverified_stops * 2.0)
        data_score = max(3.0, 10.0 - penalties)

        # Total Calculation
        total_score = round(budget_score + schedule_score + route_score + pref_score + data_score, 1)

        if hard_failure:
            status = "infeasible"
        elif total_score >= 75.0 and not is_over_budget:
            status = "feasible"
        else:
            status = "tight"

        components = [
            {
                "name": "Budget Fit",
                "score": round(budget_score, 1),
                "max_score": 30.0,
                "status": "fail" if is_over_budget else ("warning" if budget_score < 25 else "pass"),
                "explanation": "Cost exceeds budget" if is_over_budget else f"Expenses use { (total_cost/total_budget)*100 if total_budget else 0:.0f}% of budget."
            },
            {
                "name": "Schedule Fit",
                "score": round(schedule_score, 1),
                "max_score": 25.0,
                "status": "fail" if day_capacity_failures > 0 else "pass",
                "explanation": f"{day_capacity_failures} schedule constraint warnings detected." if day_capacity_failures else f"All daily stops fit comfortably within {pace} pacing limits."
            },
            {
                "name": "Route Efficiency",
                "score": round(route_score, 1),
                "max_score": 15.0,
                "status": "warning" if avg_km_per_day > 200 else "pass",
                "explanation": f"Average road travel of {avg_km_per_day:.0f} km/day between destinations."
            },
            {
                "name": "Preference Alignment",
                "score": round(pref_score, 1),
                "max_score": 20.0,
                "status": "pass" if pref_score >= 15 else "warning",
                "explanation": f"Covered {len(user_interests.intersection(all_matched_categories))} of {len(user_interests)} preferred interest themes." if user_interests else "Standard balanced cultural mix applied."
            },
            {
                "name": "Data Confidence",
                "score": round(data_score, 1),
                "max_score": 10.0,
                "status": "pass" if data_score >= 8 else "warning",
                "explanation": "High dataset verification density with verified government sources." if data_score >= 8 else f"{unknown_costs} cost items marked as estimates."
            }
        ]

        return {
            "score": total_score,
            "status": status,
            "components": components,
            "issues": issues,
            "suggestions": suggestions,
            "disclaimer": "Planning heuristic, not a guarantee."
        }
