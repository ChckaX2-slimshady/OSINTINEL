"""Write-time integrity constraints (doc 04 §7) — the graph rejects malformed writes.

These turn the Foundational Separation Principle into a database invariant: no node may carry
the wrong tier, no edge may skip the epistemic ladder, and Speculation may never flow into a
hypothesis set. Enforced by the backend on every ``add_node``/``add_edge``.
"""

from __future__ import annotations

from ..core.schemas import EXPLANATION_CLASSES, HYPOTHESIS_CLASSES
from .store import (
    CONTRADICTS,
    DERIVED_FROM,
    SUPPORTS,
    SYNTHESIZED_FROM,
    Edge,
    GraphStore,
    Node,
)

# INFORMATION-tier node types that may originate supports/contradicts edges.
_INFORMATION_NODES = {"EvidenceObject", "Observation"}


class ConstraintViolation(RuntimeError):
    """Raised when a node/edge write would violate a graph integrity rule."""


def check_node(node: Node) -> None:
    # (1) Provenance-required: nothing enters the graph without a source + ledger back-pointer.
    if node.provenance is None or not node.created_event_id:
        raise ConstraintViolation(
            f"node {node.node_id} ({node.node_type}) lacks provenance/created_event_id"
        )
    if node.provenance.ledger_event_id is None:
        raise ConstraintViolation(f"node {node.node_id} provenance has no ledger_event_id")
    # (2) Tier integrity (Foundational Separation, doc 00 §3): explanations and hypotheses
    # must carry a class from their own tier — never the other's.
    if node.node_type == "Explanation" and node.epistemic_class not in EXPLANATION_CLASSES:
        raise ConstraintViolation(
            f"Explanation {node.node_id} has non-explanation class {node.epistemic_class}"
        )
    if node.node_type == "Hypothesis" and node.epistemic_class not in HYPOTHESIS_CLASSES:
        raise ConstraintViolation(
            f"Hypothesis {node.node_id} has non-hypothesis class {node.epistemic_class}"
        )


def check_edge(edge: Edge, store: GraphStore) -> None:
    if not edge.created_event_id:
        raise ConstraintViolation(f"edge {edge.edge_id} lacks created_event_id")
    src, dst = store.get_node(edge.from_id), store.get_node(edge.to_id)
    if src is None or dst is None:
        raise ConstraintViolation(
            f"edge {edge.edge_id} ({edge.edge_type}) references a missing endpoint"
        )

    # (3) Ladder constraint: evidence touches hypotheses only through INFORMATION nodes; a
    # Source/Speculation/Insight may not be wired straight onto a hypothesis (doc 04 §3/§7).
    if edge.edge_type in (SUPPORTS, CONTRADICTS):
        if src.node_type not in _INFORMATION_NODES:
            raise ConstraintViolation(
                f"{edge.edge_type} edge must originate at INFORMATION "
                f"(got {src.node_type} {src.node_id}) — ladder-skip rejected"
            )
        if dst.node_type != "Hypothesis":
            raise ConstraintViolation(
                f"{edge.edge_type} edge must target a Hypothesis (got {dst.node_type})"
            )
    # synthesized_from binds a hypothesis to the explanation(s) it was built from.
    elif edge.edge_type == SYNTHESIZED_FROM:
        if src.node_type != "Hypothesis" or dst.node_type != "Explanation":
            raise ConstraintViolation(
                f"synthesized_from must be Hypothesis->Explanation "
                f"(got {src.node_type}->{dst.node_type})"
            )
    # (5) Speculation quarantine: a Speculation node can never derive a hypothesis-tier node.
    elif edge.edge_type == DERIVED_FROM:
        if dst.node_type == "Speculation":
            raise ConstraintViolation(
                "derived_from a Speculation node is forbidden (speculation quarantine)"
            )
