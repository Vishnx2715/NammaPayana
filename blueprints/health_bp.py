"""Health check blueprint."""
from flask import Blueprint, jsonify
import config
from services.destination_service import destination_service
from blueprints.extensions import csrf

health_bp = Blueprint("health_bp", __name__)


@health_bp.route("/api/health", methods=["GET"])
@csrf.exempt
def health_check():
    db_ok = False
    try:
        from services.db import db_connection
        with db_connection() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    from services.routing import routing_provider
    routing_health = routing_provider.health_check()
    return jsonify({
        "ok": True,
        "data": {
            "status": "healthy",
            "version": "2.0",
            "destinations_count": len(destination_service.get_all()),
            "service": "Namma Payana Trip Reality Engine",
            "db": "ok" if db_ok else "error",
            "ai_provider": config.AI_PROVIDER,
            "routing_provider": type(routing_provider).__name__,
            "routing": routing_health,
        }
    }), 200
