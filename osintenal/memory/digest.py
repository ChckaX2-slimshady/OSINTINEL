"""Build a ``RunDigest`` from a completed run — the **only** bridge into Memory (doc 06 Phase 4).

This is where the evidence/strategy firewall is enforced at the source: we read the *structure*
of a finished investigation (which adapter produced how much evidence, whether it supported the
gate-cleared insight, cost, iterations) and emit strategy metrics only. Evidence summaries,
payloads, structured content, and the ledger's recorded confidence history are never copied
forward — Memory learns *how* to investigate, not *what was found*.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.schemas import EpistemicClass
from .store import AdapterStat, CalibrationRecord, RunDigest

if TYPE_CHECKING:
    from ..adapters import AdapterRegistry
    from ..core.runtime.controller import InvestigationResult


def _winners(state) -> dict[str, str]:
    """The leading active hypothesis id per set (the run's 'answer' for attribution)."""
    winners: dict[str, str] = {}
    for set_id in state.hypothesis_sets:
        active = state.active_hypotheses(set_id)
        if active:
            winners[set_id] = max(active, key=lambda h: h.confidence).hypothesis_id
    return winners


def build_run_digest(result: "InvestigationResult", *,
                     registry: "AdapterRegistry | None" = None,
                     ground_truth: dict[str, str] | None = None) -> RunDigest:
    """Extract strategy/metrics from a finished run. ``ground_truth`` maps set_id -> the correct
    hypothesis statement (benchmark only) and yields calibration records."""
    state = result.state
    winners = _winners(state)
    winner_ids = set(winners.values())
    reached_insight = any(h.epistemic_class is EpistemicClass.INSIGHT
                          for h in state.hypotheses.values())
    threshold = result.investigation.config.confidence_threshold
    leading_confidence = max((state.hypotheses[w].confidence for w in winner_ids), default=0.0)
    # A run is "resolved" if it reached a gate-cleared insight or crossed the confidence
    # threshold. Only a resolved run credits its supporting adapters (doc 06 Phase 4).
    run_succeeded = reached_insight or leading_confidence >= threshold

    # Per-adapter strategy stats, attributed by provenance.tool_used (an id, not content).
    def caps_for(tool_id: str) -> list[str]:
        if registry is not None:
            try:
                return list(registry.get(tool_id).capabilities)
            except KeyError:
                pass
        return []

    stats: dict[str, AdapterStat] = {}
    capability_sequence: list[str] = []
    for ev in state.evidence.values():
        tool = ev.provenance.tool_used or "unknown"
        stat = stats.setdefault(tool, AdapterStat(adapter_id=tool, capabilities=caps_for(tool)))
        stat.evidence_produced += 1
        # contributed iff the run resolved AND this evidence supports the leader
        if run_succeeded and (set(ev.supports) & winner_ids):
            stat.contributed = True
        if stat.capabilities:
            capability_sequence.append(stat.capabilities[0])

    if registry is not None:
        for stat in stats.values():
            try:
                stat.cost_tokens = registry.get(stat.adapter_id).cost_of("collect").tokens \
                    * stat.evidence_produced
            except KeyError:
                pass

    calibration: list[CalibrationRecord] = []
    if ground_truth:
        for set_id, correct_statement in ground_truth.items():
            wid = winners.get(set_id)
            if wid is None:
                continue
            leader = state.hypotheses[wid]
            calibration.append(CalibrationRecord(
                predicted_confidence=leader.confidence,
                correct=leader.statement == correct_statement))

    budget = result.budget
    return RunDigest(
        investigation_id=result.investigation.investigation_id,
        domain=result.investigation.domain,
        set_count=len(state.hypothesis_sets),
        iterations=result.loop.iterations,
        termination_reason=result.loop.termination.reason or "max_iterations",
        reached_insight=reached_insight,
        leading_confidence=round(leading_confidence, 4),
        cost={"tokens": budget.tokens_used, "money_usd": budget.money_usd,
              "requests": budget.requests, "seconds": budget.seconds},
        adapter_stats=sorted(stats.values(), key=lambda s: s.adapter_id),
        capability_sequence=capability_sequence,
        calibration=calibration,
    )
