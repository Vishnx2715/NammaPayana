"""
Tests for Kannada Translator Service & API Endpoint.
"""
import pytest
from app import app
from services.translator import translator_service

def test_translator_lexicon_english():
    res = translator_service.translate("where is the bus stand", "en")
    assert res["ok"] is True
    data = res["data"]
    assert "ಬಸ್ ನಿಲ್ದಾಣ" in data["kannada"]
    assert "Bus nildana" in data["transliteration"]
    assert "meaning" in data and len(data["meaning"]) > 0
    assert data["verified"] is True

def test_translator_lexicon_hindi():
    res = translator_service.translate("पीने का पानी कहाँ मिलेगा", "hi")
    assert res["ok"] is True
    data = res["data"]
    assert "ನೀರು" in data["kannada"]
    assert "meaning" in data and len(data["meaning"]) > 0
    assert data["verified"] is True

def test_translator_lexicon_telugu():
    res = translator_service.translate("నమస్కారం", "te")
    assert res["ok"] is True
    data = res["data"]
    assert "ನಮಸ್ಕಾರ" in data["kannada"]
    assert "meaning" in data and len(data["meaning"]) > 0
    assert data["verified"] is True

def test_translator_api_endpoint():
    client = app.test_client()
    resp = client.post("/api/translate", json={
        "text": "How much is the auto fare",
        "source_lang": "en"
    })
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["ok"] is True
    assert "ಆಟೋ" in json_data["data"]["kannada"]
    assert "meaning" in json_data["data"] and len(json_data["data"]["meaning"]) > 0

def test_translator_empty_text():
    client = app.test_client()
    resp = client.post("/api/translate", json={"text": "   "})
    assert resp.status_code == 400
    json_data = resp.get_json()
    assert json_data["ok"] is False

def test_translator_hinglish():
    res = translator_service.translate("pani kahan milega", "hi")
    assert res["ok"] is True
    assert "ನೀರು" in res["data"]["kannada"]
    assert "meaning" in res["data"] and len(res["data"]["meaning"]) > 0

def test_translator_tanglish():
    res = translator_service.translate("thanni kudunga", "ta")
    assert res["ok"] is True
    assert "ನೀರು" in res["data"]["kannada"]
    assert "meaning" in res["data"] and len(res["data"]["meaning"]) > 0

def test_translator_manglish():
    res = translator_service.translate("auto kooli ethraya", "ml")
    assert res["ok"] is True
    assert "ಆಟೋ" in res["data"]["kannada"]
    assert "meaning" in res["data"] and len(res["data"]["meaning"]) > 0

def test_translator_tenglish():
    res = translator_service.translate("manchineellu ekkada dorukuthayi", "te")
    assert res["ok"] is True
    assert "ನೀರು" in res["data"]["kannada"]
    assert "meaning" in res["data"] and len(res["data"]["meaning"]) > 0


