"""Investigation Controller (doc 01 §2.1).

Holds an investigation's lifecycle: wires the ledger, state store, budget governor, adapter
registry, and the loop engine, then runs the investigation to a report. Returns the report
plus the ledger so callers can verify auditability and replay.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...adapters import AdapterRegistry
from ...ledger import Ledger
from ..budget import BudgetGovernor
from ..schemas import BudgetSnapshot, InsightReport, Investigation
from ..state import InvestigationState
from .loop import LoopResult, RecursiveLoopEngine


@dataclass
class InvestigationResult:
    investigation: Investigation
    report: InsightReport
    ledger: Ledger
    state: InvestigationState
    loop: LoopResult
    budget: BudgetSnapshot


class InvestigationController:
    def __init__(self, registry: AdapterRegistry, *, memory=None, gateway=None,
                 ledger_path=None) -> None:
        self.registry = registry
        self.engine = RecursiveLoopEngine(registry)
        # Optional Investigation Memory: supplies learned priors before the run and ingests the
        # run's strategy digest after it (doc 06 Phase 4). Never sees evidence content.
        self.memory = memory
        # Optional model gateway (doc 11): exposed to agents as ctx.llm. Default None keeps the
        # loop model-free (deterministic); agents that don't call it are unaffected.
        self.gateway = gateway
        # When set, the run's ledger is streamed to a durable JSONL file (doc 06 Phase 2).
        self.ledger_path = ledger_path

    def run(self, investigation: Investigation, *,
            ground_truth: dict[str, str] | None = None) -> InvestigationResult:
        ledger = Ledger(self.ledger_path)
        state = InvestigationState(investigation.investigation_id, ledger)
        governor = BudgetGovernor(investigation.config.budgets)

        ledger.append(
            investigation_id=investigation.investigation_id,
            iteration=0,
            type="investigation_start",
            actor="runtime",
            payload={"title": investigation.title, "objective": investigation.objective},
        )
        investigation.status = "running"

        # Learned priors are read-only and firewalled from evidence (doc 06 Phase 4).
        priors = None
        if self.memory is not None:
            from ...memory import MemoryPriors
            priors = MemoryPriors(self.memory)
        loop_result = self.engine.run(investigation, state, governor, priors=priors,
                                      gateway=self.gateway)

        ledger.append(
            investigation_id=investigation.investigation_id,
            iteration=investigation.current_iteration,
            type="report_emit",
            actor="runtime",
            payload={"report_id": loop_result.report.report_id,
                     "termination": loop_result.termination.reason},
        )
        ledger.verify()  # tamper-evident chain must hold

        result = InvestigationResult(
            investigation=investigation,
            report=loop_result.report,
            ledger=ledger,
            state=state,
            loop=loop_result,
            budget=governor.snapshot(),
        )

        # Learn strategy from the finished run (structure/metrics only, behind the firewall).
        if self.memory is not None:
            from ...memory import build_run_digest
            self.memory.ingest(build_run_digest(result, registry=self.registry,
                                                ground_truth=ground_truth))
        return result
