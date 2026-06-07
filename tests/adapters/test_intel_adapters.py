"""Free infra/threat-intel adapters: Shodan InternetDB, URLScan.io, AlienVault OTX."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from osintinel.adapters import (
    Adapter,
    Cassette,
    HttpClient,
    OTXAdapter,
    ShodanInternetDBAdapter,
    UrlscanAdapter,
)
from osintinel.adapters.registry import AdapterRegistry
from osintinel.adapters.transport import request_key
from osintinel.core.schemas import AcquisitionMethod, AgentName, EvidenceObject, Provenance

CASSETTES = Path("osintinel/adapters/_cassettes")


def _prov():
    return Provenance(source="x", acquisition_method=AcquisitionMethod.API,
                      agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                      investigation_id="t")


def _client():
    return HttpClient(Cassette(CASSETTES / "intel.json"), record=False)


# (adapter, capability, args, expected kind, expected group)
CASES = [
    (ShodanInternetDBAdapter, "infra.exposure", {"ip": "203.0.113.10"}, "host_exposure", "shodan"),
    (UrlscanAdapter, "infra.urlscan", {"domain": "windreach-telecom.example"},
     "urlscan_result", "urlscan"),
    (OTXAdapter, "threat.intel", {"indicator": "windreach-telecom.example"},
     "threat_intel", "otx"),
]
IDS = [c[0].__name__ for c in CASES]


@pytest.mark.parametrize("cls,cap,args,kind,group", CASES, ids=IDS)
def test_conforms_and_emits_schema_valid_evidence(cls, cap, args, kind, group):
    adapter = cls(_client())
    assert isinstance(adapter, Adapter)
    assert cap in adapter.capabilities
    evidence = adapter.acquire(cap, args, _prov())
    assert evidence
    ev = evidence[0]
    EvidenceObject.model_validate(ev.model_dump())  # schema-valid round-trip
    assert ev.kind == kind
    assert ev.structured["independence_group"] == group
    assert ev.provenance.tool_used == adapter.id and ev.provenance.license_note


def test_shodan_surfaces_ports_and_cves():
    ev = ShodanInternetDBAdapter(_client()).acquire(
        "infra.exposure", {"ip": "203.0.113.10"}, _prov())[0]
    assert ev.structured["ports"] == [22, 80, 443]
    assert "CVE-2023-44487" in ev.structured["vulns"]


def test_otx_reports_pulse_count():
    ev = OTXAdapter(_client()).acquire(
        "threat.intel", {"indicator": "windreach-telecom.example"}, _prov())[0]
    assert ev.structured["pulse_count"] == 1 and ev.structured["pulse_names"]


def test_otx_zero_pulses_reads_clean(tmp_path):
    # a domain with no threat reports → "no threat reports"
    otx = OTXAdapter.__new__(OTXAdapter)
    url = f"{otx.API}/domain/clean.example/general"
    cass = Cassette(tmp_path / "c.json")
    cass.put(request_key("GET", url, None, None),
             {"url": url, "text": json.dumps({"pulse_info": {"count": 0, "pulses": []}})})
    ev = OTXAdapter(HttpClient(cass, record=False)).acquire(
        "threat.intel", {"indicator": "clean.example"}, _prov())[0]
    assert "no threat reports" in ev.summary and ev.structured["pulse_count"] == 0


def test_registry_selects_intel_adapters_by_capability():
    reg = AdapterRegistry()
    reg.register(ShodanInternetDBAdapter(_client()))
    reg.register(UrlscanAdapter(_client()))
    reg.register(OTXAdapter(_client()))
    assert reg.by_capability("infra.exposure")[0].id == "infra.internetdb"
    assert reg.by_capability("threat.intel")[0].id == "threat.otx"


def test_api_keys_never_enter_cassettes(tmp_path, monkeypatch):
    monkeypatch.setenv("OTX_API_KEY", "secret-otx-key")
    otx = OTXAdapter.__new__(OTXAdapter)
    url = f"{otx.API}/domain/x.example/general"
    cass_path = tmp_path / "c.json"
    cass = Cassette(cass_path)
    cass.put(request_key("GET", url, None, None),
             {"url": url, "text": json.dumps({"pulse_info": {"count": 0, "pulses": []}})})
    OTXAdapter(HttpClient(cass, record=False)).acquire(
        "threat.intel", {"indicator": "x.example"}, _prov())
    assert "secret-otx-key" not in cass_path.read_text()
