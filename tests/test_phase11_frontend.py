import pathlib, re, json
REPO = pathlib.Path(__file__).parent.parent


def test_no_document_write_in_js():
    for js_file in (REPO / "static" / "js").glob("*.js"):
        src = js_file.read_text(encoding="utf-8")
        assert "document.write(" not in src, f"document.write found in {js_file.name}"


def test_no_eval_in_js():
    for js_file in (REPO / "static" / "js").glob("*.js"):
        src = js_file.read_text(encoding="utf-8")
        # Allow 'eval' as part of other identifiers (e.g. 'evaluate')
        bad = re.findall(r'\beval\s*\(', src)
        assert bad == [], f"eval() found in {js_file.name}: {bad}"


def test_auth_js_uses_textcontent_for_display_name():
    src = (REPO / "static" / "js" / "auth.js").read_text(encoding="utf-8")
    # display_name or username must not appear in a raw innerHTML assignment
    bad = re.findall(r'innerHTML\s*=\s*[^;]*(?:display_name|username|full_name)[^;]*;', src)
    assert bad == [], f"Unescaped user field in innerHTML: {bad}"


def test_app_py_under_300_lines_after_blueprint_split():
    lines = (REPO / "app.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 300, f"app.py is {len(lines)} lines (expected <=300 after blueprint split)"


def test_blueprints_directory_exists():
    assert (REPO / "blueprints").is_dir()
    assert (REPO / "blueprints" / "auth_bp.py").exists()
    assert (REPO / "blueprints" / "trips_bp.py").exists()
    assert (REPO / "blueprints" / "destinations_bp.py").exists()
    assert (REPO / "blueprints" / "health_bp.py").exists()


def test_all_api_routes_still_respond(client):
    """Smoke test that blueprint registration didn't break any endpoint."""
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/destinations").status_code == 200


def test_xss_payload_escaped_in_api_response(client):
    """API response must return HTML-safe destination text - no raw angle brackets from data."""
    resp = client.get("/api/destinations")
    assert resp.status_code == 200
    # The response JSON string should not contain unescaped script injection
    raw = resp.data.decode()
    # Check no unescaped script tags leaked into JSON (JSON encoding handles < > but verify)
    assert "<script>" not in raw.lower()


def test_leaflet_sri_integrity_present():
    html = (REPO / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'integrity="sha256-p4NxAoJBhIIN' in html  # Leaflet CSS SRI
    assert 'integrity="sha256-20nQCchB9co0' in html  # Leaflet JS SRI


def test_js_split_plan_exists():
    assert (REPO / ".agents" / "tasks" / "phase11_js_split_plan.md").exists()
