"""The two front doors: the local web app and the MCP server."""

from __future__ import annotations

from osintinel.interfaces.mcp import TOOLS, handle_request
from osintinel.interfaces.web import (
    build_result_page,
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
    assert page and "<svg" in page and "New investigation" in page  # dashboard + banner
    assert build_result_page("nonexistent") is None


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
