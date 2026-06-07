"""Phase M milestone 3 — online-first transport policy + model decorrelation (doc 11 §5)."""

from __future__ import annotations

import pytest

from osintenal.adapters.transport import AdapterError, Cassette, HttpClient, request_key
from osintenal.inference import build_gateway, gateway_status


# -- transport mode resolution ----------------------------------------------
def test_mode_resolution_precedence(tmp_path, monkeypatch):
    cass = Cassette(tmp_path / "c.json")
    assert HttpClient(cass, record=False).mode == "replay"
    assert HttpClient(cass, record=True).mode == "record"
    assert HttpClient(cass, mode="live").mode == "live"
    monkeypatch.setenv("OSINTENAL_NET", "live")
    assert HttpClient(cass).mode == "live"
    monkeypatch.delenv("OSINTENAL_NET")
    monkeypatch.setenv("OSINTENAL_RECORD", "1")
    assert HttpClient(cass).mode == "record"
    monkeypatch.delenv("OSINTENAL_RECORD")
    assert HttpClient(cass).mode == "replay"          # safe default


def test_replay_mode_errors_on_missing_entry(tmp_path):
    client = HttpClient(Cassette(tmp_path / "empty.json"), mode="replay")
    with pytest.raises(AdapterError):
        client.get_json("http://api/x", {"q": "1"})


def test_replay_serves_recorded_entry_without_network(tmp_path):
    cass = Cassette(tmp_path / "c.json")
    cass.put(request_key("GET", "http://api/x", {"q": "1"}),
             {"url": "http://api/x", "text": '{"ok": true}'})
    assert HttpClient(Cassette(tmp_path / "c.json"), mode="replay").get_json(
        "http://api/x", {"q": "1"}) == {"ok": True}


def test_live_mode_fetches_and_ignores_cassette(tmp_path, monkeypatch):
    # patch the network so 'live' is testable without egress
    import osintenal.adapters.transport as t

    class _Resp:
        def __init__(self, data): self._data = data
        def read(self): return self._data
        def __enter__(self): return self
        def __exit__(self, *a): return False

    captured = {}

    def fake_urlopen(req, timeout=30):
        captured["url"] = req.full_url
        return _Resp(b'{"live": true}')

    monkeypatch.setattr(t.urllib.request, "urlopen", fake_urlopen)

    cass = Cassette(tmp_path / "c.json")
    # even with a (stale) recorded entry, live ignores it and fetches fresh
    cass.put(request_key("GET", "http://api/x", None), {"url": "http://api/x", "text": "stale"})
    client = HttpClient(Cassette(tmp_path / "c.json"), mode="live")
    assert client.get_json("http://api/x") == {"live": True}
    assert captured["url"].startswith("http://api/x")


def test_record_mode_persists_fetched_response(tmp_path, monkeypatch):
    import osintenal.adapters.transport as t

    class _Resp:
        def read(self): return b'{"v": 1}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(t.urllib.request, "urlopen", lambda req, timeout=30: _Resp())
    path = tmp_path / "c.json"
    HttpClient(Cassette(path), mode="record").get_json("http://api/y")
    # the response is now in the cassette and replays offline
    assert HttpClient(Cassette(path), mode="replay").get_json("http://api/y") == {"v": 1}


# -- model decorrelation -----------------------------------------------------
def test_skeptic_decorrelation_routes_to_a_different_model(tmp_path, monkeypatch):
    monkeypatch.setenv("OSINTENAL_INFERENCE_PROFILE", "ollama")
    monkeypatch.setenv("OSINTENAL_SKEPTIC_PROFILE", "groq")
    gw = build_gateway(cassette_dir=tmp_path, record=False)
    assert gw.role_models["skeptic"] == "llama-3.3-70b-versatile"     # groq's reason model
    assert gw.models["reason"] == "qwen2.5:14b-instruct"               # connections stay local
    assert "skeptic" in gw.role_providers
    # the Skeptic provider is a distinct instance from the reason-tier provider
    assert gw.role_providers["skeptic"] is not gw.providers["reason"]


def test_status_reports_overrides_and_net_mode(monkeypatch):
    monkeypatch.setenv("OSINTENAL_INFERENCE_PROFILE", "ollama")
    monkeypatch.setenv("OSINTENAL_SKEPTIC_PROFILE", "gemini")
    monkeypatch.setenv("OSINTENAL_NET", "live")
    st = gateway_status()
    assert st["skeptic_override"] == "gemini" and st["net_mode"] == "live"


def test_no_decorrelation_by_default(tmp_path):
    gw = build_gateway(profile="ollama", cassette_dir=tmp_path, record=False)
    assert gw.role_providers == {} and gw.role_models == {}
