import pathlib, subprocess, sys
REPO = pathlib.Path(__file__).parent.parent

def test_dockerfile_exists():
    assert (REPO / "Dockerfile").exists()

def test_dockerignore_exists():
    di = (REPO / ".dockerignore").read_text(encoding="utf-8")
    assert ".env" in di
    assert "instance/" in di or "*.db" in di

def test_docker_compose_exists():
    assert (REPO / "docker-compose.yml").exists()
    content = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "healthcheck" in content
    assert "db_data" in content

def test_backup_script_exists():
    assert (REPO / "scripts" / "backup_db.sh").exists()

def test_wsgi_imports_app():
    wsgi = (REPO / "wsgi.py").read_text(encoding="utf-8")
    assert "from app import app" in wsgi or "import app" in wsgi

def test_gunicorn_conf_has_workers():
    conf = (REPO / "gunicorn.conf.py").read_text(encoding="utf-8")
    assert "workers" in conf
    assert "WEB_CONCURRENCY" in conf

def test_health_endpoint_returns_ok(client):
    resp = client.get("/api/health")
    data = resp.get_json()
    assert data["ok"] is True
    assert data["data"]["status"] == "healthy"
    assert data["data"]["version"] == "2.0"

def test_dockerfile_does_not_copy_env():
    df = (REPO / "Dockerfile").read_text(encoding="utf-8")
    # Should not COPY .env file
    assert "COPY .env" not in df
    # Should have non-root user
    assert "useradd" in df or "USER " in df
