"""Trips blueprint — generate, validate, replan, save, list, CRUD, share, export."""
import uuid as _uuid
import hmac
from datetime import date, timedelta
from flask import Blueprint, request, jsonify, session, Response, render_template
from pydantic import ValidationError
import config
from services.validation import JourneyDNA, ReplanRequest, TripSaveRequest
from services.destination_service import destination_service
from services.itinerary import ItineraryEngine
from services.budget import BudgetEngine
from services.feasibility import FeasibilityEngine
from services.replanner import ReplannerService
from services.trip_store import trip_store, hash_token
from services.ai_planner import ai_planner_service
from blueprints.extensions import limiter, csrf, csrf_protect_if_enabled

trips_bp = Blueprint("trips_bp", __name__)


def _validate_trip_id(trip_id: str):
    """Return (error_response, status_code) if trip_id is not a valid UUID, else (None, None)."""
    try:
        _uuid.UUID(trip_id)
    except ValueError:
        return jsonify({"ok": False, "error": {"code": "INVALID_ID", "message": "trip_id must be a valid UUID."}}), 400
    return None, None


# ── Static-segment routes FIRST to prevent 'generate'/'validate'/etc. matching <trip_id> ──

@trips_bp.route("/api/trips/generate", methods=["POST"])
@csrf.exempt
@limiter.limit(lambda: config.RATE_LIMIT_GENERATE)
def generate_trip():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({
            "ok": False,
            "error": {
                "code": "INVALID_BODY",
                "message": "Missing or malformed JSON payload."
            }
        }), 400
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Request body must be a JSON object."}}), 400

    try:
        dna = JourneyDNA(**body)
    except ValidationError as ve:
        fields = {err["loc"][0] if err["loc"] else "root": err["msg"] for err in ve.errors()}
        return jsonify({
            "ok": False,
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Input validation failed on one or more fields.",
                "fields": fields
            }
        }), 400

    dna_dict = dna.model_dump()

    plan = ai_planner_service.generate_plan(dna_dict)
    itinerary = plan["itinerary"]
    budget = plan["budget"]
    feasibility = plan["feasibility"]

    return jsonify({
        "ok": True,
        "data": {
            "dna": dna_dict,
            "itinerary": itinerary,
            "budget": budget,
            "feasibility": feasibility,
            "ai_meta": plan["ai_meta"]
        }
    }), 200


@trips_bp.route("/api/trips/validate", methods=["POST"])
@csrf.exempt
def validate_trip():
    """Instantly validates budget & feasibility without full itinerary rebuild."""
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Missing JSON payload."}}), 400
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Request body must be a JSON object."}}), 400

    try:
        dna = JourneyDNA(**body.get("dna", {}))
    except ValidationError as ve:
        fields = {err["loc"][0] if err["loc"] else "root": err["msg"] for err in ve.errors()}
        return jsonify({
            "ok": False,
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Invalid Journey DNA format.",
                "fields": fields
            }
        }), 400

    itinerary = body.get("itinerary", {})
    flat_stops = []
    for d in itinerary.get("days", []):
        flat_stops.extend(d.get("stops", []))

    dist_km = itinerary.get("total_distance_km", 0.0)
    budget = BudgetEngine.calculate_budget(dna.model_dump(), flat_stops, dist_km)
    feasibility = FeasibilityEngine.evaluate(dna.model_dump(), budget, itinerary)

    return jsonify({
        "ok": True,
        "data": {
            "budget": budget,
            "feasibility": feasibility
        }
    }), 200


@trips_bp.route("/api/trips/replan", methods=["POST"])
@csrf.exempt
@limiter.limit(lambda: config.RATE_LIMIT_REPLAN)
def replan_trip():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Missing JSON payload."}}), 400
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Request body must be a JSON object."}}), 400

    trip = body.get("trip")
    if isinstance(trip, dict):
        dna_raw = body.get("dna") or body.get("current_dna") or trip.get("dna") or trip.get("current_dna")
        itinerary = body.get("itinerary") or body.get("previous_itinerary") or trip.get("itinerary") or trip.get("previous_itinerary")
        budget = body.get("budget") or body.get("previous_budget") or trip.get("budget") or trip.get("previous_budget") or trip.get("cost_summary")
    else:
        dna_raw = body.get("dna") or body.get("current_dna")
        itinerary = body.get("itinerary") or body.get("previous_itinerary")
        budget = body.get("budget") or body.get("previous_budget")

    if not dna_raw or not itinerary or not budget:
        return jsonify({
            "ok": False,
            "error": {
                "code": "MISSING_DATA",
                "message": "Replan requires current 'dna', 'itinerary', and 'budget'."
            }
        }), 400

    try:
        dna = JourneyDNA(**dna_raw)
    except ValidationError as ve:
        return jsonify({
            "ok": False,
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Invalid Journey DNA.",
                "fields": {err["loc"][0]: err["msg"] for err in ve.errors()}
            }
        }), 400

    changes = body.get("changes") or body.get("structured_changes")
    instruction = body.get("instruction") or body.get("natural_instruction")

    result = ReplannerService.replan(
        current_dna=dna.model_dump(),
        previous_itinerary=itinerary,
        previous_budget=budget,
        structured_changes=changes,
        natural_instruction=instruction
    )

    if not result.get("ok"):
        return jsonify(result), 200

    return jsonify({
        "ok": True,
        "data": result
    }), 200


@trips_bp.route("/api/trips/save", methods=["POST"])
@csrf_protect_if_enabled
def save_trip():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Missing JSON payload."}}), 400
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Request body must be a JSON object."}}), 400

    try:
        save_req = TripSaveRequest(**body)
    except ValidationError as ve:
        return jsonify({
            "ok": False,
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Invalid trip save payload.",
                "fields": {err["loc"][0]: err["msg"] for err in ve.errors()}
            }
        }), 400

    try:
        user_id = session.get("user_id")
        saved = trip_store.save_trip(
            dna=save_req.dna.model_dump(mode="json"),
            itinerary=save_req.itinerary,
            cost_summary=save_req.cost_summary,
            trip_id=save_req.trip_id,
            edit_token=save_req.edit_token,
            uncertainties=save_req.uncertainties,
            user_id=user_id
        )
        return jsonify({
            "ok": True,
            "data": saved
        }), 201 if not save_req.trip_id else 200
    except KeyError as e:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": str(e)}}), 404
    except PermissionError as pe:
        return jsonify({"ok": False, "error": {"code": "FORBIDDEN", "message": str(pe)}}), 403


@trips_bp.route("/api/trips/claim", methods=["POST"])
@csrf_protect_if_enabled
def claim_trips():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Must be logged in to claim trips."}}), 401

    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Missing or malformed JSON payload."}}), 400

    tokens = body.get("edit_tokens")
    if not isinstance(tokens, list):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_FAILED", "message": "'edit_tokens' must be a list."}}), 400

    claimed = trip_store.claim_trips(edit_tokens=tokens, user_id=user_id)
    return jsonify({"ok": True, "data": {"claimed": claimed}}), 200


# ── Dynamic-segment routes AFTER static ones ──

@trips_bp.route("/api/trips", methods=["GET"])
@csrf.exempt
def list_saved_trips():
    try:
        limit = min(int(request.args.get("limit", 50)), 100)
    except (ValueError, TypeError):
        limit = 50
    trips = trip_store.list_trips(
        limit=limit,
        user_id=session.get("user_id"),
        edit_tokens=request.args.getlist("edit_token")
    )
    return jsonify({
        "ok": True,
        "data": {
            "trips": trips,
            "count": len(trips)
        }
    }), 200


@trips_bp.route("/api/trips/<trip_id>", methods=["GET"])
@csrf.exempt
def get_trip(trip_id: str):
    err, code = _validate_trip_id(trip_id)
    if err:
        return err, code
    trip = trip_store.get_trip(trip_id)
    if not trip:
        return jsonify({
            "ok": False,
            "error": {
                "code": "TRIP_NOT_FOUND",
                "message": f"Trip '{trip_id}' not found."
            }
        }), 404

    return jsonify({
        "ok": True,
        "data": trip
    }), 200


@trips_bp.route("/api/trips/<trip_id>", methods=["PUT"])
@csrf_protect_if_enabled
def update_trip(trip_id: str):
    err, code = _validate_trip_id(trip_id)
    if err:
        return err, code
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Missing JSON payload."}}), 400
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Request body must be a JSON object."}}), 400

    existing_trip = trip_store.get_trip(trip_id)
    if existing_trip is None:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": f"Trip '{trip_id}' not found."}}), 404

    session_user_id = session.get("user_id")
    edit_token = request.headers.get("X-Edit-Token") or body.get("edit_token")

    # Determine if the session user is the owner
    user_owns_trip = (session_user_id is not None and existing_trip["user_id"] == session_user_id)

    if not user_owns_trip:
        if existing_trip["user_id"] is not None and existing_trip["user_id"] != session_user_id:
            if not edit_token:
                return jsonify({
                    "ok": False,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Missing edit_token in header or body."
                    }
                }), 401
        elif existing_trip["user_id"] is None and session_user_id is None:
            if not edit_token:
                return jsonify({
                    "ok": False,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Missing edit_token in header or body."
                    }
                }), 401

    try:
        dna = JourneyDNA(**body.get("dna", {}))
    except ValidationError as ve:
        return jsonify({
            "ok": False,
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Invalid Journey DNA.",
                "fields": {err["loc"][0]: err["msg"] for err in ve.errors()}
            }
        }), 400

    try:
        # If user owns the trip, fetch the stored edit_token_hash so save_trip can verify it internally.
        # We pass the raw token from client if provided; otherwise for owners we use the stored hash bypass
        # by delegating directly to the store update bypassing token check.
        if user_owns_trip and not edit_token:
            # Owner update: directly write without token (owner identity verified via session)
            from services.db import db_connection
            import json as _json_mod
            from services.trip_store import safe_json_dumps
            import datetime as _dt
            now = _dt.datetime.now(_dt.timezone.utc).isoformat()
            with db_connection(trip_store.db_path) as conn:
                conn.execute("""
                    UPDATE trips
                    SET updated_at = ?, dna_json = ?, itinerary_json = ?, cost_json = ?, uncertainties_json = ?
                    WHERE id = ? AND user_id = ?
                """, (
                    now,
                    safe_json_dumps(dna.model_dump(mode="json")),
                    safe_json_dumps(body.get("itinerary", {})),
                    safe_json_dumps(body.get("cost_summary", {})),
                    safe_json_dumps(body.get("uncertainties", [])),
                    trip_id,
                    session_user_id
                ))
                conn.commit()
            return jsonify({"ok": True, "data": {"id": trip_id, "updated_at": now}}), 200

        updated = trip_store.save_trip(
            dna=dna.model_dump(mode="json"),
            itinerary=body.get("itinerary", {}),
            cost_summary=body.get("cost_summary", {}),
            trip_id=trip_id,
            edit_token=edit_token or "",
            uncertainties=body.get("uncertainties", []),
            user_id=session_user_id
        )
        return jsonify({"ok": True, "data": updated}), 200
    except KeyError as e:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": str(e)}}), 404
    except PermissionError as pe:
        return jsonify({"ok": False, "error": {"code": "FORBIDDEN", "message": str(pe)}}), 403


@trips_bp.route("/api/trips/<trip_id>", methods=["DELETE"])
@csrf_protect_if_enabled
def delete_trip(trip_id: str):
    err, code = _validate_trip_id(trip_id)
    if err:
        return err, code
    user_id = session.get("user_id")
    edit_token = request.headers.get("X-Edit-Token")
    if not edit_token and request.is_json:
        edit_token = request.json.get("edit_token")

    if not edit_token and not user_id:
        return jsonify({
            "ok": False,
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Missing edit token for deletion."
            }
        }), 401

    try:
        deleted = trip_store.delete_trip(trip_id, edit_token=edit_token or "", user_id=user_id)
        if not deleted:
            return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": "Trip not found."}}), 404
        return jsonify({"ok": True, "data": {"deleted": True, "id": trip_id}}), 200
    except PermissionError as pe:
        return jsonify({"ok": False, "error": {"code": "FORBIDDEN", "message": str(pe)}}), 403


@trips_bp.route("/api/trips/<trip_id>/duplicate", methods=["POST"])
@csrf.exempt
def duplicate_trip(trip_id: str):
    err, code = _validate_trip_id(trip_id)
    if err:
        return err, code
    try:
        new_trip = trip_store.duplicate_trip(trip_id)
        return jsonify({"ok": True, "data": new_trip}), 201
    except KeyError as e:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": str(e)}}), 404


@trips_bp.route("/api/trips/<trip_id>/export", methods=["GET"])
@csrf.exempt
def export_trip(trip_id: str):
    err, code = _validate_trip_id(trip_id)
    if err:
        return err, code
    export_format = request.args.get("format", "csv").lower()
    trip = trip_store.get_trip(trip_id)
    if not trip:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": "Trip not found."}}), 404

    if export_format == "csv":
        csv_data = BudgetEngine.export_as_csv(trip["cost_summary"])
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=namma_payana_trip_{trip_id[:8]}.csv"}
        )
    elif export_format in ["html", "pdf"]:
        return render_template("print_export.html", trip=trip)
    else:
        return jsonify({
            "ok": False,
            "error": {
                "code": "INVALID_FORMAT",
                "message": "Format must be one of: csv, html, pdf"
            }
        }), 400


@trips_bp.route("/api/trips/<trip_id>/share", methods=["POST"])
@csrf_protect_if_enabled
def get_share_link(trip_id):
    """Returns the share token for a trip. Requires ownership (session user_id) or edit_token."""
    err, code = _validate_trip_id(trip_id)
    if err:
        return err, code
    edit_token = request.headers.get("X-Edit-Token") or (request.get_json(silent=True) or {}).get("edit_token", "")
    user_id = session.get("user_id")
    trip = trip_store.get_trip(trip_id)
    if not trip:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": "Trip not found."}}), 404
    owns = (user_id and trip.get("user_id") == user_id)
    has_token = False
    if edit_token:
        from services.db import db_connection
        with db_connection(trip_store.db_path) as _conn:
            _row = _conn.execute("SELECT edit_token_hash FROM trips WHERE id = ?", (trip_id,)).fetchone()
            if _row:
                has_token = hmac.compare_digest(hash_token(edit_token), _row["edit_token_hash"])
    if not owns and not has_token:
        return jsonify({"ok": False, "error": {"code": "FORBIDDEN", "message": "Ownership required."}}), 403
    return jsonify({"ok": True, "data": {"share_token": trip["share_token"], "url": f"/api/shared/{trip['share_token']}"}}), 200


@trips_bp.route("/api/shared/<share_token>", methods=["GET"])
@csrf.exempt
def get_shared_trip(share_token):
    """Public read-only endpoint — no auth required."""
    if not share_token or len(share_token) > 64:
        return jsonify({"ok": False, "error": {"code": "INVALID_TOKEN", "message": "Invalid share token."}}), 400
    trip = trip_store.get_trip_by_share_token(share_token)
    if not trip:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": "Shared trip not found."}}), 404
    return jsonify({"ok": True, "data": trip}), 200


@trips_bp.route("/api/trips/<trip_id>/export/ics", methods=["GET"])
@trips_bp.route("/api/trips/<trip_id>/export-ics", methods=["GET"])
@csrf.exempt
def export_trip_ics(trip_id):
    """Exports the trip itinerary as an iCalendar (.ics) file."""
    err, code = _validate_trip_id(trip_id)
    if err:
        return err, code
    trip = trip_store.get_trip(trip_id)
    if not trip:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": "Trip not found."}}), 404

    itinerary = trip.get("itinerary", {})
    start_date_str = trip.get("dna", {}).get("start_date") or "2026-01-01"
    try:
        base_date = date.fromisoformat(start_date_str)
    except ValueError:
        from datetime import date as _date
        base_date = _date.today()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Namma Payana//Trip Reality Engine//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for day in itinerary.get("days", []):
        day_date = base_date + timedelta(days=day["day_number"] - 1)
        date_str = day_date.strftime("%Y%m%d")
        for stop in day.get("stops", []):
            dest = stop.get("destination", {})
            name = dest.get("name_en", "Stop").replace(",", "\\,").replace("\n", "\\n")
            desc = dest.get("description", "").replace(",", "\\,").replace("\n", "\\n")[:200]
            uid = f"{trip_id}-day{day['day_number']}-{dest.get('id','stop')}@nammapayana"
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTART;VALUE=DATE:{date_str}",
                f"DTEND;VALUE=DATE:{date_str}",
                f"SUMMARY:{name}",
                f"DESCRIPTION:{desc}",
                f"GEO:{dest.get('lat', 0)};{dest.get('lng', 0)}",
                "END:VEVENT",
            ]

    lines.append("END:VCALENDAR")
    ics_content = "\r\n".join(lines) + "\r\n"

    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={"Content-Disposition": f"attachment;filename=namma_payana_trip_{trip_id[:8]}.ics"}
    )
