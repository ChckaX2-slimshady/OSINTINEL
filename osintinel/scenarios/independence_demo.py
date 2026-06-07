"""Phase M embed-tier demo: catch *illusory* source independence (doc 11 §6).

Three sources appear to corroborate a hypothesis — but two of them carry near-duplicate
(syndicated) content. The embed tier collapses them, so the genuine independent-source count
drops, and the Skeptic raises a BLOCKING ``illusory_independence`` finding that holds promotion
until a *genuinely* distinct source arrives. Runs on the deterministic embedder (identical text →
cosine 1.0), so it needs no model or network; with a real embedder it generalizes to paraphrase.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..adapters import AdapterRegistry
from ..agents.base import AgentContext
from ..agents.semantic import analyze_independence
from ..agents.skeptic import SkepticAgent
from ..agents.synthesis import SynthesisAgent
from ..core.budget import BudgetGovernor
from ..core.schemas import (
    AcquisitionMethod,
    AgentName,
    Budgets,
    EvidenceObject,
    Explanation,
    Hypothesis,
    HypothesisSet,
    Investigation,
    InvestigationConfig,
)
from ..core.state import InvestigationState
from ..inference import build_gateway
from ..ledger import Ledger

LEADER = "The ridge structure is a communications mast."
ALT = "The ridge structure is a wind turbine."

# Two syndicated copies (identical text) + one genuinely distinct source.
_SYNDICATED = "Telecom mast confirmed on the ridge near Bullington, Hampshire."
_DISTINCT = "Wikidata entity: a radio relay station recorded at this ridgeline coordinate."


@dataclass
class IndependenceDemoResult:
    declared_before: int
    effective_before: int
    finding_raised: bool
    declared_after: int
    effective_after: int
    finding_resolved: bool
    merged_clusters: list


def _evidence(ctx, source, group, summary, leader_id) -> EvidenceObject:
    prov = ctx.provenance(AgentName.ACQUISITION, method=AcquisitionMethod.API, confidence=0.8,
                          source=source)
    return EvidenceObject(kind="reference", summary=summary,
                          structured={"independence_group": group}, supports=[leader_id],
                          weights={leader_id: 0.7}, provenance=prov)


def run_independence_demo() -> IndependenceDemoResult:
    ledger = Ledger()
    state = InvestigationState("independence-demo", ledger)
    gateway = build_gateway()  # deterministic embedder (no network); embeds via gateway.embed
    investigation = Investigation(
        title="Illusory independence", objective="Detect syndicated corroboration.",
        domain="demo", inputs=[],
        config=InvestigationConfig(confidence_threshold=0.7, budgets=Budgets()))
    governor = BudgetGovernor(investigation.config.budgets)
    ctx = AgentContext(investigation, state, iteration=0, governor=governor,
                       registry=AdapterRegistry(), llm=gateway)

    def prov(agent):
        return ctx.provenance(agent, method=AcquisitionMethod.DERIVED, confidence=0.5)

    hs = HypothesisSet(question="What is the ridge structure?", provenance=prov(AgentName.CONNECTIONS))
    state.add_set(hs, 0)
    leader = None
    for statement in (LEADER, ALT):
        ex = Explanation(set_id=hs.set_id, statement=statement, provenance=prov(AgentName.CONNECTIONS))
        state.add_explanation(ex, 0)
        h = Hypothesis(set_id=hs.set_id, statement=statement,
                       derived_from_explanations=[ex.explanation_id], provenance=prov(AgentName.CONNECTIONS))
        state.add_hypothesis(h, 0)
        if statement == LEADER:
            leader = h
    lid = leader.hypothesis_id

    # --- two syndicated sources (look independent: osm + newswire) -----------
    state.add_evidence(_evidence(ctx, "OpenStreetMap", "osm", _SYNDICATED, lid), 0)
    state.add_evidence(_evidence(ctx, "Regional Newswire", "newswire", _SYNDICATED, lid), 0)
    SynthesisAgent().run(ctx)
    state.update_confidence(lid, 0.8, "strong apparent corroboration", AgentName.CONFIDENCE, 0)

    declared_before = len(state.independent_source_groups(lid))
    rep_before = analyze_independence(
        ["osm", "newswire"], [_SYNDICATED, _SYNDICATED], gateway.embed)
    SkepticAgent().run(ctx)
    finding_raised = bool(state.unresolved_blocking_findings(lid))

    # --- a genuinely distinct source arrives (wikidata) ----------------------
    ctx.iteration = 1
    state.add_evidence(_evidence(ctx, "Wikidata", "wikidata", _DISTINCT, lid), 1)
    SynthesisAgent().run(ctx)
    declared_after = len(state.independent_source_groups(lid))
    rep_after = analyze_independence(
        ["osm", "newswire", "wikidata"], [_SYNDICATED, _SYNDICATED, _DISTINCT], gateway.embed)
    SkepticAgent().run(ctx)
    finding_resolved = not state.unresolved_blocking_findings(lid)

    return IndependenceDemoResult(
        declared_before=declared_before, effective_before=len(rep_before.effective),
        finding_raised=finding_raised, declared_after=declared_after,
        effective_after=len(rep_after.effective), finding_resolved=finding_resolved,
        merged_clusters=rep_before.merged)
