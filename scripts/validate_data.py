#!/usr/bin/env python3
"""
Validate data/destinations.json against the DestinationRecord schema.
Run: python scripts/validate_data.py
Exit 0 = all valid (warnings allowed). Exit 1 = validation errors found.
"""
import json
import sys
import pathlib
import datetime

REPO = pathlib.Path(__file__).parent.parent
DATA_FILE = REPO / "data" / "destinations.json"

KARNATAKA_LAT = (11.5, 18.5)
KARNATAKA_LNG = (74.0, 78.6)
VALID_BASES = {"sourced", "estimated", "unknown"}
VALID_VERIFICATION = {"verified", "partial", "unverified"}
VALID_REGIONS = {"North Karnataka", "South Karnataka", "Coastal Karnataka", "Malnad", "Central Karnataka"}
VALID_WHEELCHAIR = {"yes", "partial", "no", "unknown"}
VALID_CROWD = {"low", "medium", "high", "unknown"}


def validate_transit_food(errors, warnings):
    """Check data/transit_hubs.json and data/food.json for required structure."""
    for filename, required_item_fields in [
        ("transit_hubs.json", ["id", "name", "lat", "lng"]),
        ("food.json", ["id", "name", "lat", "lng"]),
    ]:
        path = REPO / "data" / filename
        if not path.exists():
            warnings.append(f"{filename}: file missing (stub not yet generated)")
            continue

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            errors.append(f"{filename}: invalid JSON — {exc}")
            continue

        if "attribution" not in data:
            errors.append(f"{filename}: missing 'attribution' field")

        items = data.get("items")
        if not isinstance(items, list):
            errors.append(f"{filename}: 'items' field is missing or not a list")
            continue

        if len(items) == 0:
            warnings.append(f"{filename}: items list is empty (stub)")
            continue

        for item in items[:10]:
            for field in required_item_fields:
                if field not in item:
                    errors.append(f"{filename}: item missing required field '{field}': {item.get('id', '?')}")


def validate():
    errors = []
    warnings = []
    today = datetime.date.today()

    with open(DATA_FILE, encoding="utf-8") as f:
        dests = json.load(f)

    ids_seen = set()
    for i, d in enumerate(dests):
        prefix = f"[{i}] {d.get('id', '?')}"

        # Duplicate ID
        did = d.get("id", "")
        if did in ids_seen:
            errors.append(f"{prefix}: duplicate id '{did}'")
        ids_seen.add(did)

        # Required fields
        for field in ["id", "name_en", "name_kn", "lat", "lng", "district", "region",
                      "categories", "description", "visit_hours", "entry_fee_inr",
                      "verification_status", "dataset_version"]:
            if field not in d:
                errors.append(f"{prefix}: missing field '{field}'")

        # Coordinate bounds
        lat, lng = d.get("lat", 0), d.get("lng", 0)
        if not (KARNATAKA_LAT[0] <= lat <= KARNATAKA_LAT[1]):
            errors.append(f"{prefix}: lat {lat} out of Karnataka bounds")
        if not (KARNATAKA_LNG[0] <= lng <= KARNATAKA_LNG[1]):
            errors.append(f"{prefix}: lng {lng} out of Karnataka bounds")

        # Fee basis
        fee = d.get("entry_fee_inr", {})
        if fee.get("basis") not in VALID_BASES:
            errors.append(f"{prefix}: invalid entry_fee_inr.basis '{fee.get('basis')}'")
        if fee.get("value") is not None and fee["value"] < 0:
            errors.append(f"{prefix}: negative entry fee")

        # Verification status
        if d.get("verification_status") not in VALID_VERIFICATION:
            errors.append(f"{prefix}: invalid verification_status")

        # Region
        if d.get("region") not in VALID_REGIONS:
            errors.append(f"{prefix}: unknown region '{d.get('region')}'")

        # visit_hours positive
        if d.get("visit_hours", 0) <= 0:
            errors.append(f"{prefix}: visit_hours must be > 0")

        # wheelchair_accessible (required, validated value)
        wa = d.get("wheelchair_accessible")
        if wa is None:
            errors.append(f"{prefix}: missing field 'wheelchair_accessible'")
        elif wa not in VALID_WHEELCHAIR:
            errors.append(f"{prefix}: invalid wheelchair_accessible '{wa}'")

        # crowd_level (required, validated value)
        cl = d.get("crowd_level")
        if cl is None:
            errors.append(f"{prefix}: missing field 'crowd_level'")
        elif cl not in VALID_CROWD:
            errors.append(f"{prefix}: invalid crowd_level '{cl}'")

        # last_verified format (optional, but must be YYYY-MM-DD if present)
        lv = d.get("last_verified")
        if lv is not None:
            try:
                lv_date = datetime.date.fromisoformat(lv)
                if (today - lv_date).days > 365:
                    warnings.append(f"{prefix}: last_verified is over 12 months old ({lv})")
            except ValueError:
                errors.append(f"{prefix}: invalid last_verified format '{lv}' (expected YYYY-MM-DD)")

        # Sources: at least one, each starts with http
        sources = d.get("sources", [])
        if not sources:
            errors.append(f"{prefix}: sources list is empty")
        else:
            for s in sources:
                if not str(s).startswith("http"):
                    errors.append(f"{prefix}: source URL does not start with http: '{s}'")

        # Image URL format (if present)
        img_url = d.get("image", {}).get("url", "")
        if img_url and not (img_url.startswith("/static/images/") or img_url.startswith("https://")):
            errors.append(f"{prefix}: image.url has unexpected format: '{img_url}'")

    validate_transit_food(errors, warnings)

    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  {w}")

    if errors:
        print(f"VALIDATION FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(f"OK — {len(dests)} destinations validated successfully.")


if __name__ == "__main__":
    validate()
