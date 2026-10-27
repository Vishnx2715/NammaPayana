import pathlib, re, subprocess, sys
REPO = pathlib.Path(__file__).parent.parent

def test_no_pdf_in_static_images():
    pdfs = list((REPO / "static" / "images").glob("*.pdf"))
    assert pdfs == [], f"PDF files found in static/images: {pdfs}"

def test_gitattributes_exists():
    ga = (REPO / ".gitattributes").read_text(encoding="utf-8")
    assert "text=auto" in ga

def test_ci_yml_exists():
    ci = REPO / ".github" / "workflows" / "ci.yml"
    assert ci.exists(), "CI workflow file missing"

def test_ci_yml_has_pytest():
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "pytest" in ci
    assert "validate_data" in ci

def test_ci_yml_has_all_required_steps():
    """Ensure removal of bandit, mypy, ruff, or gitleaks from CI is caught."""
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "ruff" in ci, "CI is missing ruff lint step"
    assert "mypy" in ci, "CI is missing mypy type-check step"
    assert "bandit" in ci, "CI is missing bandit security scan step"
    assert "gitleaks" in ci, "CI is missing gitleaks secret scan step"

def test_gitattributes_covers_yml_files():
    ga = (REPO / ".gitattributes").read_text(encoding="utf-8")
    assert "*.yml" in ga, ".gitattributes missing *.yml rule"

def test_security_notes_has_correct_publishable_key():
    notes = (REPO / "SECURITY_NOTES.md").read_text(encoding="utf-8")
    assert "sb_publishable_4pOvWswO" in notes, \
        "SECURITY_NOTES.md missing the correct publishable key for git filter-repo"

def test_make_release_script_exists():
    assert (REPO / "scripts" / "make_release.sh").exists()

def test_env_example_no_real_secrets():
    env = (REPO / ".env.example").read_text(encoding="utf-8")
    assert not re.search(r'AQ\.[A-Za-z0-9_\-]{10,}', env)
    assert "xkzzwori" not in env
    assert "sb_publishable_U0r" not in env

def test_gitignore_covers_env_and_db():
    gi = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gi
    assert "instance/" in gi or "*.db" in gi

def test_requirements_in_exists():
    assert (REPO / "requirements.in").exists()
