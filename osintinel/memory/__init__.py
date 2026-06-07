"""Investigation Memory (doc 01 §2.5, doc 06 Phase 4).

Learns strategy from completed runs and exposes priors to the planner/selector, behind a strict
evidence/strategy firewall: it reads run structure and metrics, never evidence content, and has
no path to mutate the ledger or graph.
"""

from .digest import build_run_digest
from .firewall import FirewallViolation, assert_strategy_only, verify_read_only
from .priors import MemoryPriors
from .store import AdapterStat, CalibrationRecord, InvestigationMemory, RunDigest

__all__ = [
    "AdapterStat",
    "CalibrationRecord",
    "FirewallViolation",
    "InvestigationMemory",
    "MemoryPriors",
    "RunDigest",
    "assert_strategy_only",
    "build_run_digest",
    "verify_read_only",
]
