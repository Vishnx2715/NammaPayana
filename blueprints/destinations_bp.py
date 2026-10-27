"""Destinations, phrases, and translation blueprint."""
import os
import json
import pathlib
from flask import Blueprint, request, jsonify, current_app
import config
from services.destination_service import destination_service
from services.translator import translator_service
from blueprints.extensions import limiter, csrf

destinations_bp = Blueprint("destinations_bp", __name__)

ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0"


@destinations_bp.route("/api/destinations", methods=["GET"])
@csrf.exempt
def get_destinations():
    region = request.args.get("region")
    category = request.args.get("category")
    max_hours = request.args.get("max_hours", type=float)
    max_fee = request.args.get("max_fee", type=float)

    destinations = destination_service.get_all(
        region=region,
        category=category,
        max_hours=max_hours,
        max_fee=max_fee
    )
    return jsonify({
        "ok": True,
        "data": {
            "count": len(destinations),
            "destinations": destinations
        }
    }), 200


@destinations_bp.route("/api/destinations/<destination_id>", methods=["GET"])
@csrf.exempt
def get_destination_detail(destination_id: str):
    dest = destination_service.get_by_id(destination_id)
    if not dest:
        return jsonify({
            "ok": False,
            "error": {
                "code": "DESTINATION_NOT_FOUND",
                "message": f"Destination with ID '{destination_id}' was not found in dataset."
            }
        }), 404

    return jsonify({
        "ok": True,
        "data": dest
    }), 200


@destinations_bp.route("/api/destinations/<destination_id>/safety", methods=["GET"])
@csrf.exempt
def get_destination_safety(destination_id: str):
    """Returns safety info for a destination (emergency numbers, hospital, advisories)."""
    dest = destination_service.get_by_id(destination_id)
    if not dest:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": "Destination not found."}}), 404
    safety = dest.get("safety_info", {})
    return jsonify({
        "ok": True,
        "data": {
            "destination_id": destination_id,
            "name": dest.get("name_en"),
            "safety_info": safety,
            "emergency_number": safety.get("emergency_number", "112"),
            "nearest_hospital": safety.get("nearest_hospital"),
            "ghat_road_advisory": safety.get("ghat_road_advisory"),
            "basis": safety.get("basis", "unknown"),
            "disclaimer": "Safety information is indicative only. Always verify locally and contact emergency services directly."
        }
    }), 200


@destinations_bp.route("/api/phrases", methods=["GET"])
@csrf.exempt
def get_phrases():
    query = request.args.get("q", "").strip().lower()
    scenario = request.args.get("scenario", "").strip().lower()

    phrases_path = os.path.join(config.DATA_DIR, "kannada_phrases.json")
    if not os.path.exists(phrases_path):
        return jsonify({"ok": False, "error": {"code": "DATA_MISSING", "message": "Phrases dataset missing."}}), 500

    with open(phrases_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    phrases = data.get("phrases", [])
    dialogues = data.get("dialogues", [])

    if scenario:
        phrases = [p for p in phrases if p.get("scenario", "").lower() == scenario]

    if query:
        phrases = [
            p for p in phrases
            if query in p.get("english", "").lower()
            or query in p.get("transliteration", "").lower()
            or query in p.get("kannada", "")
        ]

    return jsonify({
        "ok": True,
        "data": {
            "count": len(phrases),
            "phrases": phrases,
            "dialogues": dialogues
        }
    }), 200


@destinations_bp.route("/api/translate", methods=["POST"])
@csrf.exempt
@limiter.limit(lambda: config.RATE_LIMIT_TRANSLATE)
def translate_to_kannada():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({
            "ok": False,
            "error": {
                "code": "INVALID_BODY",
                "message": "Missing JSON payload."
            }
        }), 400
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Request body must be a JSON object."}}), 400

    text = body.get("text", "").strip()
    if len(text) > 300:
        return jsonify({"ok": False, "error": {"code": "TEXT_TOO_LONG", "message": "Text must be 300 characters or fewer."}}), 400
    source_lang = body.get("source_lang", "en").strip().lower()

    if not text:
        return jsonify({
            "ok": False,
            "error": {
                "code": "EMPTY_TEXT",
                "message": "Please provide text to translate."
            }
        }), 400

    result = translator_service.translate(text=text, source_lang=source_lang)
    return jsonify(result), 200


@destinations_bp.route("/api/transit", methods=["GET"])
@csrf.exempt
@limiter.limit("30 per minute")
def get_transit():
    data_path = pathlib.Path(current_app.root_path) / "data" / "transit_hubs.json"
    if not data_path.exists():
        items = []
    else:
        with open(data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        items = raw.get("items", [])

    near = request.args.get("near")
    type_filter = request.args.get("type")
    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        limit = 20

    if near:
        items = [it for it in items if it.get("nearest_destination_id") == near]
    if type_filter:
        items = [it for it in items if it.get("type") == type_filter]

    items = items[:limit]

    return jsonify({
        "ok": True,
        "data": {
            "count": len(items),
            "items": items,
            "attribution": ATTRIBUTION,
        }
    }), 200


@destinations_bp.route("/api/food", methods=["GET"])
@csrf.exempt
@limiter.limit("30 per minute")
def get_food():
    data_path = pathlib.Path(current_app.root_path) / "data" / "food.json"
    if not data_path.exists():
        items = []
    else:
        with open(data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        items = raw.get("items", [])

    near = request.args.get("near")
    diet = request.args.get("diet")
    tier = request.args.get("tier")
    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        limit = 20

    if near:
        items = [it for it in items if it.get("nearest_destination_id") == near]
    if diet:
        items = [it for it in items if it.get("diet") == diet]
    if tier:
        items = [it for it in items if it.get("price_tier") == tier]

    items = items[:limit]

    return jsonify({
        "ok": True,
        "data": {
            "count": len(items),
            "items": items,
            "attribution": ATTRIBUTION,
        }
    }), 200
