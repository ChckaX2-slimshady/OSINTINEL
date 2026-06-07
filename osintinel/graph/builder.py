"""Materialize the doc-04 knowledge graph from an ``InvestigationState`` (doc 04 §2–§5).

The graph is a *view* over recorded state: every node/edge carries the ``created_event_id`` of
the ledger event that introduced its object, so the projection is itself auditable. Because
``InvestigationState`` is replayable from the ledger, ``build_graph(replay_state(ledger))`` is
the materialized graph reconstructed purely from the event log (doc 04 §8).

Nodes are added before edges so the constraint layer can validate endpoints.
"""

from __future__ import annotations

from ..core.ids import new_id
from ..core.state import InvestigationState
from .backends import InMemoryGraphStore
from .store import (
    CONTRADICTS,
    DERIVED_FROM,
    HAS_EXPLANATION,
    HAS_MEMBER,
    SUPPORTS,
    SYNTHESIZED_FROM,
    Edge,
    Node,
)


def _source_node_id(name: str) -> str:
    return f"source:{name}"


def build_graph(state: InvestigationState) -> InMemoryGraphStore:
    store = InMemoryGraphStore()

    # --- nodes ---------------------------------------------------------------
    def source_node_for(prov, independence_group: str | None = None) -> str:
        sid = _source_node_id(prov.source)
        group = state.sources.get(prov.source, independence_group or prov.source)
        store.add_node(Node(
            node_id=sid, node_type="Source", label=prov.source, provenance=prov,
            created_event_id=prov.ledger_event_id,
            attributes={"independence_group": group},
        ))
        return sid

    for hs in state.hypothesis_sets.values():
        store.add_node(Node(
            node_id=hs.set_id, node_type="HypothesisSet", label=hs.question,
            provenance=hs.provenance, created_event_id=hs.provenance.ledger_event_id,
            attributes={"residual_mass": hs.residual_mass},
        ))
    for ex in state.explanations.values():
        store.add_node(Node(
            node_id=ex.explanation_id, node_type="Explanation", label=ex.statement,
            epistemic_class=ex.epistemic_class, provenance=ex.provenance,
            created_event_id=ex.provenance.ledger_event_id,
            attributes={"confidence": ex.confidence, "set_id": ex.set_id},
        ))
    for h in state.hypotheses.values():
        store.add_node(Node(
            node_id=h.hypothesis_id, node_type="Hypothesis", label=h.statement,
            epistemic_class=h.epistemic_class, provenance=h.provenance,
            created_event_id=h.provenance.ledger_event_id,
            attributes={"confidence": h.confidence, "status": h.status, "set_id": h.set_id},
        ))
    for obs in state.observations.values():
        store.add_node(Node(
            node_id=obs.observation_id, node_type="Observation", label=obs.type,
            epistemic_class=obs.epistemic_class, provenance=obs.provenance,
            created_event_id=obs.provenance.ledger_event_id,
            attributes={"modality": obs.modality},
        ))
        source_node_for(obs.provenance)
    for ev in state.evidence.values():
        store.add_node(Node(
            node_id=ev.evidence_id, node_type="EvidenceObject", label=ev.summary,
            epistemic_class=ev.epistemic_class, provenance=ev.provenance,
            created_event_id=ev.provenance.ledger_event_id,
            attributes={"kind": ev.kind},
        ))
        source_node_for(ev.provenance, ev.structured.get("independence_group"))
    for sp in state.speculations.values():
        store.add_node(Node(
            node_id=sp.speculation_id, node_type="Speculation", label=sp.statement,
            epistemic_class=sp.epistemic_class, provenance=sp.provenance,
            created_event_id=sp.provenance.ledger_event_id,
            attributes={"speculative_confidence": sp.speculative_confidence},
        ))

    # --- edges ---------------------------------------------------------------
    def edge(edge_type, frm, to, prov, weight=None) -> None:
        store.add_edge(Edge(edge_id=new_id(), edge_type=edge_type, from_id=frm, to_id=to,
                            provenance=prov, created_event_id=prov.ledger_event_id,
                            weight=weight))

    for hs in state.hypothesis_sets.values():
        for ex_id in hs.explanations:
            edge(HAS_EXPLANATION, hs.set_id, ex_id, state.explanations[ex_id].provenance)
        for h_id in hs.hypotheses:
            edge(HAS_MEMBER, hs.set_id, h_id, state.hypotheses[h_id].provenance)
    for h in state.hypotheses.values():
        for ex_id in h.derived_from_explanations:
            if ex_id in state.explanations:
                edge(SYNTHESIZED_FROM, h.hypothesis_id, ex_id, h.provenance)
    for obs in state.observations.values():
        edge(DERIVED_FROM, obs.observation_id, _source_node_id(obs.provenance.source),
             obs.provenance)
    for ev in state.evidence.values():
        edge(DERIVED_FROM, ev.evidence_id, _source_node_id(ev.provenance.source), ev.provenance)
        for h_id in ev.supports:
            edge(SUPPORTS, ev.evidence_id, h_id, ev.provenance,
                 weight=ev.weights.get(h_id))
        for h_id in ev.contradicts:
            edge(CONTRADICTS, ev.evidence_id, h_id, ev.provenance,
                 weight=ev.weights.get(h_id))

    return store
