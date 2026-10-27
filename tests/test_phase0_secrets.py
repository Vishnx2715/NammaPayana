"""
Phase 0 — Secret Hygiene Tests.
These tests prove secrets are no longer hardcoded and the app works offline without them.
"""
import os
import re
import pathlib
import pytest


REPO_ROOT = pathlib.Path(__file__).parent.parent


def test_no_gemini_key_in_config_py():
    """config.py must not contain any hardcoded Gemini API key."""
    src = (REPO_ROOT / "config.py").read_text(encoding="utf-8")
    # The specific leaked key must not appear
    assert "AQ.Ab8RN6IUFVeCE3" not in src
    # No fallback string assignment with AQ. pattern
    assert not re.search(r'or\s*["\']AQ\.', src), \
        "config.py contains a hardcoded Gemini key fallback"


def test_no_supabase_credentials_in_config_py():
    """config.py must not contain hardcoded Supabase URL or keys."""
    src = (REPO_ROOT / "config.py").read_text(encoding="utf-8")
    assert "REDACTED_SUPABASE_HOST" not in src
    assert "sb_publishable_U0r-" not in src
    # The anon key JWT must not appear as a literal default
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIs" not in src


def test_no_secrets_in_translator_py():
    """services/translator.py must not contain any hardcoded Gemini key fallback."""
    src = (REPO_ROOT / "services" / "translator.py").read_text(encoding="utf-8")
    assert "AQ.Ab8RN6IUFVeCE3" not in src
    assert not re.search(r'api_key\s*=\s*["\']AQ\.', src), \
        "translator.py contains a hardcoded API key assignment"


def test_translator_works_offline_without_api_key(monkeypatch):
    """
    Translator must return a valid lexicon result when GEMINI_API_KEY is absent.
    Proves the offline fallback works without any API credentials.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "")
    # Re-import config so the monkeypatched env is picked up
    import importlib
    import config as cfg
    importlib.reload(cfg)

    from services.translator import translator_service
    result = translator_service.translate("where is the bus stand", "en")
    assert result["ok"] is True
    assert "\u0cac\u0cb8\u0ccd \u0ca8\u0cbf\u0cb2\u0ccd\u0ca6\u0cbe\u0ca3" in result["data"]["kannada"]
    assert result["data"]["verified"] is True
    assert result["data"]["source"] == "Namma Payana Verified Lexicon"
