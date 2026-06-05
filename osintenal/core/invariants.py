"""Epistemic invariants enforced at runtime (doc 03 §16, doc 09 §3).

These checks turn the Foundational Separation Principle and the brief's non-negotiables
into executable guarantees. The runtime calls ``check_state`` after each iteration and
``check_report`` before emitting a report; the epistemic test suite (tests/epistemic)
asserts the same invariants against synthetic states. A violation raises rather than
silently degrading an epistemic class.
"""

from __future__ import annotations

from .schemas import (
    EXPLANATION_CLASSES,
    HYPOTHESIS_CLASSES,
    EpistemicClass,
    InsightReport,
)
from .state import InvestigationState


class InvariantViolation(AssertionError):
    """Raised when an epistemic invariant is violated."""


def check_state(state: InvestigationState) -> None:
    """Invariants 1, 3, 4, 6 (doc 03 §16) over live investigation state."""
    for obj in (
        list(state.observations.values())
        + list(state.evidence.values())
        + list(state.hypotheses.values())
    ):
        # (1) Provenance-or-nothing: persisted objects carry a ledger-bound provenance.
        if obj.provenance.ledger_event_id is None:
            raise InvariantViolation(f"object missing ledger_event_id: {obj!r}")

    for h in state.hypotheses.values():
        # (4) confidence_history is append-only and ordered by iteration.
        iters = [e.iteration for e in h.confidence_history]
        if iters != sorted(iters):
            raise InvariantViolation(
                f"confidence_history not monotonically ordered: {h.hypothesis_id}"
            )
        # current confidence equals the last history entry (no out-of-band writes)
        if h.confidence_history and h.confidence != h.confidence_history[-1].confidence:
            raise InvariantViolation(
                f"confidence diverges from history: {h.hypothesis_id}"
            )

    for hs in state.hypothesis_sets.values():
        # (6) a set never drops below one active member.
        active = [hid for hid in hs.hypotheses
                  if state.hypotheses[hid].status != "archived"]
        if hs.hypotheses and not active:
            raise InvariantViolation(f"hypothesis set has no active member: {hs.set_id}")
        # residual mass + active confidences should not exceed 1 (probability sanity)
        total = hs.residual_mass + sum(state.hypotheses[hid].confidence for hid in active)
        if total > 1.0001:
            raise InvariantViolation(
                f"set probability mass exceeds 1.0 ({total:.3f}): {hs.set_id}"
            )

    # (5) Speculation quarantine: Speculative Possibility Engine items never carry
    # hypothesis-set edges (distinct from the in-flow SPECULATION explanation type).
    spec_ids = set(state.speculations)
    for h in state.hypotheses.values():
        if h.hypothesis_id in spec_ids:
            raise InvariantViolation("speculation leaked into hypothesis set")

    # (Foundational Separation) The two tiers must not be merged (doc 00 §3):
    #   explanations are SPECULATION or EXTRAPOLATION; hypotheses are HYPOTHESIS or INSIGHT.
    for ex in state.explanations.values():
        if ex.epistemic_class not in EXPLANATION_CLASSES:
            raise InvariantViolation(
                f"explanation {ex.explanation_id} has non-explanation class "
                f"{ex.epistemic_class}"
            )
    for h in state.hypotheses.values():
        if h.epistemic_class not in HYPOTHESIS_CLASSES:
            raise InvariantViolation(
                f"hypothesis {h.hypothesis_id} has non-hypothesis class {h.epistemic_class}"
            )


def check_skeptic_gate(state: InvestigationState, hypothesis_id: str) -> None:
    """Invariant 5: no promotion to INSIGHT/EXTRAPOLATION under an unresolved blocking finding."""
    h = state.hypotheses[hypothesis_id]
    if h.epistemic_class in (EpistemicClass.INSIGHT, EpistemicClass.EXTRAPOLATION):
        if state.unresolved_blocking_findings(hypothesis_id):
            raise InvariantViolation(
                f"hypothesis {hypothesis_id} promoted past Skeptic gate "
                f"while a blocking finding is unresolved"
            )


def check_report(report: InsightReport, state: InvestigationState) -> None:
    """Invariant 2 (auditability) + class consistency for the final deliverable."""
    # (7) explainable confidence: every promoted hypothesis has an assessment-backed history.
    for cps in report.connective_probability_scores:
        for rh in cps.ranked_hypotheses:
            h = state.hypotheses.get(rh.hypothesis_id)
            if h is None:
                raise InvariantViolation(f"report references unknown hypothesis {rh.hypothesis_id}")
            if rh.confidence > 0 and not h.confidence_history:
                raise InvariantViolation(
                    f"hypothesis {rh.hypothesis_id} has confidence but no history"
                )
    # (2) auditability: every reasoning step that asserts an INSIGHT/EXTRAPOLATION must
    # cite supporting evidence/hypotheses (a chain toward sourced INFORMATION).
    for step in report.reasoning_chain:
        if step.epistemic_class in (EpistemicClass.INSIGHT, EpistemicClass.EXTRAPOLATION):
            if not step.supports:
                raise InvariantViolation(
                    f"reasoning step {step.step} asserts {step.epistemic_class} "
                    f"without supporting references"
                )
