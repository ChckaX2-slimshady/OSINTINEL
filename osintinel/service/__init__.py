"""Service layer — the front door to the engine (doc 10 rule 5: interfaces depend on a thin
service over the controller, not on internals)."""

from .investigation import (
    EvidenceInput,
    InvestigationSummary,
    autoresearch_investigation,
    run_investigation,
)
from .runstore import RunStore, persistence_enabled

__all__ = [
    "EvidenceInput",
    "InvestigationSummary",
    "RunStore",
    "autoresearch_investigation",
    "persistence_enabled",
    "run_investigation",
]
