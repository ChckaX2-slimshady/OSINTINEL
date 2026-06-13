"""Service layer — the front door to the engine (doc 10 rule 5: interfaces depend on a thin
service over the controller, not on internals)."""

from .diagnostics import Check, diagnostics_ok, run_diagnostics
from .investigation import (
    EvidenceInput,
    InvestigationSummary,
    autoresearch_investigation,
    run_investigation,
)
from .research import live_web_adapter, run_web_research
from .runstore import RunStore, persistence_enabled

__all__ = [
    "Check",
    "EvidenceInput",
    "InvestigationSummary",
    "RunStore",
    "autoresearch_investigation",
    "diagnostics_ok",
    "live_web_adapter",
    "persistence_enabled",
    "run_diagnostics",
    "run_investigation",
    "run_web_research",
]
