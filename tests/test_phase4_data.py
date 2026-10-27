import subprocess, sys, pathlib

REPO = pathlib.Path(__file__).parent.parent

def test_validate_data_script_passes():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "validate_data.py")],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"Data validation failed:\n{result.stdout}\n{result.stderr}"

def test_destination_count_at_least_69():
    import json
    dests = json.loads((REPO / "data" / "destinations.json").read_text(encoding="utf-8"))
    assert len(dests) >= 69, f"Only {len(dests)} destinations, expected ≥69"

def test_no_duplicate_destination_ids():
    import json
    dests = json.loads((REPO / "data" / "destinations.json").read_text(encoding="utf-8"))
    ids = [d["id"] for d in dests]
    assert len(ids) == len(set(ids)), "Duplicate destination IDs found"

def test_all_coordinates_in_karnataka():
    import json
    dests = json.loads((REPO / "data" / "destinations.json").read_text(encoding="utf-8"))
    for d in dests:
        assert 11.5 <= d["lat"] <= 18.5, f"{d['id']} lat out of bounds"
        assert 74.0 <= d["lng"] <= 78.6, f"{d['id']} lng out of bounds"

def test_no_fabricated_fee_basis():
    import json
    dests = json.loads((REPO / "data" / "destinations.json").read_text(encoding="utf-8"))
    valid = {"sourced", "estimated", "unknown"}
    for d in dests:
        basis = d.get("entry_fee_inr", {}).get("basis")
        assert basis in valid, f"{d['id']} has invalid fee basis: {basis}"

def test_wheelchair_accessible_field_present():
    import json
    dests = json.loads((REPO / "data" / "destinations.json").read_text(encoding="utf-8"))
    valid = {"yes", "partial", "no", "unknown"}
    for d in dests:
        assert "wheelchair_accessible" in d, f"{d['id']} missing wheelchair_accessible"
        assert d["wheelchair_accessible"] in valid, \
            f"{d['id']} has invalid wheelchair_accessible: {d['wheelchair_accessible']}"

def test_crowd_level_field_present():
    import json
    dests = json.loads((REPO / "data" / "destinations.json").read_text(encoding="utf-8"))
    valid = {"low", "medium", "high", "unknown"}
    for d in dests:
        assert "crowd_level" in d, f"{d['id']} missing crowd_level"
        assert d["crowd_level"] in valid, \
            f"{d['id']} has invalid crowd_level: {d['crowd_level']}"
