"""Common agent context (doc 02 "Common Agent Contract").

Phase 1 agents are deterministic: their reasoning is computed from state, which keeps the
loop runnable and replayable offline. Each agent receives an ``AgentContext`` giving
read access to investigation state plus a provenance-stamping helper, and returns typed
objects that the runtime persists. Agents never mutate the graph or call each other
directly (doc 01 §3). An optional ``LLMClient`` is available for later enrichment.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..adapters import AdapterRegistry
from ..core.budget import BudgetGovernor
from ..core.schemas import AcquisitionMethod, AgentName, Investigation, Provenance
from ..core.state import InvestigationState
from .llm import LLMClient


@dataclass
class AgentContext:
    investigation: Investigation
    state: InvestigationState
    iteration: int
    governor: BudgetGovernor
    registry: AdapterRegistry
    llm: LLMClient | None = None

    def provenance(
        self,
        agent: AgentName,
        *,
        method: AcquisitionMethod,
        confidence: float = 1.0,
        source: str = "internal",
        tool: str | None = None,
        derived_from: list[str] | None = None,
        license_note: str | None = None,
    ) -> Provenance:
        return Provenance(
            source=source,
            acquisition_method=method,
            agent_responsible=agent,
            confidence=confidence,
            tool_used=tool,
            investigation_id=self.investigation.investigation_id,
            derived_from=derived_from or [],
            license_note=license_note,
        )
