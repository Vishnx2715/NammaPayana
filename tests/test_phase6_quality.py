import pathlib
import json
import sys

REPO = pathlib.Path(__file__).parent.parent


def test_db_module_exists():
    assert (REPO / "services" / "db.py").exists()


def test_pyproject_toml_exists():
    assert (REPO / "pyproject.toml").exists()


def test_requirements_dev_exists():
    assert (REPO / "requirements-dev.txt").exists()


def test_pytest_not_in_runtime_requirements():
    reqs = (REPO / "requirements.txt").read_text()
    assert "pytest" not in reqs, "pytest should be in requirements-dev.txt, not requirements.txt"


def test_health_endpoint_includes_db_status(client):
    resp = client.get("/api/health")
    data = resp.get_json()
    assert data["ok"] is True
    assert "db" in data["data"]
    assert data["data"]["db"] == "ok"


def test_health_endpoint_includes_routing_provider(client):
    resp = client.get("/api/health")
    data = resp.get_json()
    assert "routing_provider" in data["data"]
    assert "Provider" in data["data"]["routing_provider"]


def test_wal_mode_enabled():
    from services.db import db_connection
    import config
    import os
    test_db = config.DATABASE_PATH
    if not os.path.exists(test_db):
        return  # skip if no DB file
    with db_connection(test_db) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
