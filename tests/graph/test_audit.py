"""Phase 2 exit criterion: an audit query returns a complete evidence chain terminating in
sourced INFORMATION nodes (doc 04 §6, doc 03 §16.3); graph queries agree with state.
"""

from __future__ import annotations

from osintinel.core.schemas import EpistemicClass
from osintinel.graph import (
    build_graph,
    chain_terminates_in_information,
    contradiction_clusters,
    evidence_chain,
    independent_source_groups,
    source_monoculture,
)


def _leading_insight_id(demo_result):
    cps = demo_result.report.connective_probability_scores[0]
    return cps.ranked_hypotheses[0].hypothesis_id


def test_evidence_chain_terminates_in_sourced_information(demo_result):
    store = build_graph(demo_result.state)
    insight_id = _leading_insight_id(demo_result)
    chain = evidence_chain(store, insight_id)

    types = [n.node_type for n in chain]
    assert types[0] == "Hypothesis"
    assert "Explanation" in types            # passes through the explanation tier
    assert "EvidenceObject" in types         # reaches INFORMATION
    assert "Source" in types                 # ...which is sourced
    # auditability guarantee
    assert chain_terminates_in_information(store, insight_id) is True
    # every INFORMATION node in the chain carries provenance with a ledger back-pointer
    for n in chain:
        if n.epistemic_class is EpistemicClass.INFORMATION:
            assert n.provenance.ledger_event_id is not None


def test_graph_independence_matches_state(demo_result):
    store = build_graph(demo_result.state)
    insight_id = _leading_insight_id(demo_result)
    # leading insight corroborated by >= 2 independent groups (it cleared the Skeptic gate)
    graph_groups = independent_source_groups(store, insight_id)
    assert graph_groups == demo_result.state.independent_source_groups(insight_id)
    assert len(graph_groups) >= 2


def test_monoculture_and_contradiction_queries(demo_result):
    store = build_graph(demo_result.state)
    set_id = demo_result.report.connective_probability_scores[0].set_id
    # the leader is multi-source, so the set is not a monoculture
    assert source_monoculture(store, set_id) is False
    clusters = contradiction_clusters(store, set_id)
    # losing hypotheses carry contradicting evidence in this scenario
    assert sum(clusters.values()) >= 1
