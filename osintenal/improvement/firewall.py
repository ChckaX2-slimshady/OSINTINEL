"""Self-improvement firewall audit (doc 06 Phase 8 exit criterion, doc 07).

Phase 8 may improve *strategy* — it must never rewrite evidentiary history. This reuses the
Phase 4 firewall scan to prove a self-improvement report carries no evidence content, and adds
an audit that wraps any improvement action and verifies the run's ledger (hash chain) and every
hypothesis' confidence history are byte-for-byte unchanged by it.
"""

from __future__ import annotations

from typing import Callable

from ..memory.firewall import FirewallViolation, _scan
from .tuning import SelfImprovementReport


def assert_strategy_artifacts_only(report: SelfImprovementReport) -> None:
    """Reject a report that smuggles any evidence-content key (reuses the memory firewall scan)."""
    _scan(report.model_dump())


def _confidence_snapshot(state) -> dict:
    return {h.hypothesis_id: [(c.iteration, c.confidence) for c in h.confidence_history]
            for h in state.hypotheses.values()}


def audit_no_evidence_mutation(result, action: Callable[[], object]) -> object:
    """Run ``action`` (a self-improvement step) and prove it touched no evidentiary history:
    the ledger still verifies and confidence histories are unchanged."""
    before_chain = result.ledger.verify()
    before_conf = _confidence_snapshot(result.state)
    before_events = len(result.ledger)

    out = action()

    if not (before_chain and result.ledger.verify()):
        raise FirewallViolation("ledger hash chain altered by self-improvement")
    if len(result.ledger) != before_events:
        raise FirewallViolation("self-improvement appended to the run ledger")
    if _confidence_snapshot(result.state) != before_conf:
        raise FirewallViolation("self-improvement mutated recorded confidence history")
    return out
