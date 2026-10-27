import pathlib
REPO = pathlib.Path(__file__).parent.parent


def test_readme_exists_and_has_content():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert len(readme) > 2000, "README is too short"
    assert "117" in readme or "tests" in readme.lower()
    assert "deterministic" in readme.lower()
    assert "SECRET_KEY" in readme


def test_readme_honest_ai_statement():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "offline" in readme.lower()
    assert "gemini" in readme.lower()
    assert "narrative" in readme.lower() or "translation" in readme.lower()


def test_changelog_exists():
    assert (REPO / "CHANGELOG.md").exists()
    content = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Security" in content
    assert "Phase 0" in content or "authentication" in content.lower()


def test_architecture_md_exists():
    assert (REPO / "ARCHITECTURE.md").exists()
    content = (REPO / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "deterministic" in content.lower() or "engine" in content.lower()


def test_contributing_md_exists():
    assert (REPO / "CONTRIBUTING.md").exists()


def test_privacy_md_exists():
    assert (REPO / "PRIVACY.md").exists()
    content = (REPO / "PRIVACY.md").read_text(encoding="utf-8")
    assert "password" in content.lower()
    assert "delete" in content.lower()


def test_env_example_has_no_real_secrets():
    import re
    env = (REPO / ".env.example").read_text(encoding="utf-8")
    assert not re.search(r'AQ\.[A-Za-z0-9_\-]{10,}', env), ".env.example contains real Gemini key"
    assert "xkzzwori" not in env, ".env.example contains real Supabase URL"
