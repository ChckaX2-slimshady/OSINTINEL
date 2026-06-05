"""Knowledge graph (doc 04): GraphStore port, embedded backend, constraints, queries, view.

The graph is a materialized view over the append-only ledger. ``build_graph(state)`` projects
an investigation's state into a constraint-checked property graph; because state is replayable
from the ledger, the graph is fully reconstructable from the event log alone.
"""

from __future__ import annotations

from .backends import InMemoryGraphStore
from .builder import build_graph
from .constraints import ConstraintViolation, check_edge, check_node
from .queries import (
    chain_terminates_in_information,
    contradiction_clusters,
    evidence_chain,
    independent_source_groups,
    source_monoculture,
    supporting_evidence,
)
from .store import Edge, GraphStore, Node
from .view import GraphView

__all__ = [
    "ConstraintViolation",
    "Edge",
    "GraphStore",
    "GraphView",
    "InMemoryGraphStore",
    "Node",
    "build_graph",
    "chain_terminates_in_information",
    "check_edge",
    "check_node",
    "contradiction_clusters",
    "evidence_chain",
    "independent_source_groups",
    "source_monoculture",
    "supporting_evidence",
]
