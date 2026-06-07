"""Phase M reason-tier demo: the flagship model does open-ended reasoning (doc 11 §2).

Two things the deterministic spine can't: the **Connections** agent asks the reason tier for
*additional* competing explanations beyond those handed in (open-ended hypothesis generation),
and the **Skeptic** asks it for adversarial critique (hidden assumptions / reasoning weaknesses)
that the structural challenges don't cover. Driven here by a ``ScriptedProvider`` so it runs
offline through the real gateway (cost + ``model_call`` ledger events); point the reason tier at
Ollama or a free-cloud model and the same path produces genuine reasoning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..adapters import AdapterRegistry
from ..agents.base import AgentContext
from ..agents.connections import ConnectionsAgent
from ..agents.skeptic import SkepticAgent
from ..agents.synthesis import SynthesisAgent
from ..core.budget import BudgetGovernor
from ..core.schemas import (
    AcquisitionMethod,
    AgentName,
    Budgets,
    EvidenceObject,
    Investigation,
    InvestigationConfig,
)
from ..core.state import InvestigationState
from ..inference.gateway import TieredGateway
from ..inference.providers import DeterministicEmbedder, ScriptedProvider
from ..ledger import Ledger

QUESTION = "What is the circular structure on the ridge?"
GIVEN_CANDIDATES = ["communications mast", "summit cairn"]

# What a reasoning model would return (canned for an offline, deterministic demo).
_PROPOSED = json.dumps(["a water reservoir / tank", "a wind-measurement (met) mast"])
_CRITIQUE = json.dumps([
    {"category": "hidden_assumption", "severity": "high",
     "description": "Assumes the lattice silhouette implies telecom; met masts look identical."},
    {"category": "reasoning_weakness", "severity": "medium",
     "description": "No RF/antenna evidence yet — structure type is inferred from shape alone."},
])


@dataclass
class ReasonDemoResult:
    given: int
    after_connections: int
    proposed: list[str]
    model_findings: list[tuple[str, str, str]]  # (category, severity, description)
    model_calls: int


def _reason_gateway(ledger: Ledger) -> TieredGateway:
    provider = ScriptedProvider({"connections": _PROPOSED, "skeptic": _CRITIQUE})
    tiers = {t: provider for t in ("reason", "large", "small", "task", "nano")}
    return TieredGateway(tiers, embedder=DeterministicEmbedder(), ledger=ledger,
                         investigation_id="reason-demo")


def run_reason_demo() -> ReasonDemoResult:
    ledger = Ledger()
    state = InvestigationState("reason-demo", ledger)
    gateway = _reason_gateway(ledger)
    investigation = Investigation(
        title="Ridge structure", objective="Identify the circular ridge structure.",
        domain="demo",
        inputs=[{"kind": "observation", "type": "image_note", "content": "lattice tower on a bare ridge"},
                {"kind": "question", "question": QUESTION, "candidates": list(GIVEN_CANDIDATES)}],
        config=InvestigationConfig(budgets=Budgets()))
    governor = BudgetGovernor(investigation.config.budgets)
    ctx = AgentContext(investigation, state, iteration=0, governor=governor,
                       registry=AdapterRegistry(), llm=gateway)

    # OBSERVE → CONNECT (reason tier expands the explanation space)
    from ..agents.aggregation import AggregationAgent
    AggregationAgent().run(ctx)
    ConnectionsAgent().run(ctx)
    set_id = next(iter(state.hypothesis_sets))
    after = len(state.hypothesis_sets[set_id].explanations)

    # synthesize hypotheses, attach a little evidence, then adversarial critique
    SynthesisAgent().synthesize_hypotheses(ctx)
    leader = state.active_hypotheses(set_id)[0]
    prov = ctx.provenance(AgentName.ACQUISITION, method=AcquisitionMethod.API, confidence=0.8,
                          source="OpenStreetMap")
    ev = EvidenceObject(kind="osm_feature", summary="OSM node tagged man_made=mast.",
                        structured={"independence_group": "osm"}, supports=[leader.hypothesis_id],
                        weights={leader.hypothesis_id: 0.6}, provenance=prov)
    state.add_evidence(ev, 0)
    SynthesisAgent().run(ctx)
    SkepticAgent().run(ctx)

    model_findings = [(f.category, f.severity, f.description) for f in state.findings.values()
                      if f.category in {"hidden_assumption", "reasoning_weakness", "overfit",
                                        "contradiction"}]
    return ReasonDemoResult(
        given=len(GIVEN_CANDIDATES),
        after_connections=after,
        proposed=json.loads(_PROPOSED),
        model_findings=model_findings,
        model_calls=sum(1 for e in ledger.events() if e.type == "model_call"))
