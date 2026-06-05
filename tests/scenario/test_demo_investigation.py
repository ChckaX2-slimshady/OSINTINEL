"""Scenario tests for the full recursive loop (doc 09 §4), run deterministically offline.

These assert the Phase 1 exit criteria (doc 06): end-to-end run emits a schema-valid report,
the Skeptic gate provably blocks promotion until independent corroboration arrives, and
termination conditions are honored.
"""

from __future__ import annotations

from osinetenal.core.runtime import InvestigationController
from osinetenal.core.schemas import EpistemicClass, InsightReport
from osinetenal.scenarios import build_demo_investigation


def test_run_emits_schema_valid_report(demo_result):
    report = demo_result.report
    assert isinstance(report, InsightReport)
    # round-trips through validation
    InsightReport.model_validate_json(report.model_dump_json())
    assert report.connective_probability_scores
    assert report.reasoning_chain


def test_converges_on_communications_structure(demo_result):
    cps = demo_result.report.connective_probability_scores[0]
    leader = cps.ranked_hypotheses[0]
    assert leader.statement == "communications structure"
    assert leader.confidence >= 0.85
    assert leader.epistemic_class is EpistemicClass.EXTRAPOLATION
    assert demo_result.loop.termination.reason == "confidence_threshold"


def test_competing_hypotheses_present_with_residual(demo_result):
    cps = demo_result.report.connective_probability_scores[0]
    statements = {rh.statement for rh in cps.ranked_hypotheses}
    assert {"summit marker", "image artifact"} <= statements  # losers preserved
    assert cps.residual_mass > 0.0  # "none of the above" mass retained


def test_skeptic_gate_holds_promotion_until_independent_corroboration():
    """Step the loop manually and assert the leader is NOT promoted while it rests on a
    single source, then IS promoted once a second independent source corroborates it."""
    investigation, registry = build_demo_investigation()
    controller = InvestigationController(registry)

    from osinetenal.core.budget import BudgetGovernor
    from osinetenal.core.state import InvestigationState
    from osinetenal.ledger import Ledger

    ledger = Ledger()
    state = InvestigationState(investigation.investigation_id, ledger)
    governor = BudgetGovernor(investigation.config.budgets)
    engine = controller.engine

    from osinetenal.agents import AgentContext

    def step(i):
        ctx = AgentContext(investigation, state, i, governor, registry)
        engine.aggregation.run(ctx)
        engine.connections.run(ctx)
        reqs = engine.planning.run(ctx)
        plans = engine.selection.run(ctx, reqs)
        engine.acquisition.run(ctx, plans)
        engine.synthesis.run(ctx)
        engine.skeptic.run(ctx)
        engine.confidence.run(ctx)
        engine.epistemology.run(ctx)

    hs_id = None

    # Iterations 0 and 1: evidence comes only from OpenStreetMap (one independent group).
    step(0)
    step(1)
    hs_id = next(iter(state.hypothesis_sets))
    leader = max(state.active_hypotheses(hs_id), key=lambda h: h.confidence)
    assert leader.statement == "communications structure"
    assert leader.confidence >= 0.75  # confident...
    assert len(state.independent_source_groups(leader.hypothesis_id)) == 1
    assert leader.epistemic_class is EpistemicClass.HYPOTHESIS  # ...but gate holds promotion
    assert state.unresolved_blocking_findings(leader.hypothesis_id)  # blocking finding exists

    # Iteration 2: Wikidata corroborates -> second independent group -> gate clears.
    step(2)
    leader = max(state.active_hypotheses(hs_id), key=lambda h: h.confidence)
    assert len(state.independent_source_groups(leader.hypothesis_id)) >= 2
    assert not state.unresolved_blocking_findings(leader.hypothesis_id)
    assert leader.epistemic_class is EpistemicClass.EXTRAPOLATION  # now promoted


def test_budget_termination():
    investigation, registry = build_demo_investigation()
    investigation.config.budgets.tokens = 1  # exhaust immediately
    controller = InvestigationController(registry)
    result = controller.run(investigation)
    assert result.loop.termination.reason == "resource_threshold"
    # even a budget-terminated run emits a valid, labeled report
    InsightReport.model_validate_json(result.report.model_dump_json())


def test_ledger_chain_verifies(demo_result):
    assert demo_result.ledger.verify() is True
    assert len(demo_result.ledger) > 0
