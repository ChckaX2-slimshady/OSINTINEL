"""Rebuild the knowledge graph from the append-only ledger (doc 04 §8, doc 06 Phase 2).

The graph is a *materialized view* over the ledger: replaying the event stream in order
reconstructs an ``InvestigationState`` byte-for-byte. This is the corruption-recovery and
"kill the process, reload from the ledger" guarantee — and the basis for dashboard replay
(doc 06 Phase 7).

Replay applies each event's recorded effect WITHOUT re-recording it (the `_index_*`/`_apply_*`
helpers on ``InvestigationState``), so a replayed state carries an identical ledger reference
and identical objects. ``EvidenceObject.supports/contradicts`` fully determine each
hypothesis' evidence links, so a final ``relink_evidence`` pass reproduces them deterministically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.schemas import (
    AgentName,
    EpistemicClass,
    EvidenceObject,
    Explanation,
    Hypothesis,
    HypothesisSet,
    KnowledgeStateSnapshot,
    Observation,
    SkepticFinding,
    SpeculationItem,
)
from .ledger import Ledger

if TYPE_CHECKING:
    from ..core.state import InvestigationState

# node_type (in the ledger payload) -> (schema model, state indexer method name)
_NODE_KINDS = {
    "Observation": (Observation, "_index_observation"),
    "EvidenceObject": (EvidenceObject, "_index_evidence"),
    "HypothesisSet": (HypothesisSet, "_index_set"),
    "Explanation": (Explanation, "_index_explanation"),
    "Hypothesis": (Hypothesis, "_index_hypothesis"),
    "SkepticFinding": (SkepticFinding, "_index_finding"),
    "Speculation": (SpeculationItem, "_index_speculation"),
    "KnowledgeStateSnapshot": (KnowledgeStateSnapshot, "_index_snapshot"),
}


def replay_state(ledger: Ledger, investigation_id: str | None = None) -> "InvestigationState":
    """Reconstruct an ``InvestigationState`` from a ledger's events."""
    # Imported lazily to avoid a ledger <-> core.state import cycle (state mirrors to the ledger).
    from ..core.state import InvestigationState

    events = ledger.events()
    if investigation_id is None:
        investigation_id = events[0].investigation_id if events else ""

    # The replayed state writes to a fresh, empty ledger; replay itself records nothing.
    state = InvestigationState(investigation_id, Ledger())

    for ev in events:
        p = ev.payload
        if ev.type == "node_add":
            model, indexer = _NODE_KINDS[p["node_type"]]
            obj = model.model_validate(p["object"])
            # Restore the provenance back-pointer to *this* creating event (as at write time).
            if hasattr(obj, "provenance"):
                obj.provenance.ledger_event_id = ev.event_id
            getattr(state, indexer)(obj)
        elif ev.type == "confidence_change":
            state._apply_confidence(p["hypothesis_id"], p["to"], p["reason"],
                                    AgentName(ev.actor), ev.iteration, ev.event_id,
                                    ev.timestamp)
        elif ev.type == "explanation_reclassify":
            state._apply_reclassify(p["explanation_id"], p["confidence"])
        elif ev.type == "hypothesis_promote":
            state.hypotheses[p["hypothesis_id"]].epistemic_class = EpistemicClass(p["to"])
        elif ev.type == "residual_mass_change":
            state.hypothesis_sets[p["set_id"]].residual_mass = p["to"]
        elif ev.type == "hypothesis_archive":
            state.hypotheses[p["hypothesis_id"]].status = "archived"
        elif ev.type == "hypothesis_reactivate":
            state.hypotheses[p["hypothesis_id"]].status = "reactivated"
        elif ev.type == "finding_resolved":
            state.findings[p["finding_id"]].resolved = True
        # investigation_start / report_emit carry no graph mutation; skipped.

    # Evidence links are a pure projection over recorded evidence (mirrors Synthesis Agent).
    state.relink_evidence()
    return state
