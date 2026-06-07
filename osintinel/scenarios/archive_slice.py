"""Phase 3 vertical slice (doc 06): real adapters, replayable from cassettes.

> "Tool Selection picks an archive adapter by capability, Acquisition fetches a real snapshot,
> evidence updates a hypothesis — all replayable from cassettes."

A compact investigation: does ``windreach.example`` operate a *communications mast* at
Bullington, or is the structure a *wind turbine*? Two real adapters are chosen **by capability**
(no hardcoded path) and their cassette-backed responses become evidence:

* **Wayback** (``archive.snapshot``) — fetches a real page snapshot; the HTML bytes go to the
  content-addressed store, and only a lean ``raw_response`` ref enters the ledger.
* **Overpass** (``geo.features``) — an independent OSM corroboration source.

Linking evidence to a hypothesis here is a small deterministic relevance rule standing in for
the Connections/LLM judgment (Phase 1 keeps the loop model-free). Synthesis + Confidence then
move the hypothesis, and — with two independent source groups — promote it to INSIGHT.

Everything runs offline from committed cassettes; ``record=True`` (``OSINTINEL_RECORD=1``) would
refresh them against live endpoints.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..adapters import (
    Cassette,
    CertTransparencyAdapter,
    ContentAddressedStore,
    HttpClient,
    NominatimAdapter,
    OverpassAdapter,
    WaybackAdapter,
    WikidataAdapter,
)
from ..adapters.registry import AdapterRegistry
from ..agents.base import AgentContext
from ..agents.confidence import ConfidenceAgent
from ..agents.relevance import Candidate, apply_weights
from ..agents.selection import ToolSelectionAgent
from ..agents.synthesis import SynthesisAgent
from ..core.budget import BudgetGovernor
from ..core.schemas import (
    AcquisitionMethod,
    AgentName,
    Budgets,
    EvidenceRequest,
    Explanation,
    Hypothesis,
    HypothesisSet,
    Investigation,
    InvestigationConfig,
)
from ..core.state import InvestigationState
from ..ledger import Ledger

QUESTION = "Does windreach.example operate a communications mast at Bullington?"
CASSETTE_DIR = Path(__file__).resolve().parent.parent / "adapters" / "_cassettes"

# Per-request acquisition arguments (the concrete query the chosen adapter runs).
_REQUEST_ARGS = {
    "archive": {"url": "windreach.example", "limit": 10},
    "geo": {"lat": 51.0153, "lon": -1.3253, "radius": 500, "key": "man_made"},
}


@dataclass
class SliceResult:
    state: InvestigationState
    ledger: Ledger
    cas: ContentAddressedStore
    registry: AdapterRegistry
    set_id: str
    mast_hypothesis_id: str
    turbine_hypothesis_id: str
    selected_adapters: list[str]


def build_registry(cas: ContentAddressedStore, *, record: bool = False) -> AdapterRegistry:
    """Register the lawful reference adapters, each wired to its committed cassette."""
    def client(name: str) -> HttpClient:
        return HttpClient(Cassette(CASSETTE_DIR / f"{name}.json"), record=record)

    reg = AdapterRegistry()
    reg.register(WaybackAdapter(client("wayback"), cas), effectiveness=0.82)
    reg.register(OverpassAdapter(client("overpass")), effectiveness=0.75)
    reg.register(NominatimAdapter(client("nominatim")), effectiveness=0.6)
    reg.register(WikidataAdapter(client("wikidata")), effectiveness=0.7)
    reg.register(CertTransparencyAdapter(client("crtsh")), effectiveness=0.6)
    return reg


def _relevance_link(ev, mast_id: str, turbine_id: str) -> None:
    """Deterministic stand-in for the Connections/LLM relevance judgment.

    A telecom-titled archive page or an OSM mast/tower feature supports the mast hypothesis and
    weighs against the turbine hypothesis; anything else stays unlinked."""
    title = (ev.structured.get("title") or "").lower()
    man_made = ev.structured.get("tags", {}).get("man_made")
    if ev.kind == "archive_snapshot" and ("telecom" in title or "mast" in title):
        ev.supports, ev.contradicts = [mast_id], [turbine_id]
        ev.weights = {mast_id: 0.8, turbine_id: -0.3}
    elif ev.kind == "osm_feature" and man_made in {"mast", "tower"}:
        ev.supports, ev.contradicts = [mast_id], [turbine_id]
        ev.weights = {mast_id: 0.6, turbine_id: -0.2}


def run_archive_slice(*, cas_dir: str | Path | None = None, record: bool = False,
                      judge=None) -> SliceResult:
    """Run the slice. ``judge`` (a ``RelevanceJudge``) replaces the deterministic relevance
    stand-in with model-driven judgment (Phase M); ``None`` keeps the heuristic (CI default)."""
    cas = ContentAddressedStore(cas_dir or tempfile.mkdtemp())
    ledger = Ledger()
    state = InvestigationState("slice-inv", ledger)
    registry = build_registry(cas, record=record)

    investigation = Investigation(
        title="Bullington structure", objective="Identify the operator/nature of the structure.",
        domain="geolocation", inputs=[],
        config=InvestigationConfig(
            confidence_threshold=0.7,
            budgets=Budgets(tokens=100_000, money_usd=5.0, seconds=300.0, requests=100)),
    )
    governor = BudgetGovernor(investigation.config.budgets)
    ctx = AgentContext(investigation, state, iteration=1, governor=governor, registry=registry)

    def prov(agent: AgentName, method: AcquisitionMethod, **kw):
        return ctx.provenance(agent, method=method, **kw)

    # --- hypothesis set (two competing explanations -> hypotheses) -----------
    hs = HypothesisSet(question=QUESTION,
                       provenance=prov(AgentName.CONNECTIONS, AcquisitionMethod.DERIVED))
    state.add_set(hs, 0)
    ex_mast = Explanation(set_id=hs.set_id,
                          statement="The structure is a communications mast operated by WindReach Telecom.",
                          provenance=prov(AgentName.CONNECTIONS, AcquisitionMethod.DERIVED))
    ex_turbine = Explanation(set_id=hs.set_id,
                             statement="The structure is a wind turbine.",
                             provenance=prov(AgentName.CONNECTIONS, AcquisitionMethod.DERIVED))
    state.add_explanation(ex_mast, 0)
    state.add_explanation(ex_turbine, 0)
    h_mast = Hypothesis(set_id=hs.set_id, statement=ex_mast.statement,
                        derived_from_explanations=[ex_mast.explanation_id],
                        provenance=prov(AgentName.CONNECTIONS, AcquisitionMethod.DERIVED))
    h_turbine = Hypothesis(set_id=hs.set_id, statement=ex_turbine.statement,
                           derived_from_explanations=[ex_turbine.explanation_id],
                           provenance=prov(AgentName.CONNECTIONS, AcquisitionMethod.DERIVED))
    state.add_hypothesis(h_mast, 0)
    state.add_hypothesis(h_turbine, 0)

    # --- evidence requests, each tagged with the role its args belong to -----
    er_archive = EvidenceRequest(
        question_ref=hs.set_id, description="Archived web presence of windreach.example",
        candidate_capabilities=["archive.snapshot", "archive.timemap"],
        provenance=prov(AgentName.EVIDENCE_PLANNING, AcquisitionMethod.DERIVED))
    er_geo = EvidenceRequest(
        question_ref=hs.set_id, description="Mapped structures near the coordinate",
        candidate_capabilities=["geo.features"],
        provenance=prov(AgentName.EVIDENCE_PLANNING, AcquisitionMethod.DERIVED))
    role_by_req = {er_archive.evidence_request_id: "archive", er_geo.evidence_request_id: "geo"}

    # --- Tool Selection by capability (no hardcoded adapter) -----------------
    plans = ToolSelectionAgent().run(ctx, [er_archive, er_geo])

    # --- Acquisition: run each plan's adapter, record a lean raw_response -----
    for plan in plans:
        adapter = registry.get(plan.selected_adapter)
        capability = plan.arguments["capability"]
        args = _REQUEST_ARGS[role_by_req[plan.evidence_request_id]]
        aprov = prov(AgentName.ACQUISITION, AcquisitionMethod.API, confidence=0.8,
                     derived_from=[plan.evidence_request_id])
        evidence = adapter.acquire(capability, args, aprov)

        art = adapter.last_artifact
        if art is not None:
            cost = adapter.cost_of("collect")
            governor.charge(tokens=cost.tokens, money_usd=cost.money_usd, requests=cost.requests)
            state.record_raw_response(
                ctx.iteration, adapter_id=adapter.id, capability=capability,
                content_hash=art.digest(), source=art.source, url=art.url,
                bytes_len=art.structured.get("bytes"))
        for ev in evidence:
            if judge is None:
                _relevance_link(ev, h_mast.hypothesis_id, h_turbine.hypothesis_id)
            else:
                # Phase M: a model (task tier) judges relevance instead of the heuristic stand-in.
                apply_weights(ev, judge.score(
                    kind=ev.kind, summary=ev.summary, structured=ev.structured,
                    candidates=[Candidate(h_mast.hypothesis_id, h_mast.statement),
                                Candidate(h_turbine.hypothesis_id, h_turbine.statement)]))
            ev.addresses_query = plan.evidence_request_id
            state.add_evidence(ev, ctx.iteration)

    # --- Synthesis (relink) + Confidence (move + gate) -----------------------
    SynthesisAgent().run(ctx)
    ConfidenceAgent().run(ctx)

    return SliceResult(
        state=state, ledger=ledger, cas=cas, registry=registry, set_id=hs.set_id,
        mast_hypothesis_id=h_mast.hypothesis_id, turbine_hypothesis_id=h_turbine.hypothesis_id,
        selected_adapters=[p.selected_adapter for p in plans],
    )
