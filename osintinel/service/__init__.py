"""Service layer — the front door to the engine (doc 10 rule 5: interfaces depend on a thin
service over the controller, not on internals)."""

from .investigation import (
    EvidenceInput,
    InvestigationSummary,
    autoresearch_investigation,
    run_investigation,
)

__all__ = [
    "EvidenceInput",
    "InvestigationSummary",
    "autoresearch_investigation",
    "run_investigation",
]
