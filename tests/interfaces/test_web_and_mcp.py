"""The two front doors: the local web app and the MCP server."""

from __future__ import annotations

from osintinel.interfaces.mcp import TOOLS, handle_request
from osintinel.interfaces.web import (
    build_result_page,
    model_label,
    parse_form,
    render_form,
    run_and_store,
)


# -- web app -----------------------------------------------------------------
def test_form_renders_with_fields():
    html = render_form()
    assert html.startswith("<!doctype html>")
    for field in ('name="question"', 'name="candidates"', 'name="evidence"', "/investigate"):
        assert field in html
    assert "http://" not in html and "https://" not in html  # offline, self-contained


def test_parse_form_reads_candidates_and_evidence():
    q, cands, ev = parse_form({
        "question": ["What is it?"],
        "candidates": ["mast\nturbine\nwater tower"],
        "evidence": ["OpenStreetMap | man_made=mast | 1\nLocal news | 'the turbine' | 2"]})
    assert q == "What is it?" and cands == ["mast", "turbine", "water tower"]
    assert [(e.source, e.supports) for e in ev] == [("OpenStreetMap", 0), ("Local news", 1)]


def test_run_and_store_then_result_page_is_dashboard():
    rid = run_and_store("Mast or turbine?", ["communications mast", "wind turbine"],
                        parse_form({"question": ["x"], "candidates": ["x"],
                                    "evidence": ["OSM | man_made=mast | 1"]})[2])
    page = build_result_page(rid)
    assert page and "<svg" in page and "resultnav" in page  # dashboard + result nav banner
    assert build_result_page("nonexistent") is None


def test_form_has_a_model_picker_with_every_profile():
    html = render_form()
    assert 'name="profile"' in html and "Launch default" in html
    for name in ("deterministic", "ollama", "gemini"):
        assert f'value="{name}"' in html


def test_model_picker_label_recorded_on_the_result_page():
    rid = run_and_store("Mast or turbine?", ["communications mast", "wind turbine"],
                        parse_form({"question": ["x"], "candidates": ["x"],
                                    "evidence": ["OSM | man_made=mast | 1"]})[2],
                        profile="deterministic")
    page = build_result_page(rid)
    assert "model:" in page and "deterministic" in page


def test_model_label_describes_deterministic_floor():
    assert "no model" in model_label("deterministic")


# -- live HTTP round-trip ----------------------------------------------------
def test_http_server_serves_form_and_runs_investigation():
    import threading
    import urllib.parse
    import urllib.request
    from http.server import ThreadingHTTPServer

    from osintinel.interfaces.web.app import _Handler

    srv = ThreadingHTTPServer(("127.0.0.1", 8794), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert urllib.request.urlopen("http://127.0.0.1:8794/health").read() == b"ok"
        data = urllib.parse.urlencode({
            "question": "Mast or turbine?", "candidates": "communications mast\nwind turbine",
            "evidence": "OpenStreetMap | man_made=mast | 1"}).encode()
        body = urllib.request.urlopen(
            urllib.request.Request("http://127.0.0.1:8794/investigate", data=data)).read().decode()
        assert "<svg" in body and "Investigation Console" in body  # redirected to the dashboard
    finally:
        srv.shutdown()


# -- MCP server --------------------------------------------------------------
def test_mcp_initialize_and_tools_list():
    init = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "osintinel"
    assert "tools" in init["result"]["capabilities"]
    names = {t["name"] for t in handle_request(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]}
    assert names == {"investigate", "models_status"}
    assert names == {t["name"] for t in TOOLS}


def test_mcp_investigate_tool_returns_report_text():
    resp = handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "investigate",
        "arguments": {"question": "Mast or turbine?",
                      "candidates": ["communications mast", "wind turbine"],
                      "evidence": [{"text": "OSM man_made=mast", "source": "osm", "supports": 1}]}}})
    text = resp["result"]["content"][0]["text"]
    assert "communications mast" in text and "Ranked hypotheses" in text
    assert resp["result"].get("isError") in (None, False)


def test_mcp_models_status_tool():
    resp = handle_request({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                           "params": {"name": "models_status", "arguments": {}}})
    assert "profile:" in resp["result"]["content"][0]["text"]


def test_mcp_unknown_tool_and_method():
    bad_tool = handle_request({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                               "params": {"name": "nope"}})
    assert bad_tool["result"]["isError"] is True
    bad_method = handle_request({"jsonrpc": "2.0", "id": 6, "method": "bogus"})
    assert bad_method["error"]["code"] == -32601


def test_mcp_notification_returns_no_response():
    assert handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


# -- OSINTINEL Web (comprehensive console) ------------------------------------
def test_render_form_has_autonomous_and_photo_and_advanced():
    from osintinel.interfaces.web import render_form
    h = render_form()
    for token in ('name="autonomous"', 'type="file"', 'name="photo"',
                  'name="reason_model"', 'enctype="multipart/form-data"'):
        assert token in h
    assert "http://" not in h and "https://" not in h  # form stays self-contained/offline


def test_parse_multipart_extracts_fields_and_file():
    from osintinel.interfaces.web import parse_multipart
    boundary = b"BOUND"
    body = (b'--BOUND\r\nContent-Disposition: form-data; name="question"\r\n\r\nWhat?\r\n'
            b'--BOUND\r\nContent-Disposition: form-data; name="photo"; filename="a.jpg"\r\n'
            b'Content-Type: image/jpeg\r\n\r\n\xff\xd8data\r\n'
            b'--BOUND--\r\n')
    fields, files = parse_multipart(body, boundary)
    assert fields["question"] == ["What?"]
    assert files["photo"][0] == "a.jpg" and files["photo"][1] == b"\xff\xd8data"


def test_render_history_lists_saved_runs():
    from osintinel.interfaces.web import parse_form, render_history, run_and_store
    run_and_store("Mast or turbine?", ["mast", "turbine"],
                  parse_form({"question": ["x"], "candidates": ["x"],
                              "evidence": ["OSM | man_made=mast | 1"]})[2], profile="deterministic")
    h = render_history()
    assert "History" in h and "Mast or turbine?" in h


def test_web_photo_result_renders_geotag_and_sun():
    from osintinel.adapters.media.exif import write_exif_jpeg
    from osintinel.interfaces.web import render_photo_result
    from osintinel.service.photo import analyze_photo
    jpg = write_exif_jpeg(make="Canon", model="EOS 80D",
                          datetime_original="2021:06:21 14:30:00",
                          lat=51.0153, lon=-1.3253, altitude_m=118.0)
    h = render_photo_result(analyze_photo(jpg), "shot.jpg")
    assert "Geotag" in h and "51.0153" in h and "shadows point" in h


def test_render_form_has_detect_per_tier_and_js():
    from osintinel.interfaces.web import render_form
    h = render_form()
    assert 'onclick="detect()"' in h and 'id="models_dl"' in h and 'list="models_dl"' in h
    assert "<script>" in h and 'name="reason_model"' in h and 'name="embed_model"' in h
    assert "http://" not in h and "https://" not in h  # endpoint URLs resolved server-side


def test_detect_models_resolves_profile_base(monkeypatch):
    from osintinel.interfaces.web import detect_models
    monkeypatch.setattr("osintinel.inference.list_installed_models",
                        lambda base: ["dollamin:latest", "nomic-embed-text"] if base else [])
    assert detect_models({"profile": ["ollama"]})["models"] == ["dollamin:latest", "nomic-embed-text"]
    assert detect_models({"profile": ["deterministic"]})["models"] == []  # no endpoint → none


def test_mcp_investigate_autonomous_routes_to_web_research(monkeypatch):
    seen = {}

    def fake_research(question, candidates=None, gateway=None, rounds=3, web_adapter=None):
        seen["q"], seen["rounds"] = question, rounds
        from osintinel.service import run_investigation
        return run_investigation(question=question, candidates=candidates or ["yes", "no"],
                                 evidence=[], gateway=gateway)

    monkeypatch.setattr("osintinel.interfaces.mcp.server.run_web_research", fake_research)
    resp = handle_request({"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {
        "name": "investigate",
        "arguments": {"question": "Who built the ridge mast?", "autonomous": True, "rounds": 2}}})
    text = resp["result"]["content"][0]["text"]
    assert seen["q"] == "Who built the ridge mast?" and seen["rounds"] == 2
    assert "Ranked hypotheses" in text and resp["result"].get("isError") in (None, False)


def test_form_wears_the_dashboard_console_chrome():
    from osintinel.interfaces.web import render_form
    h = render_form()
    assert "Investigation Console" in h and 'class="ladder"' in h
    for rung in ("information", "hypothesis", "insight"):  # the epistemic-ladder bar
        assert f">{rung}<" in h
