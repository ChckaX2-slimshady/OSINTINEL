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
from ..schemas import InsightReport, Investigation
from ..state import InvestigationState
from .loop import LoopResult, RecursiveLoopEngine


@dataclass
class InvestigationResult:
    investigation: Investigation
    report: InsightReport
    ledger: Ledger
    state: InvestigationState
    loop: LoopResult


class InvestigationController:
    def __init__(self, registry: AdapterRegistry, *, ledger_path=None) -> None:
        self.registry = registry
        self.engine = RecursiveLoopEngine(registry)
        # When set, the run's ledger is streamed to a durable JSONL file (doc 06 Phase 2).
        self.ledger_path = ledger_path

    def run(self, investigation: Investigation) -> InvestigationResult:
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

        loop_result = self.engine.run(investigation, state, governor)

        ledger.append(
            investigation_id=investigation.investigation_id,
            iteration=investigation.current_iteration,
            type="report_emit",
            actor="runtime",
            payload={"report_id": loop_result.report.report_id,
                     "termination": loop_result.termination.reason},
        )
        ledger.verify()  # tamper-evident chain must hold

        return InvestigationResult(
            investigation=investigation,
            report=loop_result.report,
            ledger=ledger,
            state=state,
            loop=loop_result,
        )
