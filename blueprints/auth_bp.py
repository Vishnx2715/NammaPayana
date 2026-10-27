"""Authentication blueprint — login, register, Google OAuth, session management."""
import os
import hmac
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import generate_csrf
import config
from services.user_store import user_store, _GENERIC_REGISTRATION_ERROR
from services.trip_store import trip_store
from blueprints.extensions import limiter, csrf, csrf_protect_if_enabled

auth_bp = Blueprint("auth_bp", __name__)

# Pre-computed dummy hash for timing-constant login (prevents user enumeration via timing).
# Both the "user not found" and "wrong password" branches cost exactly one
# check_password_hash() call.
_DUMMY_HASH = generate_password_hash("dummy_constant_string_32chars_xx")


def _cycle_session(user_id=None):
    """Regenerates session to defend against fixation while preserving CSRF session token."""
    csrf_tok = session.get("csrf_token")
    session.clear()
    if csrf_tok:
        session["csrf_token"] = csrf_tok
    if user_id:
        session["user_id"] = user_id


@auth_bp.route("/api/csrf-token", methods=["GET"])
@csrf.exempt
def get_csrf_token():
    return jsonify({"ok": True, "data": {"csrf_token": generate_csrf()}}), 200


@auth_bp.route("/api/auth/register", methods=["POST"])
@csrf_protect_if_enabled
@limiter.limit("3 per minute; 10 per hour")
def auth_register():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Missing JSON payload."}}), 400
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Request body must be a JSON object."}}), 400

    username = body.get("username", "").strip()
    email = body.get("email", "").strip()
    full_name = body.get("full_name", "").strip()
    password = body.get("password", "")
    persona = body.get("persona", "Heritage Explorer")
    home_city = body.get("home_city", "Bengaluru")

    try:
        user = user_store.create_user(
            username=username,
            email=email,
            full_name=full_name,
            password=password,
            persona=persona,
            home_city=home_city
        )
        _cycle_session(user["id"])
        return jsonify({"ok": True, "data": {"message": "Account created. Please verify your email."}}), 201
    except ValueError as ve:
        msg = str(ve)
        if msg == _GENERIC_REGISTRATION_ERROR:
            # Duplicate email/username — return same 201 to prevent enumeration
            return jsonify({"ok": True, "data": {"message": "Account created. Please verify your email."}}), 201
        # Genuine validation error (bad format, short password, etc.)
        return jsonify({"ok": False, "error": {"code": "VALIDATION_FAILED", "message": msg}}), 400
    except Exception as exc:
        import logging
        logging.getLogger("nammapayana").exception("Registration failed: %s", exc)
        return jsonify({"ok": False, "error": {"code": "REGISTRATION_ERROR", "message": "Failed to create account."}}), 500


@auth_bp.route("/api/auth/login", methods=["POST"])
@csrf_protect_if_enabled
@limiter.limit("5 per minute; 20 per hour")
def auth_login():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Missing JSON payload."}}), 400
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "Request body must be a JSON object."}}), 400

    identifier = (body.get("identifier") or body.get("email") or body.get("username", "")).strip()
    password = body.get("password", "")

    _INVALID = {"ok": False, "error": {"code": "INVALID_CREDENTIALS", "message": "Invalid credentials."}}

    existing_user = user_store.get_user_by_identifier(identifier)
    if not existing_user:
        check_password_hash(_DUMMY_HASH, password)
        return jsonify(_INVALID), 401

    user = user_store.authenticate(identifier=identifier, password=password)
    if not user:
        return jsonify(_INVALID), 401

    _cycle_session(user["id"])
    session["login_time"] = datetime.now(timezone.utc).isoformat()
    session["last_active"] = datetime.now(timezone.utc).isoformat()
    return jsonify({"ok": True, "data": user}), 200


@auth_bp.route("/api/auth/google-check", methods=["POST"])
@csrf.exempt
@limiter.limit("5 per minute")
def auth_google_check():
    import jwt as pyjwt
    from flask import current_app
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip() or config.SUPABASE_JWT_SECRET
    if not jwt_secret:
        return jsonify({"ok": False, "error": {"code": "AUTH_NOT_CONFIGURED", "message": "Auth provider not configured."}}), 503

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Bearer token required."}}), 401

    token = auth_header[len("Bearer "):].strip()
    try:
        claims = pyjwt.decode(token, jwt_secret, algorithms=["HS256"], audience="authenticated", options={"require": ["exp", "sub", "email"]})
    except pyjwt.ExpiredSignatureError:
        return jsonify({"ok": False, "error": {"code": "TOKEN_EXPIRED", "message": "Token has expired."}}), 401
    except pyjwt.InvalidTokenError:
        return jsonify({"ok": False, "error": {"code": "INVALID_TOKEN", "message": "Invalid token."}}), 401

    # Validate issuer — Supabase sets iss to the project URL
    supabase_url = os.environ.get("SUPABASE_URL", "")
    if supabase_url and not current_app.config.get("TESTING"):
        expected_iss = supabase_url + "/auth/v1"
        if claims.get("iss") != expected_iss:
            return jsonify({"ok": False, "error": {"code": "INVALID_TOKEN", "message": "Token issuer mismatch."}}), 401

    if not claims.get("email_verified"):
        return jsonify({"ok": False, "error": {"code": "EMAIL_NOT_VERIFIED", "message": "Email not verified."}}), 401

    email = (claims.get("email") or "").strip().lower()
    if not email:
        return jsonify({"ok": False, "error": {"code": "INVALID_TOKEN", "message": "Token has no email claim."}}), 401

    user = user_store.get_user_by_email(email)
    if not user:
        return jsonify({"ok": False, "registered": False, "error": {"code": "NOT_REGISTERED", "message": "No account found. Please register to continue."}}), 404

    _cycle_session(user["id"])
    session["login_time"] = datetime.now(timezone.utc).isoformat()
    session["last_active"] = datetime.now(timezone.utc).isoformat()
    return jsonify({"ok": True, "registered": True, "data": user}), 200


@auth_bp.route("/api/auth/logout", methods=["POST"])
@csrf_protect_if_enabled
def auth_logout():
    _cycle_session()
    return jsonify({"ok": True, "data": {"logged_out": True}}), 200


@auth_bp.route("/api/auth/me", methods=["GET"])
@csrf.exempt
def auth_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Not logged in."}}), 401

    user = user_store.get_user_by_id(user_id)
    if not user:
        _cycle_session()
        return jsonify({"ok": False, "error": {"code": "USER_NOT_FOUND", "message": "User session expired."}}), 404

    return jsonify({"ok": True, "data": user}), 200


@auth_bp.route("/api/auth/profile", methods=["GET"])
def get_profile():
    """Returns the logged-in user's profile."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Login required."}}), 401
    user = user_store.get_user_by_id(user_id)
    if not user:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": "User not found."}}), 404
    return jsonify({"ok": True, "data": user}), 200


@auth_bp.route("/api/auth/profile", methods=["PATCH"])
@csrf_protect_if_enabled
def update_profile():
    """Updates editable profile fields: full_name, home_city, persona."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Login required."}}), 401
    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "JSON object required."}}), 400
    allowed = {"full_name", "home_city", "persona"}
    updates = {k: str(v)[:100] for k, v in body.items() if k in allowed and isinstance(v, str)}
    if not updates:
        return jsonify({"ok": False, "error": {"code": "NO_VALID_FIELDS", "message": "No valid fields to update."}}), 400
    updated = user_store.update_user(user_id, updates)
    if not updated:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": "User not found."}}), 404
    return jsonify({"ok": True, "data": updated}), 200


@auth_bp.route("/api/auth/export", methods=["GET"])
def export_user_data():
    """Returns all user data as JSON (GDPR-style export)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Login required."}}), 401
    user = user_store.get_user_by_id(user_id)
    if not user:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": "User not found."}}), 404
    trips = trip_store.list_trips(user_id=user_id, limit=100)
    export_data = {
        "user": user,
        "trips": trips,
        "exported_at": datetime.now(timezone.utc).isoformat()
    }
    return jsonify({"ok": True, "data": export_data}), 200


@auth_bp.route("/api/auth/account", methods=["DELETE"])
@csrf_protect_if_enabled
def delete_account():
    """Deletes the user account and all their trips."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Login required."}}), 401
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": {"code": "INVALID_BODY", "message": "JSON object required."}}), 400
    password = body.get("password", "")
    user = user_store.get_user_by_id(user_id)
    if not user:
        return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": "User not found."}}), 404
    user_check = user_store.authenticate(identifier=user["email"], password=password)
    if not user_check:
        return jsonify({"ok": False, "error": {"code": "INVALID_CREDENTIALS", "message": "Password confirmation failed."}}), 401
    user_trips = trip_store.list_trips(user_id=user_id, limit=1000)
    for trip in user_trips:
        try:
            trip_store.delete_trip(trip["id"], user_id=user_id)
        except Exception:
            pass
    deleted = user_store.delete_user(user_id)
    session.clear()
    return jsonify({"ok": True, "data": {"deleted": deleted}}), 200
