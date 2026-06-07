"""Termination Evaluator (doc 01 §5).

Stops the loop on any of: confidence threshold reached (with the Skeptic gate clear),
probability-score separation reached and stable, resource budget exhausted, a no-improvement
plateau, or the iteration ceiling.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..budget import BudgetGovernor
from ..schemas import InvestigationConfig
from ..state import InvestigationState


@dataclass
class IterationRecord:
    iteration: int
    max_leader_confidence: float
    total_evidence: int
    planner_dry: bool


@dataclass
class TerminationDecision:
    should_stop: bool
    reason: str | None = None
    detail: str = ""


class TerminationEvaluator:
    def evaluate(
        self,
        state: InvestigationState,
        config: InvestigationConfig,
        governor: BudgetGovernor,
        history: list[IterationRecord],
    ) -> TerminationDecision:
        if governor.is_exhausted():
            return TerminationDecision(True, "resource_threshold",
                                       f"budget exhausted: {governor.exhausted_dimension()}")

        # Confidence threshold: every set's leader resolved and past the Skeptic gate.
        if state.hypothesis_sets and self._all_sets_resolved(state, config):
            return TerminationDecision(True, "confidence_threshold",
                                       "all sets reached calibrated confidence with gate clear")

        if self._separation_stable(state, config, history):
            return TerminationDecision(True, "probability_separation",
                                       "a clear, stable leader separated from competitors")

        if history and history[-1].iteration + 1 >= config.max_iterations:
            return TerminationDecision(True, "max_iterations", "iteration ceiling reached")

        if self._plateaued(config, history):
            return TerminationDecision(True, "no_improvement_plateau",
                                       "no understanding delta and no new discriminating evidence")

        return TerminationDecision(False)

    def _all_sets_resolved(self, state, config) -> bool:
        for hs in state.hypothesis_sets.values():
            active = state.active_hypotheses(hs.set_id)
            if not active:
                return False
            leader = max(active, key=lambda h: h.confidence)
            gate_clear = not state.unresolved_blocking_findings(leader.hypothesis_id)
            if not (leader.confidence >= config.confidence_threshold and gate_clear):
                return False
        return True

    def _separation_stable(self, state, config, history) -> bool:
        if len(history) < 2:
            return False
        for hs in state.hypothesis_sets.values():
            active = sorted(state.active_hypotheses(hs.set_id),
                            key=lambda h: h.confidence, reverse=True)
            if len(active) < 2:
                continue
            leader = active[0]
            if state.unresolved_blocking_findings(leader.hypothesis_id):
                return False
            if (active[0].confidence - active[1].confidence) < config.probability_separation_threshold:
                return False
        # stable means the last two iterations did not change the leading confidence much
        return abs(history[-1].max_leader_confidence - history[-2].max_leader_confidence) < 0.02

    def _plateaued(self, config, history) -> bool:
        patience = config.no_improvement_patience
        if len(history) <= patience:
            return False
        window = history[-(patience + 1):]
        confs = [r.max_leader_confidence for r in window]
        no_gain = max(confs) - confs[0] < 1e-6
        no_new_evidence = all(window[i].total_evidence == window[0].total_evidence
                              for i in range(len(window)))
        return no_gain and no_new_evidence
