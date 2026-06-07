"""Contract + parse/normalize tests for the Phase 3 reference adapters (doc 05 §6).

Each adapter is exercised against its committed cassette (offline) and must emit schema-valid
``EvidenceObject``s carrying full provenance — ``source``, ``tool_used``, ``content_hash``,
``license_note`` (doc 05 §5.1). The heavy adapter (Wayback) must route bytes through the CAS and
carry a ``cas:`` ``payload_ref``; light adapters carry their data inline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from osintinel.adapters import (
    Adapter,
    Cassette,
    CertTransparencyAdapter,
    ContentAddressedStore,
    HttpClient,
    NominatimAdapter,
    OverpassAdapter,
    WaybackAdapter,
    WikidataAdapter,
)
from osintinel.adapters.storage import CAS_SCHEME
from osintinel.core.schemas import AcquisitionMethod, AgentName, EvidenceObject, Provenance

CASSETTES = Path("osintinel/adapters/_cassettes")


def _prov() -> Provenance:
    return Provenance(source="x", acquisition_method=AcquisitionMethod.API,
                      agent_responsible=AgentName.ACQUISITION, confidence=0.8,
                      investigation_id="inv")


def _client(name: str) -> HttpClient:
    return HttpClient(Cassette(CASSETTES / f"{name}.json"), record=False)


def _build(adapter_cls, cassette, cas=None):
    return adapter_cls(_client(cassette), cas) if cas is not None else adapter_cls(_client(cassette))


# (adapter class, cassette name, capability, acquire args, needs_cas)
CASES = [
    (NominatimAdapter, "nominatim", "geo.geocode", {"q": "Bullington telecom mast", "limit": 5}, False),
    (OverpassAdapter, "overpass", "geo.features",
     {"lat": 51.0153, "lon": -1.3253, "radius": 500, "key": "man_made"}, False),
    (WaybackAdapter, "wayback", "archive.timemap", {"url": "windreach.example", "limit": 10}, True),
    (WikidataAdapter, "wikidata", "reference.encyclopedic", {"qid": "Q12345"}, False),
    (CertTransparencyAdapter, "crtsh", "infra.certs", {"domain": "windreach.example"}, False),
]
IDS = [c[0].__name__ for c in CASES]


@pytest.mark.parametrize("adapter_cls,cassette,capability,args,needs_cas", CASES, ids=IDS)
def test_adapter_conforms_to_protocol(adapter_cls, cassette, capability, args, needs_cas, tmp_path):
    cas = ContentAddressedStore(tmp_path) if needs_cas else None
    adapter = _build(adapter_cls, cassette, cas)
    assert isinstance(adapter, Adapter)  # runtime_checkable Protocol
    assert capability in adapter.capabilities


@pytest.mark.parametrize("adapter_cls,cassette,capability,args,needs_cas", CASES, ids=IDS)
def test_adapter_emits_schema_valid_evidence_with_provenance(
        adapter_cls, cassette, capability, args, needs_cas, tmp_path):
    cas = ContentAddressedStore(tmp_path) if needs_cas else None
    adapter = _build(adapter_cls, cassette, cas)

    evidence = adapter.acquire(capability, args, _prov())
    assert evidence, f"{adapter_cls.__name__} produced no evidence"
    for ev in evidence:
        assert isinstance(ev, EvidenceObject)
        EvidenceObject.model_validate(ev.model_dump())  # round-trips / schema-valid
        p = ev.provenance
        assert p.source and p.source != "x"          # adapter stamped a real source
        assert p.tool_used == adapter.id
        assert p.content_hash is not None             # integrity reference present
        assert p.license_note                         # licensing recorded (doc 05 §5.1)
        assert ev.structured.get("independence_group")


def test_wayback_routes_heavy_bytes_through_cas(tmp_path):
    cas = ContentAddressedStore(tmp_path)
    adapter = WaybackAdapter(_client("wayback"), cas)
    ev = adapter.acquire("archive.snapshot", {"url": "windreach.example", "limit": 10}, _prov())[0]

    assert ev.payload_ref and ev.payload_ref.startswith(CAS_SCHEME)
    assert cas.has(ev.provenance.content_hash)
    html = cas.get(ev.provenance.content_hash).decode("utf-8")
    assert "<title>" in html  # the real fetched page bytes are recoverable by hash


def test_light_adapter_carries_data_inline_not_in_cas(tmp_path):
    # Nominatim has no CAS; its evidence is fully inline with a structured-payload digest.
    adapter = NominatimAdapter(_client("nominatim"))
    ev = adapter.acquire("geo.geocode", {"q": "Bullington telecom mast", "limit": 5}, _prov())[0]
    assert ev.payload_ref is None
    assert ev.structured["lat"] == pytest.approx(51.0153, abs=1e-3)


def test_pure_parse_normalize_are_deterministic(tmp_path):
    # parse/normalize must be pure: same artifact -> identical normalized output.
    cas = ContentAddressedStore(tmp_path)
    a1 = WaybackAdapter(_client("wayback"), cas)
    a2 = WaybackAdapter(_client("wayback"), cas)
    e1 = a1.acquire("archive.timemap", {"url": "windreach.example", "limit": 10}, _prov())[0]
    e2 = a2.acquire("archive.timemap", {"url": "windreach.example", "limit": 10}, _prov())[0]
    assert e1.summary == e2.summary
    assert e1.provenance.content_hash == e2.provenance.content_hash
