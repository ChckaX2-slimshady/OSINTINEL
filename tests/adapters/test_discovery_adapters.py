"""New free, keyless adapters: DNS-over-HTTPS, RIPEstat ASN, Wikimedia Commons.

Each test crafts its own cassette inline (the committed demos don't need to grow), exercising the
full search → collect → parse → normalize path and asserting schema-valid evidence with a stable
independence group — exactly the contract the Confidence Agent relies on.
"""

from __future__ import annotations

import json

from osintinel.adapters import (
    Adapter,
    AsnAdapter,
    Cassette,
    DnsAdapter,
    HttpClient,
    WikimediaCommonsAdapter,
)
from osintinel.adapters.registry import AdapterRegistry
from osintinel.adapters.transport import request_key
from osintinel.core.schemas import AcquisitionMethod, AgentName, EvidenceObject, Provenance


def _prov():
    return Provenance(source="x", acquisition_method=AcquisitionMethod.API,
                      agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                      investigation_id="t")


def _client(cass: Cassette) -> HttpClient:
    return HttpClient(cass, record=False)


# -- DNS over HTTPS ----------------------------------------------------------
def _dns_cassette(tmp_path) -> Cassette:
    cass = Cassette(tmp_path / "dns.json")
    answers = {
        "A": [{"name": "windreach-telecom.example.", "type": 1, "TTL": 300,
               "data": "203.0.113.10"}],
        "AAAA": [],
        "MX": [{"name": "windreach-telecom.example.", "type": 15, "TTL": 300,
                "data": "10 mail.windreach-telecom.example."}],
        "NS": [{"name": "windreach-telecom.example.", "type": 2, "TTL": 3600,
                "data": "ns1.windreach-telecom.example."}],
        "TXT": [{"name": "windreach-telecom.example.", "type": 16, "TTL": 300,
                 "data": "v=spf1 -all"}],
    }
    for rtype, ans in answers.items():
        key = request_key("GET", DnsAdapter.API,
                          {"name": "windreach-telecom.example", "type": rtype})
        cass.put(key, {"url": DnsAdapter.API, "text": json.dumps({"Status": 0, "Answer": ans})})
    return cass


def test_dns_conforms_and_aggregates_record_types(tmp_path):
    adapter = DnsAdapter(_client(_dns_cassette(tmp_path)))
    assert isinstance(adapter, Adapter) and "infra.dns" in adapter.capabilities
    ev = adapter.acquire("infra.dns", {"domain": "windreach-telecom.example"}, _prov())[0]
    EvidenceObject.model_validate(ev.model_dump())  # schema-valid round-trip
    assert ev.kind == "dns_records"
    assert ev.structured["independence_group"] == "dns"
    assert ev.structured["ipv4"] == ["203.0.113.10"]
    assert ev.structured["mx"] and ev.structured["txt"] == ["v=spf1 -all"]
    assert "203.0.113.10" in ev.summary
    assert ev.provenance.tool_used == "infra.dns" and ev.provenance.license_note


def test_dns_empty_zone_reads_clean(tmp_path):
    cass = Cassette(tmp_path / "dns.json")
    for rtype in ("A", "AAAA", "MX", "NS", "TXT"):
        cass.put(request_key("GET", DnsAdapter.API, {"name": "void.example", "type": rtype}),
                 {"url": DnsAdapter.API, "text": json.dumps({"Status": 3})})
    ev = DnsAdapter(_client(cass)).acquire("infra.dns", {"domain": "void.example"}, _prov())[0]
    assert "no records" in ev.summary and ev.structured["ipv4"] == []


# -- RIPEstat ASN / network --------------------------------------------------
def test_asn_maps_ip_to_as_and_holder(tmp_path):
    cass = Cassette(tmp_path / "asn.json")
    cass.put(request_key("GET", AsnAdapter.NETWORK_INFO, {"resource": "8.8.8.8"}),
             {"url": AsnAdapter.NETWORK_INFO,
              "text": json.dumps({"data": {"asns": ["15169"], "prefix": "8.8.8.0/24"}})})
    cass.put(request_key("GET", AsnAdapter.AS_OVERVIEW, {"resource": "AS15169"}),
             {"url": AsnAdapter.AS_OVERVIEW,
              "text": json.dumps({"data": {"holder": "GOOGLE, US"}})})
    adapter = AsnAdapter(_client(cass))
    assert isinstance(adapter, Adapter) and "infra.asn" in adapter.capabilities
    ev = adapter.acquire("infra.asn", {"ip": "8.8.8.8"}, _prov())[0]
    EvidenceObject.model_validate(ev.model_dump())
    assert ev.kind == "asn_registration"
    assert ev.structured["independence_group"] == "ripestat"
    assert ev.structured["asns"] == ["15169"] and ev.structured["prefix"] == "8.8.8.0/24"
    assert "AS15169" in ev.summary and "GOOGLE" in ev.summary


def test_asn_unrouted_ip_reads_clean(tmp_path):
    cass = Cassette(tmp_path / "asn.json")
    cass.put(request_key("GET", AsnAdapter.NETWORK_INFO, {"resource": "203.0.113.10"}),
             {"url": AsnAdapter.NETWORK_INFO,
              "text": json.dumps({"data": {"asns": [], "prefix": None}})})
    ev = AsnAdapter(_client(cass)).acquire("infra.asn", {"ip": "203.0.113.10"}, _prov())[0]
    assert "no announced ASN" in ev.summary and ev.structured["asns"] == []


# -- Wikimedia Commons -------------------------------------------------------
def test_commons_lists_media_matches(tmp_path):
    cass = Cassette(tmp_path / "commons.json")
    params = {"action": "query", "list": "search", "srsearch": "Bullington transmitting station",
              "srnamespace": 6, "srlimit": 5, "format": "json"}
    body = {"query": {"search": [
        {"pageid": 1, "title": "File:Bullington mast.jpg", "snippet": "the mast"},
        {"pageid": 2, "title": "File:Bullington ridge.jpg", "snippet": "ridge view"}]}}
    cass.put(request_key("GET", WikimediaCommonsAdapter.API, params),
             {"url": WikimediaCommonsAdapter.API, "text": json.dumps(body)})
    adapter = WikimediaCommonsAdapter(_client(cass))
    assert isinstance(adapter, Adapter) and "archive.media" in adapter.capabilities
    ev = adapter.acquire("archive.media",
                         {"query": "Bullington transmitting station"}, _prov())[0]
    EvidenceObject.model_validate(ev.model_dump())
    assert ev.kind == "media_archive"
    assert ev.structured["independence_group"] == "wikimedia"
    assert ev.structured["count"] == 2
    assert ev.structured["files"][0]["page"].startswith(
        "https://commons.wikimedia.org/wiki/File:Bullington_mast.jpg")
    assert "Bullington mast.jpg" in ev.summary


def test_commons_no_match_reads_clean(tmp_path):
    cass = Cassette(tmp_path / "commons.json")
    params = {"action": "query", "list": "search", "srsearch": "zzz nothing",
              "srnamespace": 6, "srlimit": 5, "format": "json"}
    cass.put(request_key("GET", WikimediaCommonsAdapter.API, params),
             {"url": WikimediaCommonsAdapter.API,
              "text": json.dumps({"query": {"search": []}})})
    ev = WikimediaCommonsAdapter(_client(cass)).acquire(
        "archive.media", {"query": "zzz nothing"}, _prov())[0]
    assert ev.structured["count"] == 0 and "0 Commons media match" in ev.summary


# -- registry selection by capability ----------------------------------------
def test_registry_selects_new_adapters_by_capability(tmp_path):
    reg = AdapterRegistry()
    reg.register(DnsAdapter(_client(Cassette(tmp_path / "a.json"))))
    reg.register(AsnAdapter(_client(Cassette(tmp_path / "b.json"))))
    reg.register(WikimediaCommonsAdapter(_client(Cassette(tmp_path / "c.json"))))
    assert reg.by_capability("infra.dns")[0].id == "infra.dns"
    assert reg.by_capability("infra.asn")[0].id == "infra.ripestat"
    assert reg.by_capability("archive.media")[0].id == "archive.commons"


def test_catalog_marks_new_tools_live():
    from osintinel.adapters.catalog import BASIC
    live = {t.capability for c in BASIC for t in c.tools if t.status == "live"}
    assert {"infra.dns", "infra.asn", "archive.media"} <= live


def test_reference_registry_lists_new_adapters():
    # `osintinel adapters` builds this registry — the new live adapters must be discoverable there.
    import tempfile

    from osintinel.adapters import ContentAddressedStore
    from osintinel.scenarios.archive_slice import build_registry

    reg = build_registry(ContentAddressedStore(tempfile.mkdtemp()))
    assert reg.by_capability("infra.dns")[0].id == "infra.dns"
    assert reg.by_capability("infra.asn")[0].id == "infra.ripestat"
    assert reg.by_capability("archive.media")[0].id == "archive.commons"
