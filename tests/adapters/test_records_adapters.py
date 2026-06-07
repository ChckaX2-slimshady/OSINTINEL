"""Free public-records adapters: OpenCorporates, SEC EDGAR, GLEIF (record.public)."""

from __future__ import annotations

from pathlib import Path

import pytest

from osintinel.adapters import (
    Adapter,
    Cassette,
    GLEIFAdapter,
    HttpClient,
    OpenCorporatesAdapter,
    SECEdgarAdapter,
)
from osintinel.adapters.registry import AdapterRegistry
from osintinel.core.schemas import AcquisitionMethod, AgentName, EvidenceObject, Provenance

CASSETTES = Path("osintinel/adapters/_cassettes")
COMPANY = "WindReach Telecom"


def _prov():
    return Provenance(source="x", acquisition_method=AcquisitionMethod.API,
                      agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                      investigation_id="t")


def _client():
    return HttpClient(Cassette(CASSETTES / "records.json"), record=False)


CASES = [
    (OpenCorporatesAdapter, "opencorporates"),
    (SECEdgarAdapter, "sec_edgar"),
    (GLEIFAdapter, "gleif"),
]
IDS = [c[0].__name__ for c in CASES]


@pytest.mark.parametrize("cls,group", CASES, ids=IDS)
def test_conforms_and_emits_public_record_evidence(cls, group):
    adapter = cls(_client())
    assert isinstance(adapter, Adapter)
    assert "record.public" in adapter.capabilities
    ev = adapter.acquire("record.public", {"query": COMPANY}, _prov())[0]
    EvidenceObject.model_validate(ev.model_dump())            # schema-valid
    assert ev.kind == "public_record"
    assert ev.structured["independence_group"] == group
    assert ev.provenance.tool_used == adapter.id and ev.provenance.license_note
    assert COMPANY in ev.summary


def test_opencorporates_returns_matches():
    ev = OpenCorporatesAdapter(_client()).acquire("record.public", {"query": COMPANY}, _prov())[0]
    assert len(ev.structured["matches"]) == 2
    assert ev.structured["matches"][0]["jurisdiction"] == "gb"


def test_gleif_returns_lei():
    ev = GLEIFAdapter(_client()).acquire("record.public", {"query": COMPANY}, _prov())[0]
    assert ev.structured["matches"][0]["lei"] == "549300EXAMPLE0000001"


def test_three_records_adapters_share_capability_distinct_groups():
    reg = AdapterRegistry()
    for cls in (OpenCorporatesAdapter, SECEdgarAdapter, GLEIFAdapter):
        reg.register(cls(_client()))
    selected = reg.by_capability("record.public")
    assert {a.id for a in selected} == {"record.opencorporates", "record.sec_edgar",
                                        "record.gleif"}
