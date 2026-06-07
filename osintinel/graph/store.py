"""The ``GraphStore`` port and its node/edge value types (doc 04 §1–§3).

The knowledge graph is accessed only through this port, so the backend (in-memory now;
Neo4j/SQLite later) is swappable without touching agents. Writes are runtime-only and always
flow through a ledger event (the nodes/edges carry ``created_event_id`` back-pointers);
reads are exposed to agents via ``GraphView``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..core.schemas import EpistemicClass, Provenance

# Edge types (doc 04 §3). "but not limited to" — extensible.
SUPPORTS = "supports"
CONTRADICTS = "contradicts"
SYNTHESIZED_FROM = "synthesized_from"
DERIVED_FROM = "derived_from"
HAS_MEMBER = "has_member"          # HypothesisSet -> Hypothesis (structural)
HAS_EXPLANATION = "has_explanation"  # HypothesisSet -> Explanation (structural)


@dataclass(frozen=True)
class Node:
    node_id: str
    node_type: str
    label: str
    provenance: Provenance
    created_event_id: str
    epistemic_class: EpistemicClass | None = None
    attributes: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    edge_id: str
    edge_type: str
    from_id: str
    to_id: str
    provenance: Provenance
    created_event_id: str
    weight: float | None = None


@runtime_checkable
class GraphStore(Protocol):
    """Backend-neutral graph contract. Writes apply write-time constraints (doc 04 §7)."""

    def add_node(self, node: Node) -> None: ...
    def add_edge(self, edge: Edge) -> None: ...
    def get_node(self, node_id: str) -> Node | None: ...
    def nodes(self, *, node_type: str | None = None,
              epistemic_class: EpistemicClass | None = None) -> list[Node]: ...
    def edges(self, *, edge_type: str | None = None) -> list[Edge]: ...
    def out_edges(self, node_id: str, *, edge_type: str | None = None) -> list[Edge]: ...
    def in_edges(self, node_id: str, *, edge_type: str | None = None) -> list[Edge]: ...
