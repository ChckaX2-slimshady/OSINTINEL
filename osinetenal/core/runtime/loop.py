"""Recursive Loop Engine (doc 01 §4).

Runs Observe → Hypothesize → Plan → Investigate → Synthesize → Challenge → Update Confidence
→ Update Knowledge State → Repeat. The runtime — not the agents — owns this ordering, which
is what keeps runs deterministic, replayable, and auditable. Each iteration is recorded to
the ledger and checked against the epistemic invariants before the loop continues.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...adapters import AdapterRegistry
from ...agents import (
    AcquisitionAgent,
    AggregationAgent,
    AgentContext,
    ConfidenceAgent,
    ConnectionsAgent,
    EpistemologyAgent,
    EvidencePlanningAgent,
    SkepticAgent,
    SpeculationAgent,
    SynthesisAgent,
    ToolSelectionAgent,
)
from ...reporting import build_insight_report
from .. import invariants
from ..budget import BudgetExhausted, BudgetGovernor
from ..schemas import InsightReport, Investigation
from ..state import InvestigationState
from .termination import IterationRecord, TerminationDecision, TerminationEvaluator


@dataclass
class LoopResult:
    report: InsightReport
    iterations: int
    termination: TerminationDecision
    history: list[IterationRecord] = field(default_factory=list)


class RecursiveLoopEngine:
    def __init__(self, registry: AdapterRegistry) -> None:
        self.registry = registry
        self.aggregation = AggregationAgent()
        self.connections = ConnectionsAgent()
        self.planning = EvidencePlanningAgent()
        self.selection = ToolSelectionAgent()
        self.acquisition = AcquisitionAgent()
        self.synthesis = SynthesisAgent()
        self.skeptic = SkepticAgent()
        self.confidence = ConfidenceAgent()
        self.epistemology = EpistemologyAgent()
        self.speculation = SpeculationAgent()
        self.terminator = TerminationEvaluator()

    def run(
        self,
        investigation: Investigation,
        state: InvestigationState,
        governor: BudgetGovernor,
    ) -> LoopResult:
        history: list[IterationRecord] = []
        snapshot = None
        decision = TerminationDecision(False)

        for iteration in range(investigation.config.max_iterations):
            investigation.current_iteration = iteration
            ctx = AgentContext(investigation, state, iteration, governor, self.registry)

            # OBSERVE → HYPOTHESIZE
            self.aggregation.run(ctx)
            self.connections.run(ctx)

            # PLAN → INVESTIGATE
            requests = self.planning.run(ctx)
            plans = self.selection.run(ctx, requests)
            try:
                evidence = self.acquisition.run(ctx, plans)
            except BudgetExhausted:
                evidence = []
            planner_dry = not plans or not evidence
            if planner_dry:
                # Expand the possibility space rather than fabricate (doc 02 §10).
                self.speculation.run(ctx)

            # SYNTHESIZE → CHALLENGE (gate) → UPDATE CONFIDENCE
            self.synthesis.run(ctx)
            self.skeptic.run(ctx)
            self.confidence.run(ctx)

            # UPDATE KNOWLEDGE STATE
            snapshot = self.epistemology.run(ctx)
            investigation.knowledge_state = snapshot.snapshot_id

            # invariants must hold every iteration (release-blocking in tests)
            invariants.check_state(state)

            history.append(self._record(state, iteration, planner_dry))
            self._charge_iteration(governor)

            decision = self.terminator.evaluate(
                state, investigation.config, governor, history
            )
            if decision.should_stop:
                break

        report = build_insight_report(
            investigation, state, snapshot, decision.reason or "max_iterations"
        )
        invariants.check_report(report, state)
        investigation.report_ref = report.report_id
        investigation.status = "completed"
        return LoopResult(report=report, iterations=len(history),
                          termination=decision, history=history)

    @staticmethod
    def _record(state, iteration, planner_dry) -> IterationRecord:
        max_leader = 0.0
        for hs in state.hypothesis_sets.values():
            active = state.active_hypotheses(hs.set_id)
            if active:
                max_leader = max(max_leader, max(h.confidence for h in active))
        return IterationRecord(
            iteration=iteration,
            max_leader_confidence=max_leader,
            total_evidence=len(state.evidence),
            planner_dry=planner_dry,
        )

    @staticmethod
    def _charge_iteration(governor: BudgetGovernor) -> None:
        # Account for the per-iteration agent reasoning cost (doc 08 token accounting).
        governor.charge(tokens=1500, money_usd=0.0)
