"""Phase 3 vertical slice + exit criteria (doc 06).

Asserts the slice's headline guarantees: Tool Selection chooses adapters **by capability** (no
hardcoded path, with fallbacks), real cassette-backed evidence **updates a hypothesis**, the run
is **replayable offline**, and — the integral storage decision — heavy bytes live in the CAS
while the ledger stays lean.
"""

from __future__ import annotations

from osintinel.adapters import ContentAddressedStore
from osintinel.adapters.registry import AdapterRegistry
from osintinel.core.schemas import EpistemicClass
from osintinel.graph import build_graph, chain_terminates_in_information
from osintinel.ledger import replay_state
from osintinel.scenarios.archive_slice import build_registry


def test_tool_selection_chose_adapters_by_capability(slice_result):
    # archive request -> Wayback; geo request -> Overpass — selected by tag, not name.
    assert slice_result.selected_adapters == ["archive.wayback", "osm.overpass"]


def test_evidence_updated_the_hypothesis_to_insight(slice_result):
    mast = slice_result.state.hypotheses[slice_result.mast_hypothesis_id]
    turbine = slice_result.state.hypotheses[slice_result.turbine_hypothesis_id]
    assert mast.supporting_evidence            # real evidence attached
    assert mast.confidence > turbine.confidence
    # two independent source groups (Internet Archive + OpenStreetMap) clear the Skeptic gate
    assert slice_result.state.independent_source_groups(slice_result.mast_hypothesis_id) == {
        "InternetArchive", "OpenStreetMap"}
    assert mast.epistemic_class is EpistemicClass.INSIGHT


def test_heavy_bytes_in_cas_ledger_stays_lean(slice_result):
    raws = [e for e in slice_result.ledger.events() if e.type == "raw_response"]
    assert raws, "expected raw_response provenance events"
    for e in raws:
        # the lean event carries references only — never the fetched bytes
        assert set(e.payload) == {"adapter", "capability", "content_hash", "source", "url", "bytes"}
    # the Wayback HTML is recoverable from the CAS by its recorded hash
    wb = next(e for e in raws if e.payload["adapter"] == "archive.wayback")
    assert slice_result.cas.has(wb.payload["content_hash"])
    # no single ledger event is anywhere near a raw page in size
    assert max(len(e.model_dump_json()) for e in slice_result.ledger.events()) < 4000


def test_slice_replays_byte_identically_offline(slice_result):
    replayed = replay_state(slice_result.ledger)
    assert replayed.snapshot() == slice_result.state.snapshot()


def test_audit_chain_terminates_in_information(slice_result):
    store = build_graph(slice_result.state)
    assert chain_terminates_in_information(store, slice_result.mast_hypothesis_id)


def test_selection_falls_back_when_preferred_capability_absent(tmp_path):
    # With no geo.features adapter registered, an alternative capability must still resolve.
    cas = ContentAddressedStore(tmp_path)
    full = build_registry(cas)
    from osintinel.agents.base import AgentContext
    from osintinel.agents.selection import ToolSelectionAgent
    from osintinel.core.budget import BudgetGovernor
    from osintinel.core.schemas import (
        AcquisitionMethod, AgentName, Budgets, EvidenceRequest, HypothesisSet, Investigation,
        InvestigationConfig, Provenance,
    )
    from osintinel.core.state import InvestigationState
    from osintinel.ledger import Ledger

    # registry missing the first-choice capability but offering a fallback
    reg = AdapterRegistry()
    reg.register(full.get("wikidata.entity"), effectiveness=0.7)  # reference.encyclopedic only

    inv = Investigation(title="t", objective="o", domain="d", inputs=[],
                        config=InvestigationConfig(budgets=Budgets(
                            tokens=1000, money_usd=1.0, seconds=10.0, requests=10)))
    state = InvestigationState("fb", Ledger())
    prov = Provenance(source="i", acquisition_method=AcquisitionMethod.DERIVED,
                      agent_responsible=AgentName.CONNECTIONS, confidence=0.7, investigation_id="fb")
    hs = HypothesisSet(question="q?", provenance=prov)
    state.add_set(hs, 0)
    ctx = AgentContext(inv, state, 1, BudgetGovernor(inv.config.budgets), reg)

    req = EvidenceRequest(question_ref=hs.set_id, description="d",
                          candidate_capabilities=["geo.features", "reference.encyclopedic"],
                          provenance=prov)
    plans = ToolSelectionAgent().run(ctx, [req])
    assert len(plans) == 1
    assert plans[0].selected_adapter == "wikidata.entity"  # fell back to the available capability
    assert plans[0].arguments["capability"] == "reference.encyclopedic"
