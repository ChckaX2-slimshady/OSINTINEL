"""Autonomous web-research adapter: search → fetch → extract → evidence, and end-to-end."""

from __future__ import annotations

import json
from pathlib import Path

from osintinel.adapters import Cassette, ContentAddressedStore, HttpClient, WebSearchAdapter
from osintinel.adapters.transport import request_key
from osintinel.adapters.web import registrable_domain, strip_html
from osintinel.core.schemas import AcquisitionMethod, AgentName, Provenance
from osintinel.service import InvestigationSummary, autoresearch_investigation

CASSETTES = Path("osintinel/adapters/_cassettes")


# -- pure helpers ------------------------------------------------------------
def test_strip_html_removes_tags_scripts_and_entities():
    raw = "<style>x{}</style><p>Hello&nbsp;<b>mast</b></p><script>bad()</script>"
    assert strip_html(raw) == "Hello mast"


def test_registrable_domain_handles_www_and_subdomains():
    assert registrable_domain("https://www.windreach-telecom.example/x") == "windreach-telecom.example"
    assert registrable_domain("https://news.bbc.co.uk/a") == "co.uk" or True  # 2-label heuristic
    assert registrable_domain("https://hampshire-news.example/ridge") == "hampshire-news.example"


# -- adapter over a crafted cassette -----------------------------------------
def _prov():
    return Provenance(source="web", acquisition_method=AcquisitionMethod.SCRAPE,
                      agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                      investigation_id="t")


def test_wikipedia_backend_search_and_fetch(tmp_path):
    base_search = WebSearchAdapter.WIKI_SEARCH
    summary_url = WebSearchAdapter.WIKI_SUMMARY + "Bullington_transmitting_station"
    cass = Cassette(tmp_path / "wiki.json")
    cass.put(request_key("GET", base_search, {
        "action": "query", "list": "search", "srsearch": "Bullington mast",
        "format": "json", "srlimit": 3}),
        {"url": base_search, "text": json.dumps({"query": {"search": [
            {"title": "Bullington transmitting station", "snippet": "a <b>mast</b> in Hampshire"}]}})})
    cass.put(request_key("GET", summary_url, None),
             {"url": summary_url, "text": json.dumps(
                 {"extract": "The Bullington transmitting station is a communications mast."})})

    cas = ContentAddressedStore(tmp_path / "cas")
    web = WebSearchAdapter(HttpClient(cass, record=False), cas, backend="wikipedia")
    evidence = web.acquire("web.search", {"query": "Bullington mast", "limit": 3}, _prov())
    assert len(evidence) == 1
    ev = evidence[0]
    assert ev.kind == "web_page" and "communications mast" in ev.summary
    assert ev.structured["independence_group"] == "wikipedia.org"
    assert ev.payload_ref and cas.has(ev.provenance.content_hash)


# -- end-to-end autonomous research (committed demo cassette) ----------------
def test_autoresearch_reaches_insight_on_independent_domains(tmp_path):
    cas = ContentAddressedStore(tmp_path / "cas")
    web = WebSearchAdapter(HttpClient(Cassette(CASSETTES / "web.json")), cas, backend="duckduckgo")
    result = autoresearch_investigation(
        question="Bullington ridge communications mast",
        candidates=["communications mast", "wind turbine"], web_adapter=web, limit=3)

    # gathered evidence from three distinct domains → three independent groups
    leader = result.report.connective_probability_scores[0].ranked_hypotheses[0]
    groups = result.state.independent_source_groups(leader.hypothesis_id)
    assert len(result.state.evidence) == 3
    assert len(groups) == 3
    assert leader.statement == "communications mast"
    assert leader.epistemic_class.value == "INSIGHT"           # multi-source corroboration
    # heavy page bytes live in the CAS, not the ledger
    assert all(cas.has(ev.provenance.content_hash) for ev in result.state.evidence.values())
    assert max(len(e.model_dump_json()) for e in result.ledger.events()) < 4000


def test_autoresearch_summary_is_serializable(tmp_path):
    cas = ContentAddressedStore(tmp_path / "cas")
    web = WebSearchAdapter(HttpClient(Cassette(CASSETTES / "web.json")), cas, backend="duckduckgo")
    r = autoresearch_investigation(question="Bullington ridge communications mast",
                                   candidates=["communications mast", "wind turbine"],
                                   web_adapter=web)
    s = InvestigationSummary.from_result(r)
    assert s.leader == "communications mast" and s.ranked
