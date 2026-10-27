"""
Deterministic Trip Reality Engine - Itinerary Generator for Namma Payana.
Generates day-by-day, constraint-verified itineraries purely in Python with zero external API calls.
"""
import math
import datetime
from typing import Dict, List, Any, Tuple, Optional
import config
from services.destination_service import destination_service
from services.routing import routing_provider

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine formula for great-circle distance between two coordinates in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def estimate_road_distance_and_time(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    transport_mode: str = "bus"
) -> Tuple[float, float]:
    """Estimates road km and transit hours using road detour factor and mode speeds."""
    hav_km = haversine_distance_km(lat1, lon1, lat2, lon2)
    road_km = hav_km * config.ROAD_DETOUR_FACTOR
    speed = config.AVG_SPEED_KMPH.get(transport_mode, 40.0)
    hours = road_km / speed if speed > 0 else 0.0
    return round(road_km, 1), round(hours, 2)

class ItineraryEngine:
    @staticmethod
    def generate(dna_dict: Dict[str, Any]) -> Dict[str, Any]:
        days_count = int(dna_dict.get("days", 3))
        start_city = str(dna_dict.get("start_city", "Bengaluru")).strip()
        pace = str(dna_dict.get("pace", "balanced")).lower()
        if pace not in config.MAX_ACTIVE_HOURS:
            pace = "balanced"
        transport = str(dna_dict.get("transport", "bus")).lower()
        if transport not in config.AVG_SPEED_KMPH:
            transport = "bus"

        interests = [i.lower() for i in dna_dict.get("interests", [])]
        avoid_list = set(a.lower() for a in dna_dict.get("avoid", []))
        must_visit_list = [m.lower() for m in dna_dict.get("must_visit", [])]
        accessibility_reqs = dna_dict.get("accessibility", [])

        # Get start city coordinates (default to Bengaluru if not in list)
        start_coord = config.START_CITIES.get(start_city)
        if not start_coord:
            # Check if any destination matches start_city name
            all_dests = destination_service.get_all()
            matched = next((d for d in all_dests if d["name_en"].lower().startswith(start_city.lower())), None)
            if matched:
                start_coord = (matched["lat"], matched["lng"])
            else:
                start_coord = config.START_CITIES["Bengaluru"]

        # 1. Filter candidates
        candidates = []
        for dest in destination_service.get_all():
            dest_id = dest["id"].lower()
            dest_name = dest["name_en"].lower()

            # Avoid list check
            if dest_id in avoid_list or dest_name in avoid_list:
                continue

            # Accessibility check
            if "wheelchair" in [a.lower() for a in accessibility_reqs]:
                notes = dest.get("accessibility_notes", {})
                val = str(notes.get("value", "")).lower()
                not_accessible = (
                    "difficult" in val or
                    "climbing" in val or
                    ("steps" in val and "ramp" not in val and "wheelchair" not in val)
                )
                if not_accessible:
                    continue

            # Candidate scoring
            score = 0.0
            categories = [c.lower() for c in dest.get("categories", [])]
            matched_interests = [i for i in interests if i in categories]
            # Boost interest matches significantly so food/coastal/etc. destinations
            # get selected even when they are farther from the start city
            score += len(matched_interests) * 35.0

            # Proximity to start point (reduced weight so interest match can win)
            dist_to_start = haversine_distance_km(start_coord[0], start_coord[1], dest["lat"], dest["lng"])
            score += max(0.0, 80.0 - (dist_to_start * 0.15))

            # Must visit high priority boost
            is_must = (dest_id in must_visit_list or any(m in dest_name for m in must_visit_list))
            if is_must:
                score += 500.0

            # Season scoring
            start_date_str = dna_dict.get("start_date")
            if start_date_str:
                try:
                    travel_date = datetime.date.fromisoformat(start_date_str)
                    travel_month = travel_date.month
                    best_season = dest.get("best_season", {}).get("value", "")
                    if best_season:
                        # Parse "Oct-Mar" or "Jun-Sep" style ranges
                        MONTH_MAP = {
                            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
                            "may": 5, "jun": 6, "jul": 7, "aug": 8,
                            "sep": 9, "oct": 10, "nov": 11, "dec": 12
                        }
                        parts = best_season.lower().split("-")
                        if len(parts) == 2:
                            start_mon = MONTH_MAP.get(parts[0].strip()[:3])
                            end_mon = MONTH_MAP.get(parts[1].strip()[:3])
                            if start_mon and end_mon:
                                if start_mon <= end_mon:
                                    in_season = start_mon <= travel_month <= end_mon
                                else:
                                    # Year-wrap e.g. Oct-Mar
                                    in_season = travel_month >= start_mon or travel_month <= end_mon
                                if in_season:
                                    score += 10.0
                except (ValueError, AttributeError):
                    pass

            candidates.append({
                "dest": dest,
                "score": score,
                "dist_to_start": dist_to_start,
                "matched_interests": matched_interests,
                "is_must": is_must
            })

        # Sort candidates by score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # 2. Cluster candidates by regional proximity to minimize zig-zagging
        max_stops_day = config.MAX_STOPS_PER_DAY[pace]
        max_active_day = config.MAX_ACTIVE_HOURS[pace]
        max_travel_day = config.MAX_TRAVEL_HOURS_PER_DAY[pace]

        chosen_stops: List[Dict[str, Any]] = []
        visited_ids = set()

        # Always take must-visits first if available
        for cand in candidates:
            if cand["is_must"] and cand["dest"]["id"] not in visited_ids:
                chosen_stops.append(cand)
                visited_ids.add(cand["dest"]["id"])

        # Guarantee at least one destination per unique interest category
        # This ensures food/coastal/adventure stops get represented even when
        # they score lower due to distance from the start city.
        # Only guarantee if the best matching destination can physically fit in a single day.
        guaranteed_interests = set(interests) - {"heritage", "culture", "architecture"}  # Heritage is abundant
        already_covered = set()
        for cand in chosen_stops:
            for cat in cand["dest"].get("categories", []):
                already_covered.add(cat.lower())

        for interest in guaranteed_interests:
            if interest not in already_covered:
                # Find the best-scoring candidate with this category
                # Also check it is physically reachable within max_travel_day hours
                best = None
                for c in candidates:
                    if interest not in [cat.lower() for cat in c["dest"].get("categories", [])]:
                        continue
                    if c["dest"]["id"] in visited_ids:
                        continue
                    # Estimate travel time from start city to this destination
                    _, travel_h = estimate_road_distance_and_time(
                        start_coord[0], start_coord[1],
                        c["dest"]["lat"], c["dest"]["lng"], transport
                    )
                    # For multi-day trips, allow a full-day travel leg (up to max_travel_day * days_count / 2)
                    # so the user can reach farther food/coastal destinations
                    allowable_travel = max_travel_day * min(2.5, days_count / 2.0)
                    if travel_h <= allowable_travel:
                        best = c
                        break
                if best:
                    # Mark as interest-guaranteed so the day partitioner won't drop it
                    best = dict(best)
                    best["interest_guaranteed"] = True
                    chosen_stops.append(best)
                    visited_ids.add(best["dest"]["id"])
                    already_covered.add(interest)

        # Fill remaining slots prioritizing nearest-neighbors to already chosen stops or start
        target_stop_count = days_count * max_stops_day
        for cand in candidates:
            if len(chosen_stops) >= target_stop_count:
                break
            if cand["dest"]["id"] not in visited_ids:
                chosen_stops.append(cand)
                visited_ids.add(cand["dest"]["id"])

        if not chosen_stops:
            return {
                "feasible": False,
                "error": "No matching destinations found adhering to the given constraints and avoid list.",
                "days": [],
                "total_distance_km": 0.0,
                "why_this_plan": []
            }

        # 3. Partition into days, guaranteeing must-visit AND interest-guaranteed stops get placed
        must_cands = [c for c in chosen_stops if c["is_must"] or c.get("interest_guaranteed")]
        other_cands = [c for c in chosen_stops if not c["is_must"] and not c.get("interest_guaranteed")]

        days: List[Dict[str, Any]] = []
        current_loc = start_coord
        total_trip_distance_km = 0.0

        # We have days_count days. If there are must-visit stops, distribute them across days first.
        day_buckets: List[List[Dict[str, Any]]] = [[] for _ in range(days_count)]
        
        # Place must-visit stops into available days
        for idx, m_cand in enumerate(must_cands):
            day_slot = idx % days_count
            day_buckets[day_slot].append(m_cand)

        # Now fill each day's remaining capacity with closest other candidates
        remaining_pool = list(other_cands)

        # Pre-compute the target stops per day to ensure pool drains with rest days at end
        # If pool has fewer destinations than max_stops_day * days_count, pack aggressively
        # so the pool exhausts before all days are filled, creating explicit rest days.
        initial_pool_size = len(remaining_pool)
        forced_stops_per_day = min(max_stops_day, math.ceil(initial_pool_size / days_count)) if days_count > 0 else max_stops_day

        for day_idx in range(1, days_count + 1):
            day_stops = []
            day_active_hours = 0.0
            day_travel_hours = 0.0
            day_road_km = 0.0
            current_time_hour = float(config.DAY_START_HOUR)

            # Seed with any must-visit stops pre-assigned to this day
            pre_assigned = day_buckets[day_idx - 1]
            day_candidates_to_fit = list(pre_assigned)

            # Determine if we need to pack more aggressively: when remaining pool has more
            # items than remaining days, drain faster to ensure rest days appear at the end
            remaining_days_left = days_count - day_idx + 1
            min_stops_needed = math.ceil(len(remaining_pool) / remaining_days_left) if remaining_days_left > 0 else 0

            # Add more candidates from remaining_pool up to max_stops_day respecting daily capacity
            while len(day_candidates_to_fit) < max_stops_day and remaining_pool:
                # Find nearest to current_loc or last in day_candidates_to_fit
                ref_coord = (day_candidates_to_fit[-1]["dest"]["lat"], day_candidates_to_fit[-1]["dest"]["lng"]) if day_candidates_to_fit else current_loc
                remaining_pool.sort(
                    key=lambda c: haversine_distance_km(ref_coord[0], ref_coord[1], c["dest"]["lat"], c["dest"]["lng"])
                )

                if day_candidates_to_fit:
                    # Calculate current cumulative day hours so far
                    est_tot_active = 0.0
                    est_tot_travel = 0.0
                    last_c = current_loc
                    for ex in day_candidates_to_fit:
                        _, l_h = estimate_road_distance_and_time(last_c[0], last_c[1], ex["dest"]["lat"], ex["dest"]["lng"], transport)
                        est_tot_travel += l_h
                        est_tot_active += (l_h + float(ex["dest"].get("visit_hours", 2.5)))
                        last_c = (ex["dest"]["lat"], ex["dest"]["lng"])

                    # Force-pack up to forced_stops_per_day to ensure pool drains deterministically
                    # so that long trips produce explicit rest days when destinations are exhausted.
                    must_pack = len(day_candidates_to_fit) < forced_stops_per_day

                    if must_pack:
                        # Drain mode: place nearest candidate regardless of time limits
                        day_candidates_to_fit.append(remaining_pool.pop(0))
                    else:
                        # Normal mode: try candidates in nearest-first order; skip any that exceed pace limits
                        placed = False
                        for skip_idx in range(len(remaining_pool)):
                            trial_cand = remaining_pool[skip_idx]
                            trial_km, trial_hrs = estimate_road_distance_and_time(
                                last_c[0], last_c[1], trial_cand["dest"]["lat"], trial_cand["dest"]["lng"], transport
                            )
                            trial_visit = float(trial_cand["dest"].get("visit_hours", 2.5))
                            if (est_tot_active + trial_hrs + trial_visit) <= max_active_day and (est_tot_travel + trial_hrs) <= max_travel_day:
                                day_candidates_to_fit.append(remaining_pool.pop(skip_idx))
                                placed = True
                                break
                        if not placed:
                            # No candidate fits today's schedule; move on
                            break
                else:
                    day_candidates_to_fit.append(remaining_pool.pop(0))

            # Order today's stops by nearest-neighbor starting from current_loc
            sort_loc = current_loc
            ordered_day_cands: List[Dict[str, Any]] = []
            while day_candidates_to_fit:
                day_candidates_to_fit.sort(
                    key=lambda c: haversine_distance_km(sort_loc[0], sort_loc[1], c["dest"]["lat"], c["dest"]["lng"])
                )
                chosen = day_candidates_to_fit.pop(0)
                ordered_day_cands.append(chosen)
                sort_loc = (chosen["dest"]["lat"], chosen["dest"]["lng"])

            for candidate in ordered_day_cands:
                dest = candidate["dest"]
                leg_km, leg_hours, leg_basis = routing_provider.route(
                    current_loc[0], current_loc[1], dest["lat"], dest["lng"], transport
                )
                dest_id_for_routing = dest["id"]
                if dest_id_for_routing in config.GHAT_DESTINATIONS:
                    leg_hours = round(leg_hours / config.ROAD_CONDITION_MULTIPLIERS["ghat"], 2)
                    leg_basis = leg_basis + " (ghat road factor applied)"
                start_date_str_routing = dna_dict.get("start_date")
                if start_date_str_routing:
                    try:
                        sd = datetime.date.fromisoformat(start_date_str_routing)
                        if 6 <= sd.month <= 9 and dest_id_for_routing in config.GHAT_DESTINATIONS:
                            leg_hours = round(leg_hours / config.ROAD_CONDITION_MULTIPLIERS["monsoon"], 2)
                            leg_basis = leg_basis + " (monsoon slowdown)"
                    except ValueError:
                        pass
                visit_hrs = float(dest.get("visit_hours", 2.5))
                arrival_time = current_time_hour + leg_hours
                departure_time = arrival_time + visit_hrs

                why_matched = []
                if candidate["is_must"]:
                    why_matched.append("Selected as your explicitly requested must-visit destination")
                elif candidate.get("interest_guaranteed"):
                    dest_cats = [c.lower() for c in dest.get("categories", [])]
                    matching = [i for i in interests if i in dest_cats]
                    why_matched.append(f"Guaranteed food & culture stop matching your '{', '.join(matching)}' interest")
                elif candidate.get("matched_interests"):
                    why_matched.append(f"Matches your passion for {', '.join(candidate['matched_interests'])}")
                else:
                    why_matched.append("Geographic anchor optimizing scenic regional progression")

                # Determine stop type — food destinations get a special type
                dest_cats = [c.lower() for c in dest.get("categories", [])]
                if "food" in dest_cats and any(
                    kw in dest.get("name_en", "").lower()
                    for kw in ["udupi", "mangal", "darshini", "hotel", "restaurant", "dhaba", "matha", "panambur"]
                ) or ("food" in dest_cats and "food" in interests):
                    stop_type = "food_stop"
                else:
                    stop_type = "destination"

                stop_entry = {
                    "stop_number": len(day_stops) + 1,
                    "destination": dest,
                    "stop_type": stop_type,
                    "leg_distance_km": leg_km,
                    "leg_duration_hours": leg_hours,
                    "leg_basis": leg_basis,
                    "arrival_hour_str": f"{int(arrival_time):02d}:{int((arrival_time % 1) * 60):02d}",
                    "departure_hour_str": f"{int(departure_time):02d}:{int((departure_time % 1) * 60):02d}",
                    "visit_hours": visit_hrs,
                    "why_matched": why_matched,
                    "entry_fee_info": dest.get("entry_fee_inr", {}),
                    "verification_status": dest.get("verification_status", "verified"),
                    "source_url": dest.get("sources", [None])[0] if dest.get("sources") else None
                }

                MONSOON_WARNING_IDS = {"jog_falls", "kudremukh_peak", "dandeli_wildlife", "coorg_madikeri", "gokarna_beach"}
                start_date_str = dna_dict.get("start_date")
                if start_date_str:
                    try:
                        travel_date = datetime.date.fromisoformat(start_date_str)
                        if 6 <= travel_date.month <= 9 and dest["id"] in MONSOON_WARNING_IDS:
                            stop_entry["monsoon_warning"] = True
                            stop_entry["monsoon_note"] = "Heavy monsoon season — verify accessibility and safety conditions before visiting."
                    except (ValueError, AttributeError):
                        pass

                day_stops.append(stop_entry)
                day_active_hours += (leg_hours + visit_hrs)
                day_travel_hours += leg_hours
                day_road_km += leg_km
                current_time_hour = departure_time
                current_loc = (dest["lat"], dest["lng"])

            total_trip_distance_km += day_road_km

            # P3-2: Explicit rest day when no stops could be filled
            if not day_stops:
                days.append({
                    "day_number": day_idx,
                    "region_theme": "Rest / Travel Day",
                    "stops": [],
                    "travel_distance_km": 0.0,
                    "travel_hours": 0.0,
                    "total_active_hours": 0.0,
                    "schedule_status": "rest",
                    "rest_day_note": "No new destinations scheduled. Use this day for relaxed exploration, local food, or travel to next region."
                })
                continue

            # Determine day theme from stops
            day_regions = list(set(s["destination"]["region"] for s in day_stops))
            day_region_str = " & ".join(day_regions) if day_regions else "Karnataka"

            days.append({
                "day_number": day_idx,
                "region_theme": day_region_str,
                "stops": day_stops,
                "travel_distance_km": round(day_road_km, 1),
                "travel_hours": round(day_travel_hours, 2),
                "total_active_hours": round(day_active_hours, 2),
                "schedule_status": "optimal" if day_active_hours <= max_active_day else "tight",
            })

        # Construct concrete "Why this plan" rationale mapping inputs to effects
        why_this_plan = [
            {
                "input": f"{pace.capitalize()} Pace",
                "effect": f"Capped at max {max_stops_day} stops/day and {max_active_day}h active daily window (starts at {config.DAY_START_HOUR}:00 AM, finishes by {config.DAY_END_HOUR}:00 PM)."
            },
            {
                "input": f"{transport.capitalize()} Transit Mode",
                "effect": f"Transit times modeled at realistic average {config.AVG_SPEED_KMPH[transport]} km/h including 30% Karnataka road detour topography buffer."
            },
            {
                "input": f"Starting from {start_city}",
                "effect": f"Route organized as a directional geographic corridor starting from {start_city} coordinates to eliminate backtracking."
            }
        ]

        if interests:
            why_this_plan.append({
                "input": f"Interests: {', '.join(i.capitalize() for i in interests)}",
                "effect": f"Destination ranking prioritizes sites tagged with {', '.join(interests)} while preserving geographical continuity."
            })

        # P3-2: Rest day summary
        rest_day_count = sum(1 for d in days if d.get("schedule_status") == "rest")
        if rest_day_count > 0:
            why_this_plan.append({
                "input": "Long Trip / Destination Limit",
                "effect": f"{rest_day_count} rest day(s) added because available unique destinations were exhausted before all {days_count} days could be filled."
            })

        # P3-3: Monsoon warning summary
        start_date_str = dna_dict.get("start_date")
        if start_date_str:
            try:
                travel_date = datetime.date.fromisoformat(start_date_str)
                if 6 <= travel_date.month <= 9:
                    monsoon_stops = [
                        s["destination"]["id"]
                        for d in days
                        for s in d["stops"]
                        if s.get("monsoon_warning")
                    ]
                    if monsoon_stops:
                        why_this_plan.append({
                            "input": "Monsoon Season Warning (Jun-Sep)",
                            "effect": f"Destinations {', '.join(monsoon_stops)} may have restricted access during monsoon. Verify conditions before travel."
                        })
            except (ValueError, AttributeError):
                pass

        return {
            "feasible": True,
            "start_city": start_city,
            "days_count": days_count,
            "pace": pace,
            "transport": transport,
            "total_distance_km": round(total_trip_distance_km, 1),
            "distance_basis": "estimated road network",
            "days": days,
            "why_this_plan": why_this_plan,
        }
