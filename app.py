"""
Namma Payana - Main Flask Application & REST API
Deterministic, constraint-aware Karnataka travel planner.
"""
import os
import json as _json
import uuid as _request_uuid
import logging
import secrets
from datetime import datetime, timezone, timedelta
from flask import Flask, request, render_template, Response, session, g
from flask_cors import CORS
from pydantic import ValidationError

import config


# ─── Logging Setup ────────────────────────────────────────────────────────────

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        if record.exc_info:
            log_data["exc"] = self.formatException(record.exc_info)
        return _json.dumps(log_data, ensure_ascii=False)


_log_handler = logging.StreamHandler()
_log_handler.setFormatter(JsonFormatter())
logging.root.setLevel(logging.INFO)
logging.root.handlers = [_log_handler]


class _RequestIdFilter(logging.Filter):
    def filter(self, record):
        try:
            record.request_id = getattr(g, "request_id", None)
        except RuntimeError:
            # Outside application context (e.g. during tests or startup)
            record.request_id = None
        return True


_log_handler.addFilter(_RequestIdFilter())
logger = logging.getLogger("nammapayana")


# ─── Application Factory ──────────────────────────────────────────────────────

def create_app(config_override=None):
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates"
    )

    # ── Config ──
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV", "").lower() == "production"
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
    app.config["SUPABASE_URL"] = config.SUPABASE_URL
    app.config["SUPABASE_ANON_KEY"] = config.SUPABASE_ANON_KEY
    app.config["WTF_CSRF_CHECK_DEFAULT"] = False
    app.config["WTF_CSRF_ENABLED"] = True

    if config_override:
        app.config.update(config_override)

    # ── Extensions ──
    from blueprints.extensions import limiter, csrf
    CORS(app, origins=config.ALLOWED_ORIGINS, supports_credentials=True)
    limiter.init_app(app)
    csrf.init_app(app)

    # ── DB init ──
    from services.user_store import user_store
    user_store.init_db(app)

    # ── Blueprints ──
    from blueprints.auth_bp import auth_bp
    from blueprints.trips_bp import trips_bp
    from blueprints.destinations_bp import destinations_bp
    from blueprints.health_bp import health_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(destinations_bp)
    app.register_blueprint(health_bp)

    # ── Before-request hooks ──

    @app.before_request
    def generate_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.before_request
    def inject_request_id():
        g.request_id = str(_request_uuid.uuid4())[:8]

    @app.before_request
    def check_session_timeout():
        """Enforce idle (2h) and absolute (24h) session timeouts."""
        if request.method == "OPTIONS":
            return
        if "user_id" not in session:
            return
        now = datetime.now(timezone.utc)
        last_active = session.get("last_active")
        login_time = session.get("login_time")
        idle_limit = timedelta(hours=2)
        absolute_limit = timedelta(hours=24)

        if last_active:
            try:
                last_dt = datetime.fromisoformat(last_active)
                if now - last_dt > idle_limit:
                    session.clear()
                    return
            except ValueError:
                session.clear()
                return

        if login_time:
            try:
                login_dt = datetime.fromisoformat(login_time)
                if now - login_dt > absolute_limit:
                    session.clear()
                    return
            except ValueError:
                session.clear()
                return

        session["last_active"] = now.isoformat()

    # ── After-request hook ──

    @app.after_request
    def set_security_headers(response: Response) -> Response:
        nonce = getattr(g, "csp_nonce", "")
        csp = (
            f"default-src 'self'; "
            f"script-src 'self' 'unsafe-inline' 'unsafe-eval' 'nonce-{nonce}' https://unpkg.com https://cdn.jsdelivr.net; "
            f"script-src-elem 'self' 'unsafe-inline' 'nonce-{nonce}' https://unpkg.com https://cdn.jsdelivr.net; "
            f"script-src-attr 'unsafe-inline'; "
            f"style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; "
            f"img-src 'self' data: blob: https://tile.openstreetmap.org https://*.tile.openstreetmap.org https://*.tile.osm.org https://server.arcgisonline.com https://*.arcgisonline.com https://*.basemaps.cartocdn.com https://images.unsplash.com https://upload.wikimedia.org https://unpkg.com; "
            f"connect-src 'self' https://*.supabase.co https://unpkg.com https://cdn.jsdelivr.net https://tile.openstreetmap.org https://*.tile.openstreetmap.org https://server.arcgisonline.com https://*.basemaps.cartocdn.com data:; "
            f"font-src 'self' https://fonts.gstatic.com data:; "
            f"object-src 'none'; "
            f"frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers.remove("X-XSS-Protection")
        if os.environ.get("FLASK_ENV", "").lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # ── Error handlers ──

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return _json.dumps({
            "ok": False,
            "error": {
                "code": "PAYLOAD_TOO_LARGE",
                "message": "Request body exceeds the 64 KB limit."
            }
        }), 413, {"Content-Type": "application/json"}

    @app.errorhandler(404)
    def resource_not_found(error):
        from flask import jsonify
        return jsonify({
            "ok": False,
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested resource was not found."
            }
        }), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        from flask import jsonify
        logger.exception("Internal error occurred: %s", error)
        return jsonify({
            "ok": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again."
            }
        }), 500

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        from flask import jsonify
        return jsonify({"ok": False, "error": {"code": "RATE_LIMITED", "message": "Too many attempts. Try again later."}}), 429

    # ── Static / template routes ──

    @app.route("/favicon.ico")
    def favicon():
        return app.send_static_file("favicon.ico")

    @app.route("/")
    @app.route("/login")
    @app.route("/register")
    @app.route("/signin")
    @app.route("/journey")
    @app.route("/map")
    @app.route("/kannada")
    @app.route("/saved")
    def index():
        return render_template("index.html", config=app.config)

    return app


# Module-level app so `from app import app` in conftest.py and wsgi.py still works.
app = create_app()

# Re-export extension and route function references for backward compatibility
# with existing tests that import them directly from app.
from blueprints.extensions import limiter  # noqa: E402  (test_phase0b_auth does `from app import limiter`)
from blueprints.trips_bp import save_trip  # noqa: E402  (test_phase10_auth does `app_module.save_trip`)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
