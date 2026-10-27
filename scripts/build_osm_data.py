"""
build_osm_data.py — OSM data pipeline for NammaPayana.

Queries the Overpass API once and writes:
  data/transit_hubs.json
  data/food.json
  data/stays.json

Falls back to stub files (count=0) if Overpass is unreachable.
Skips if files are less than 7 days old (use --force to override).

Usage:
  python scripts/build_osm_data.py [--force]
"""

import argparse
import datetime
import http.client
import json
import math
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ATTRIBUTION = (
    "© OpenStreetMap contributors, ODbL 1.0 — "
    "https://www.openstreetmap.org/copyright"
)

KARNATAKA_BBOX = {"S": 11.5, "W": 74.0, "N": 18.5, "E": 78.6}


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return approximate distance in km using equirectangular approximation, R=6371."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    x = dlng * math.cos((lat1_r + lat2_r) / 2)
    return R * math.sqrt(x * x + dlat * dlat)


# ---------------------------------------------------------------------------
# Destination helpers
# ---------------------------------------------------------------------------

def load_destinations() -> list:
    """Read data/destinations.json and return a list of dicts with id, lat, lng."""
    data_file = pathlib.Path(__file__).parent.parent / "data" / "destinations.json"
    with open(data_file, encoding="utf-8") as fh:
        raw = json.load(fh)
    return [{"id": d["id"], "lat": d["lat"], "lng": d["lng"]} for d in raw]


def nearest_destination(lat: float, lng: float, destinations: list) -> tuple:
    """Return (id, distance_km) of the closest destination, or (None, inf) if empty."""
    if not destinations:
        return (None, float("inf"))
    best_id = None
    best_dist = float("inf")
    for dest in destinations:
        d = haversine(lat, lng, dest["lat"], dest["lng"])
        if d < best_dist:
            best_dist = d
            best_id = dest["id"]
    return (best_id, best_dist)


# ---------------------------------------------------------------------------
# Freshness check
# ---------------------------------------------------------------------------

def stale_check(output_files: list, max_age_days: int = 7) -> bool:
    """Return True if ALL files exist and all have mtime within max_age_days."""
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=max_age_days
    )
    for path in output_files:
        if not path.exists():
            return False
        mtime = datetime.datetime.fromtimestamp(
            path.stat().st_mtime, tz=datetime.timezone.utc
        )
        if mtime < cutoff:
            return False
    return True


# ---------------------------------------------------------------------------
# Overpass fetch
# ---------------------------------------------------------------------------

def fetch_overpass(query: str, retries: int = 3, timeout: int = 60):
    """
    POST query to Overpass API interpreter.
    Returns parsed JSON dict on success, None after retries exhausted.
    """
    url = "https://overpass-api.de/api/interpreter"
    payload = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    # Overpass rejects generic Python UA with HTTP 406 — use a descriptive one
                    "User-Agent": "NammaPayana/2.0 (Karnataka travel planner; data pipeline; contact: see github.com/nammapayana)",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, http.client.RemoteDisconnected, OSError) as exc:
            print(
                f"  [attempt {attempt}/{retries}] Overpass request failed: {exc}",
                file=sys.stderr,
            )
            if attempt < retries:
                time.sleep(5)
    return None


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------

def build_transit_query() -> str:
    """Return Overpass QL for transit hubs in Karnataka."""
    S = KARNATAKA_BBOX["S"]
    W = KARNATAKA_BBOX["W"]
    N = KARNATAKA_BBOX["N"]
    E = KARNATAKA_BBOX["E"]
    return (
        f'[out:json][timeout:60]; '
        f'(node["highway"="bus_stop"]["name"]({S},{W},{N},{E}); '
        f'node["amenity"="bus_station"]["name"]({S},{W},{N},{E}); '
        f'node["railway"="station"]["name"]({S},{W},{N},{E}); '
        f'node["railway"="halt"]["name"]({S},{W},{N},{E});); '
        f'out body;'
    )


def build_food_query() -> str:
    """Return Overpass QL for restaurants/cafes/fast-food in Karnataka."""
    S = KARNATAKA_BBOX["S"]
    W = KARNATAKA_BBOX["W"]
    N = KARNATAKA_BBOX["N"]
    E = KARNATAKA_BBOX["E"]
    bbox = f"{S},{W},{N},{E}"
    return (
        f'[out:json][timeout:90]; '
        f'(node["amenity"~"restaurant|cafe|fast_food"]["name"]({bbox}); '
        f'way["amenity"~"restaurant|cafe|fast_food"]["name"]({bbox});); '
        f'out center;'
    )


def build_stays_query() -> str:
    """Return Overpass QL for hotels/guesthouses/hostels/motels in Karnataka."""
    S = KARNATAKA_BBOX["S"]
    W = KARNATAKA_BBOX["W"]
    N = KARNATAKA_BBOX["N"]
    E = KARNATAKA_BBOX["E"]
    bbox = f"{S},{W},{N},{E}"
    return (
        f'[out:json][timeout:90]; '
        f'(node["tourism"~"hotel|guest_house|hostel|motel"]["name"]({bbox}); '
        f'way["tourism"~"hotel|guest_house|hostel|motel"]["name"]({bbox});); '
        f'out center;'
    )


# ---------------------------------------------------------------------------
# Processors
# ---------------------------------------------------------------------------

def _in_bbox(lat: float, lng: float) -> bool:
    """Return True if coordinates are within Karnataka bbox."""
    return (
        KARNATAKA_BBOX["S"] <= lat <= KARNATAKA_BBOX["N"]
        and KARNATAKA_BBOX["W"] <= lng <= KARNATAKA_BBOX["E"]
    )


def process_transit(elements: list, destinations: list) -> list:
    """
    Process Overpass transit elements into normalised item dicts.
    Keeps only named nodes within bbox with nearest destination ≤ 20 km.
    """
    items = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        # Only nodes carry lat/lon directly
        if el.get("type") != "node":
            continue
        lat = el.get("lat")
        lng = el.get("lon")
        if lat is None or lng is None:
            continue
        if not _in_bbox(lat, lng):
            continue
        nd_id, dist = nearest_destination(lat, lng, destinations)
        if dist > 20:
            continue
        # Infer type
        if tags.get("railway") in ("station", "halt"):
            hub_type = "railway_station"
        elif tags.get("amenity") == "bus_station":
            hub_type = "bus_station"
        else:
            hub_type = "bus_stop"
        items.append(
            {
                "id": f"transit_{el['id']}",
                "name": name,
                "lat": lat,
                "lng": lng,
                "type": hub_type,
                "nearest_destination_id": nd_id,
                "distance_km": round(dist, 3),
            }
        )
    return items


def process_food(elements: list, destinations: list) -> list:
    """
    Process Overpass food elements into normalised item dicts.
    Keeps only named elements within bbox with nearest destination ≤ 10 km.
    """
    items = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        el_type = el.get("type")
        if el_type == "node":
            lat = el.get("lat")
            lng = el.get("lon")
        elif el_type == "way":
            center = el.get("center", {})
            lat = center.get("lat")
            lng = center.get("lon")
        else:
            continue
        if lat is None or lng is None:
            continue
        if not _in_bbox(lat, lng):
            continue
        nd_id, dist = nearest_destination(lat, lng, destinations)
        if dist > 10:
            continue
        amenity = tags.get("amenity", "")
        cuisine = tags.get("cuisine", "unknown")
        if tags.get("diet:veg") == "yes" or tags.get("diet:vegan") == "yes":
            diet = "veg"
        elif tags.get("diet:halal") == "yes":
            diet = "halal"
        else:
            diet = "unknown"
        if amenity in ("fast_food", "cafe"):
            price_tier = "budget"
        else:
            price_tier = "mid"
        opening_hours = tags.get("opening_hours")
        items.append(
            {
                "id": f"food_{el['id']}",
                "name": name,
                "lat": lat,
                "lng": lng,
                "amenity": amenity,
                "cuisine": cuisine,
                "diet": diet,
                "price_tier": price_tier,
                "opening_hours": opening_hours,
                "nearest_destination_id": nd_id,
                "distance_km": round(dist, 3),
            }
        )
    return items


def process_stays(elements: list, destinations: list) -> list:
    """
    Process Overpass accommodation elements into normalised item dicts.
    Keeps only named elements within bbox with nearest destination ≤ 10 km.
    """
    items = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        el_type = el.get("type")
        if el_type == "node":
            lat = el.get("lat")
            lng = el.get("lon")
        elif el_type == "way":
            center = el.get("center", {})
            lat = center.get("lat")
            lng = center.get("lon")
        else:
            continue
        if lat is None or lng is None:
            continue
        if not _in_bbox(lat, lng):
            continue
        nd_id, dist = nearest_destination(lat, lng, destinations)
        if dist > 10:
            continue
        stay_type = tags.get("tourism")
        stars_raw = tags.get("stars", "")
        stars = int(stars_raw) if stars_raw.isdigit() else None
        items.append(
            {
                "id": f"stay_{el['id']}",
                "name": name,
                "lat": lat,
                "lng": lng,
                "type": stay_type,
                "stars": stars,
                "price_range": None,
                "nearest_destination_id": nd_id,
                "distance_km": round(dist, 3),
            }
        )
    return items


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_output(data_dir: pathlib.Path, filename: str, items: list, label: str) -> None:
    """Write items to data_dir/filename as JSON."""
    out = {
        "attribution": ATTRIBUTION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }
    path = data_dir / filename
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Wrote {path.name}: {len(items)} {label}")


def write_stub(data_dir: pathlib.Path, filename: str) -> None:
    """Write an empty stub file to data_dir/filename."""
    out = {
        "attribution": ATTRIBUTION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "count": 0,
        "items": [],
    }
    path = data_dir / filename
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Wrote stub {path.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build OSM transit/food/stays data.")
    parser.add_argument(
        "--force", action="store_true", help="Re-fetch even if files are fresh."
    )
    args = parser.parse_args()

    repo_root = pathlib.Path(__file__).parent.parent
    data_dir = repo_root / "data"

    transit_path = data_dir / "transit_hubs.json"
    food_path = data_dir / "food.json"
    stays_path = data_dir / "stays.json"
    output_files = [transit_path, food_path, stays_path]

    if not args.force and stale_check(output_files):
        print("Output files are fresh (< 7 days old). Use --force to re-fetch.")
        sys.exit(0)

    destinations = load_destinations()
    print(f"Loaded {len(destinations)} destinations.")

    # --- Transit ---
    print("Fetching transit data from Overpass…")
    transit_result = fetch_overpass(build_transit_query())
    if transit_result is None:
        print("  WARNING: Overpass unreachable for transit — writing stub.", file=sys.stderr)
        write_stub(data_dir, "transit_hubs.json")
    else:
        transit_items = process_transit(transit_result.get("elements", []), destinations)
        write_output(data_dir, "transit_hubs.json", transit_items, "transit hubs")

    # --- Food ---
    print("Fetching food data from Overpass…")
    food_result = fetch_overpass(build_food_query())
    if food_result is None:
        print("  WARNING: Overpass unreachable for food — writing stub.", file=sys.stderr)
        write_stub(data_dir, "food.json")
    else:
        food_items = process_food(food_result.get("elements", []), destinations)
        write_output(data_dir, "food.json", food_items, "food venues")

    # --- Stays ---
    print("Fetching stays data from Overpass…")
    stays_result = fetch_overpass(build_stays_query())
    if stays_result is None:
        print("  WARNING: Overpass unreachable for stays — writing stub.", file=sys.stderr)
        write_stub(data_dir, "stays.json")
    else:
        stays_items = process_stays(stays_result.get("elements", []), destinations)
        write_output(data_dir, "stays.json", stays_items, "stay venues")

    print("Done.")


if __name__ == "__main__":
    main()
