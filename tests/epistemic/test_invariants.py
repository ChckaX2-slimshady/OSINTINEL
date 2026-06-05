"""Epistemic invariant tests (doc 09 §3) — release blockers.

These encode the Foundational Separation Principle and the brief's non-negotiables. They run
against the deterministic demo and against hand-built adversarial states.
"""

from __future__ import annotations

import pytest

from osintenal.core import invariants
from osintenal.core.invariants import InvariantViolation
from osintenal.core.schemas import EpistemicClass


def test_demo_state_and_report_satisfy_invariants(demo_result):
    invariants.check_state(demo_result.state)
    invariants.check_report(demo_result.report, demo_result.state)


def test_provenance_or_nothing(demo_result):
    # Invariant 1: every persisted object carries a ledger-bound provenance.
    for obj in (
        list(demo_result.state.observations.values())
        + list(demo_result.state.evidence.values())
        + list(demo_result.state.hypotheses.values())
    ):
        assert obj.provenance.ledger_event_id is not None


def test_confidence_history_is_append_only_and_ordered(demo_result):
    # Invariant 4: append-only, monotonically ordered by iteration; current == last entry.
    for h in demo_result.state.hypotheses.values():
        iters = [e.iteration for e in h.confidence_history]
        assert iters == sorted(iters)
        if h.confidence_history:
            assert h.confidence == h.confidence_history[-1].confidence


def test_competing_hypotheses_preserved(demo_result):
    # Hypothesis Preservation Rule: nothing deleted; the set keeps >= 2 members; losers remain.
    for hs in demo_result.state.hypothesis_sets.values():
        assert len(hs.hypotheses) >= 2
        active = demo_result.state.active_hypotheses(hs.set_id)
        assert len(active) >= 1
        # losing hypotheses persist with full history, not removed
        for hid in hs.hypotheses:
            assert hid in demo_result.state.hypotheses


def test_foundational_separation_tiers_not_merged(demo_result):
    # Foundational Separation (doc 00 §3): explanations are SPECULATION/EXTRAPOLATION;
    # hypotheses are HYPOTHESIS/INSIGHT. The two tiers must never be merged.
    from osintenal.core.schemas import EXPLANATION_CLASSES, HYPOTHESIS_CLASSES
    state = demo_result.state
    assert state.explanations  # the explanation tier exists
    for ex in state.explanations.values():
        assert ex.epistemic_class in EXPLANATION_CLASSES
    for h in state.hypotheses.values():
        assert h.epistemic_class in HYPOTHESIS_CLASSES
        # every synthesized hypothesis traces back to a competing explanation
        assert h.derived_from_explanations


def test_auditability_chain_terminates_in_information(demo_result):
    # Invariant 2: the leading INSIGHT cites supporting evidence (INFORMATION).
    state = demo_result.state
    for hs in state.hypothesis_sets.values():
        leader = max(state.active_hypotheses(hs.set_id), key=lambda h: h.confidence)
        if leader.epistemic_class in (EpistemicClass.EXTRAPOLATION, EpistemicClass.INSIGHT):
            assert leader.supporting_evidence
            for eid in leader.supporting_evidence:
                ev = state.evidence[eid]
                assert ev.epistemic_class is EpistemicClass.INFORMATION
                assert ev.provenance.ledger_event_id is not None


def test_skeptic_gate_violation_is_detected(demo_result):
    # Invariant 5: forcibly promoting a hypothesis under an unresolved blocking finding
    # must be caught by check_skeptic_gate.
    state = demo_result.state
    hs = next(iter(state.hypothesis_sets.values()))
    leader = max(state.active_hypotheses(hs.set_id), key=lambda h: h.confidence)

    from osintenal.core.schemas import AcquisitionMethod, AgentName, SkepticFinding, Provenance

    finding = SkepticFinding(
        target_ref=leader.hypothesis_id,
        category="source_dependency",
        description="synthetic blocking finding",
        severity="blocking",
        provenance=Provenance(source="test", acquisition_method=AcquisitionMethod.DERIVED,
                              agent_responsible=AgentName.SKEPTIC, confidence=0.5,
                              investigation_id=state.investigation_id),
    )
    state.add_finding(finding, iteration=99)
    leader.epistemic_class = EpistemicClass.INSIGHT  # illegal promotion under blocking finding
    with pytest.raises(InvariantViolation):
        invariants.check_skeptic_gate(state, leader.hypothesis_id)


def test_set_minimum_preserved_on_archive(demo_result):
    # Invariant 6: cannot archive the last active member of a set.
    from osintenal.core.state import StatePreservationError

    state = demo_result.state
    hs = next(iter(state.hypothesis_sets.values()))
    active = state.active_hypotheses(hs.set_id)
    # archive all but one is allowed; archiving the final one must raise
    for h in active[:-1]:
        state.archive_hypothesis(h.hypothesis_id, iteration=99)
    with pytest.raises(StatePreservationError):
        state.archive_hypothesis(state.active_hypotheses(hs.set_id)[0].hypothesis_id, 99)
