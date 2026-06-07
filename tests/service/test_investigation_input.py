"""The investigation input layer — turning user input into a full, dashboard-ready run."""

from __future__ import annotations

from osintenal.core.schemas import EpistemicClass
from osintenal.graph import build_graph, chain_terminates_in_information
from osintenal.ledger import replay_state
from osintenal.service import EvidenceInput, InvestigationSummary, run_investigation


def test_tagged_evidence_drives_the_right_hypothesis():
    r = run_investigation(
        question="What is the circular structure on the ridge?",
        candidates=["communications mast", "wind turbine", "water tower"],
        evidence=[
            EvidenceInput(text="OSM node tagged man_made=mast.", source="OpenStreetMap",
                          group="osm", supports=0, weight=0.8),
            EvidenceInput(text="Wikidata radio relay station entity nearby.", source="Wikidata",
                          group="wikidata", supports=0, weight=0.6),
        ])
    leader = r.report.connective_probability_scores[0].ranked_hypotheses[0]
    assert leader.statement == "communications mast"
    assert leader.epistemic_class is EpistemicClass.INSIGHT          # two independent groups
    assert r.ledger.verify() is True


def test_result_is_dashboard_and_replay_ready():
    r = run_investigation(question="A or B?", candidates=["A", "B"],
                          evidence=[EvidenceInput(text="supports A", supports=0)])
    # full InvestigationResult shape: graph builds, audit chain works, replay is byte-identical
    assert build_graph(r.state).nodes()
    assert replay_state(r.ledger).snapshot() == r.state.snapshot()
    leader = r.report.connective_probability_scores[0].ranked_hypotheses[0]
    assert chain_terminates_in_information(build_graph(r.state), leader.hypothesis_id)


def test_single_candidate_is_padded_to_keep_the_space_open():
    r = run_investigation(question="Is it X?", candidates=["X"])
    ranked = r.report.connective_probability_scores[0].ranked_hypotheses
    assert len(ranked) >= 2  # an alternative is always preserved


def test_summary_is_serializable_and_ranked():
    r = run_investigation(question="A or B?", candidates=["A", "B"],
                          evidence=[EvidenceInput(text="supports B", supports=1)])
    s = InvestigationSummary.from_result(r)
    assert s.leader == "B" and s.ranked and s.ranked[0]["statement"] == "B"


def test_runs_without_evidence_or_model_deterministically():
    a = run_investigation(question="A or B?", candidates=["A", "B"])
    b = run_investigation(question="A or B?", candidates=["A", "B"])
    # no evidence, no model → reproducible framing
    assert [h.statement for h in a.state.hypotheses.values()] == \
           [h.statement for h in b.state.hypotheses.values()]
