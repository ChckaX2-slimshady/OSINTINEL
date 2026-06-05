"""Embedded in-memory ``GraphStore`` (doc 04 §1, Phase 1/2 default).

Zero-ops and laptop-runnable. The graph is a materialized view over the ledger, so this store
is always rebuildable by ``osintenal.graph.builder.build_graph`` from replayed state — a Neo4j
or SQLite backend can replace it behind the same port without touching agents.
"""

from __future__ import annotations

from ..constraints import check_edge, check_node
from ..store import EpistemicClass, Edge, Node


class InMemoryGraphStore:
    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}
        self._out: dict[str, list[str]] = {}
        self._in: dict[str, list[str]] = {}

    # -- writes (constraint-checked) ---------------------------------------
    def add_node(self, node: Node) -> None:
        check_node(node)
        if node.node_id in self._nodes:
            return  # idempotent (e.g. a Source introduced by several objects)
        self._nodes[node.node_id] = node
        self._out.setdefault(node.node_id, [])
        self._in.setdefault(node.node_id, [])

    def add_edge(self, edge: Edge) -> None:
        check_edge(edge, self)
        self._edges[edge.edge_id] = edge
        self._out.setdefault(edge.from_id, []).append(edge.edge_id)
        self._in.setdefault(edge.to_id, []).append(edge.edge_id)

    # -- reads -------------------------------------------------------------
    def get_node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def nodes(self, *, node_type: str | None = None,
              epistemic_class: EpistemicClass | None = None) -> list[Node]:
        out = self._nodes.values()
        if node_type is not None:
            out = [n for n in out if n.node_type == node_type]
        if epistemic_class is not None:
            out = [n for n in out if n.epistemic_class is epistemic_class]
        return list(out)

    def edges(self, *, edge_type: str | None = None) -> list[Edge]:
        return [e for e in self._edges.values()
                if edge_type is None or e.edge_type == edge_type]

    def out_edges(self, node_id: str, *, edge_type: str | None = None) -> list[Edge]:
        return [self._edges[eid] for eid in self._out.get(node_id, [])
                if edge_type is None or self._edges[eid].edge_type == edge_type]

    def in_edges(self, node_id: str, *, edge_type: str | None = None) -> list[Edge]:
        return [self._edges[eid] for eid in self._in.get(node_id, [])
                if edge_type is None or self._edges[eid].edge_type == edge_type]

    def __len__(self) -> int:
        return len(self._nodes)

    # -- canonical projection (backend-independent equality, doc 06 Phase 2) --
    def summary(self) -> dict:
        """Order-stable node/edge projection, excluding random edge ids, for comparison."""
        nodes = sorted(
            (n.node_id, n.node_type,
             n.epistemic_class.value if n.epistemic_class else None, n.label)
            for n in self._nodes.values()
        )
        edges = sorted(
            (e.edge_type, e.from_id, e.to_id, e.weight) for e in self._edges.values()
        )
        return {"nodes": nodes, "edges": edges}
