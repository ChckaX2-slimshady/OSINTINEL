"""Representative graph queries (doc 04 §6) over a ``GraphStore``.

These run the audit and Confidence/Epistemology graph queries *through the port*, proving the
graph — not just the in-memory state — answers them. The headline is ``evidence_chain``: the
auditability guarantee that any INSIGHT traces down to sourced INFORMATION (doc 03 §16.3).
"""

from __future__ import annotations

from ..core.schemas import EpistemicClass
from .store import (
    CONTRADICTS,
    DERIVED_FROM,
    SUPPORTS,
    SYNTHESIZED_FROM,
    GraphStore,
    Node,
)

_INFORMATION_NODES = {"EvidenceObject", "Observation"}


def evidence_chain(store: GraphStore, node_id: str) -> list[Node]:
    """The full audit chain beneath a hypothesis/insight, terminating in sourced INFORMATION.

    Walks downward: Hypothesis --synthesized_from--> Explanation; Hypothesis <--supports/
    contradicts-- Evidence; Evidence/Observation --derived_from--> Source. Returns the visited
    nodes in breadth-first (top-down) order.
    """
    start = store.get_node(node_id)
    if start is None:
        return []
    order: list[Node] = []
    seen: set[str] = set()
    queue = [start]
    while queue:
        node = queue.pop(0)
        if node.node_id in seen:
            continue
        seen.add(node.node_id)
        order.append(node)

        nxt: list[str] = []
        # explanations a hypothesis was synthesized from
        nxt += [e.to_id for e in store.out_edges(node.node_id, edge_type=SYNTHESIZED_FROM)]
        # evidence that supports/contradicts this hypothesis (incoming)
        nxt += [e.from_id for e in store.in_edges(node.node_id, edge_type=SUPPORTS)]
        nxt += [e.from_id for e in store.in_edges(node.node_id, edge_type=CONTRADICTS)]
        # sources an evidence/observation derives from (outgoing)
        nxt += [e.to_id for e in store.out_edges(node.node_id, edge_type=DERIVED_FROM)]
        for nid in nxt:
            child = store.get_node(nid)
            if child is not None and child.node_id not in seen:
                queue.append(child)
    return order


def chain_terminates_in_information(store: GraphStore, node_id: str) -> bool:
    """True iff the evidence chain reaches at least one sourced INFORMATION node."""
    for n in evidence_chain(store, node_id):
        if (n.node_type in _INFORMATION_NODES
                and n.epistemic_class is EpistemicClass.INFORMATION
                and store.out_edges(n.node_id, edge_type=DERIVED_FROM)):
            return True
    return False


def supporting_evidence(store: GraphStore, hypothesis_id: str) -> list[Node]:
    return [store.get_node(e.from_id)
            for e in store.in_edges(hypothesis_id, edge_type=SUPPORTS)]


def independent_source_groups(store: GraphStore, hypothesis_id: str) -> set[str]:
    """Distinct source independence groups behind a hypothesis (Confidence factor, doc 04 §6)."""
    groups: set[str] = set()
    for ev in supporting_evidence(store, hypothesis_id):
        for d in store.out_edges(ev.node_id, edge_type=DERIVED_FROM):
            src = store.get_node(d.to_id)
            if src is not None:
                groups.add(src.attributes.get("independence_group", src.label))
    return groups


def source_monoculture(store: GraphStore, set_id: str, *, min_evidence: int = 3) -> bool:
    """UU-indicator: >= min_evidence supporting evidence but a single independence group."""
    evidence_count, groups = 0, set()
    for h in store.out_edges(set_id, edge_type="has_member"):
        for ev in supporting_evidence(store, h.to_id):
            evidence_count += 1
            for d in store.out_edges(ev.node_id, edge_type=DERIVED_FROM):
                src = store.get_node(d.to_id)
                if src is not None:
                    groups.add(src.attributes.get("independence_group", src.label))
    return evidence_count >= min_evidence and len(groups) == 1


def contradiction_clusters(store: GraphStore, set_id: str) -> dict[str, int]:
    """Map each hypothesis in a set to its count of contradicting evidence (Skeptic signal)."""
    out: dict[str, int] = {}
    for h in store.out_edges(set_id, edge_type="has_member"):
        out[h.to_id] = len(store.in_edges(h.to_id, edge_type=CONTRADICTS))
    return out
