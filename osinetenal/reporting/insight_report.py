"""Assemble the InsightReport (doc 03 §15). Every report exposes uncertainty."""

from __future__ import annotations

from ..core.schemas import (
    ConnectiveProbabilityScore,
    EpistemicClass,
    InsightReport,
    Investigation,
    KnowledgeStateSnapshot,
    RankedHypothesis,
    ReasoningStep,
)
from ..core.state import InvestigationState


def build_insight_report(
    investigation: Investigation,
    state: InvestigationState,
    snapshot: KnowledgeStateSnapshot | None,
    termination_reason: str,
) -> InsightReport:
    scores: list[ConnectiveProbabilityScore] = []
    leaders = []
    for hs in state.hypothesis_sets.values():
        active = sorted(state.active_hypotheses(hs.set_id),
                        key=lambda h: h.confidence, reverse=True)
        ranked = [RankedHypothesis(hypothesis_id=h.hypothesis_id, statement=h.statement,
                                   confidence=h.confidence, epistemic_class=h.epistemic_class)
                  for h in active]
        scores.append(ConnectiveProbabilityScore(set_id=hs.set_id, question=hs.question,
                                                  ranked_hypotheses=ranked,
                                                  residual_mass=hs.residual_mass))
        if active:
            leaders.append((hs, active[0]))

    reasoning = _reasoning_chain(state, leaders)

    summary_bits = [
        f"{leader.statement!r} ({leader.confidence:.0%}, {leader.epistemic_class.value})"
        for _, leader in leaders
    ]
    exec_summary = (
        f"Investigation terminated ({termination_reason}). Leading explanation(s): "
        + "; ".join(summary_bits)
        + ". Competing hypotheses are preserved with full confidence history; uncertainty is "
          "reported below rather than concealed."
    ) if summary_bits else f"Investigation terminated ({termination_reason}); no hypotheses formed."

    info_summary = (
        f"Aggregated {len(state.observations)} observation(s) and acquired "
        f"{len(state.evidence)} evidence object(s) across "
        f"{len(state.hypothesis_sets)} competing-hypothesis set(s) from "
        f"{len({e.provenance.source for e in state.evidence.values()})} distinct source(s)."
    )

    known_unknowns = snapshot.known_unknowns if snapshot else []
    uu = snapshot.unknown_unknown_indicators if snapshot else []

    next_steps = [ku.question for ku in known_unknowns] or [
        "No open questions remain above the confidence threshold."
    ]

    appendix = _source_appendix(state)

    return InsightReport(
        investigation_id=investigation.investigation_id,
        executive_summary=exec_summary,
        information_summary=info_summary,
        connective_probability_scores=scores,
        hypotheses=list(state.hypotheses.keys()),
        known_unknowns=known_unknowns,
        unknown_unknown_indicators=uu,
        speculations=list(state.speculations.keys()),
        reasoning_chain=reasoning,
        recommended_next_investigations=next_steps,
        source_appendix=appendix,
        confidence_calibration_note=(
            "Confidences are set-normalized probabilities from calibration model "
            "'phase1-v1'; residual mass reserves probability for 'none of the above'. "
            "Promotion to EXTRAPOLATION requires the Skeptic gate to be clear."
        ),
    )


def _reasoning_chain(state, leaders) -> list[ReasoningStep]:
    steps: list[ReasoningStep] = []
    n = 0
    if state.observations:
        steps.append(ReasoningStep(
            step=n, claim=f"Aggregated {len(state.observations)} sourced observation(s).",
            epistemic_class=list(state.observations.values())[0].epistemic_class,
            supports=list(state.observations.keys()), agent="aggregation"))
        n += 1
    for hs in state.hypothesis_sets.values():
        steps.append(ReasoningStep(
            step=n, claim=f"Framed competing explanations for {hs.question!r}.",
            epistemic_class=EpistemicClass.CONNECTION,
            supports=hs.hypotheses, agent="connections"))
        n += 1
    for ev in state.evidence.values():
        steps.append(ReasoningStep(
            step=n, claim=f"Acquired evidence: {ev.summary}", epistemic_class=ev.epistemic_class,
            supports=[ev.evidence_id], agent="acquisition"))
        n += 1
    for _, leader in leaders:
        steps.append(ReasoningStep(
            step=n,
            claim=f"Leading explanation: {leader.statement!r} at confidence "
                  f"{leader.confidence:.2f}.",
            epistemic_class=leader.epistemic_class,
            supports=list(leader.supporting_evidence) + [leader.hypothesis_id],
            agent="synthesis"))
        n += 1
    return steps


def _source_appendix(state) -> list[dict]:
    seen: dict[str, dict] = {}
    for ev in state.evidence.values():
        p = ev.provenance
        if p.source in seen:
            continue
        seen[p.source] = {
            "source": p.source,
            "url": p.url,
            "acquisition_method": p.acquisition_method.value,
            "tool_used": p.tool_used,
            "independence_group": state.sources.get(p.source, p.source),
            "license_note": p.license_note,
        }
    return list(seen.values())
