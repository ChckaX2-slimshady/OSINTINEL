"""Read-only ``GraphView`` (doc 04 §1) — the agent-facing window onto the graph.

Agents read; only the runtime writes (always via a ledger event). This view wraps a
``GraphStore`` and exposes the doc-04 §6 queries without granting mutation access.
"""

from __future__ import annotations

from .queries import (
    chain_terminates_in_information,
    contradiction_clusters,
    evidence_chain,
    independent_source_groups,
    source_monoculture,
    supporting_evidence,
)
from .store import GraphStore, Node


class GraphView:
    def __init__(self, store: GraphStore) -> None:
        self._store = store

    def get_node(self, node_id: str) -> Node | None:
        return self._store.get_node(node_id)

    def nodes(self, **kw) -> list[Node]:
        return self._store.nodes(**kw)

    def evidence_chain(self, node_id: str) -> list[Node]:
        return evidence_chain(self._store, node_id)

    def chain_terminates_in_information(self, node_id: str) -> bool:
        return chain_terminates_in_information(self._store, node_id)

    def supporting_evidence(self, hypothesis_id: str) -> list[Node]:
        return supporting_evidence(self._store, hypothesis_id)

    def independent_source_groups(self, hypothesis_id: str) -> set[str]:
        return independent_source_groups(self._store, hypothesis_id)

    def source_monoculture(self, set_id: str, **kw) -> bool:
        return source_monoculture(self._store, set_id, **kw)

    def contradiction_clusters(self, set_id: str) -> dict[str, int]:
        return contradiction_clusters(self._store, set_id)
