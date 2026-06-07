"""Phase 2 exit criterion: ladder & provenance constraints reject malformed writes (doc 04 §7).

These prove the Foundational Separation Principle is a database invariant, not a convention:
the graph backend refuses nodes without provenance, mis-tiered nodes, ladder-skipping edges,
and any attempt to derive a hypothesis-tier node from Speculation.
"""

from __future__ import annotations

import pytest

from osintinel.core.schemas import AcquisitionMethod, AgentName, EpistemicClass, Provenance
from osintinel.graph import ConstraintViolation, InMemoryGraphStore, Node
from osintinel.graph.store import SUPPORTS, SYNTHESIZED_FROM, Edge


def _prov(eid: str | None = "ev-1") -> Provenance:
    return Provenance(source="src", acquisition_method=AcquisitionMethod.DERIVED,
                      agent_responsible=AgentName.CONNECTIONS, confidence=0.5,
                      investigation_id="inv", ledger_event_id=eid)


def _node(node_id, node_type, *, klass=None, eid="ev-1") -> Node:
    return Node(node_id=node_id, node_type=node_type, label=node_id, provenance=_prov(eid),
                created_event_id=eid, epistemic_class=klass)


def test_node_without_created_event_id_rejected():
    store = InMemoryGraphStore()
    bad = Node(node_id="n1", node_type="Observation", label="x", provenance=_prov(None),
               created_event_id="", epistemic_class=EpistemicClass.INFORMATION)
    with pytest.raises(ConstraintViolation):
        store.add_node(bad)


def test_explanation_with_hypothesis_class_rejected():
    # An Explanation must be SPECULATION/EXTRAPOLATION — never a hypothesis-tier class.
    store = InMemoryGraphStore()
    with pytest.raises(ConstraintViolation):
        store.add_node(_node("e1", "Explanation", klass=EpistemicClass.INSIGHT))


def test_hypothesis_with_explanation_class_rejected():
    store = InMemoryGraphStore()
    with pytest.raises(ConstraintViolation):
        store.add_node(_node("h1", "Hypothesis", klass=EpistemicClass.SPECULATION))


def test_supports_edge_from_source_is_ladder_skip_rejected():
    # A Source wired straight onto a Hypothesis skips the INFORMATION rung.
    store = InMemoryGraphStore()
    store.add_node(_node("src:1", "Source"))
    store.add_node(_node("h1", "Hypothesis", klass=EpistemicClass.HYPOTHESIS))
    edge = Edge(edge_id="x1", edge_type=SUPPORTS, from_id="src:1", to_id="h1",
                provenance=_prov(), created_event_id="ev-1")
    with pytest.raises(ConstraintViolation):
        store.add_edge(edge)


def test_supports_edge_from_speculation_rejected():
    # Speculation quarantine: a Speculation node may not support a hypothesis.
    store = InMemoryGraphStore()
    store.add_node(_node("sp1", "Speculation", klass=EpistemicClass.SPECULATION))
    store.add_node(_node("h1", "Hypothesis", klass=EpistemicClass.HYPOTHESIS))
    edge = Edge(edge_id="x2", edge_type=SUPPORTS, from_id="sp1", to_id="h1",
                provenance=_prov(), created_event_id="ev-1")
    with pytest.raises(ConstraintViolation):
        store.add_edge(edge)


def test_synthesized_from_must_be_hypothesis_to_explanation():
    store = InMemoryGraphStore()
    store.add_node(_node("h1", "Hypothesis", klass=EpistemicClass.HYPOTHESIS))
    store.add_node(_node("o1", "Observation", klass=EpistemicClass.INFORMATION))
    edge = Edge(edge_id="x3", edge_type=SYNTHESIZED_FROM, from_id="h1", to_id="o1",
                provenance=_prov(), created_event_id="ev-1")
    with pytest.raises(ConstraintViolation):
        store.add_edge(edge)


def test_well_formed_graph_from_demo_passes(demo_result):
    # The real demo projection writes cleanly through every constraint.
    from osintinel.graph import build_graph
    store = build_graph(demo_result.state)
    assert len(store.nodes(node_type="Hypothesis")) >= 2
    assert store.nodes(node_type="Source")  # sources materialized
