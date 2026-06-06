"""Read-only learned-strategy priors exposed to the planner and tool selector (doc 05 §3).

``MemoryPriors`` is the firewall-safe face of Investigation Memory: it satisfies the agents'
``StrategyPriors`` port with numbers and orderings only — no ledger/state handle, no mutator.
This is what lets Memory bias *strategy* (which adapter, which capability first) without any
ability to touch evidentiary history.
"""

from __future__ import annotations

from .store import InvestigationMemory


class MemoryPriors:
    def __init__(self, memory: InvestigationMemory) -> None:
        # Deliberately the ONLY reference held; exposes no mutation method (see firewall).
        self._memory = memory

    def adapter_effectiveness(self, adapter_id: str, default: float = 0.5) -> float:
        return self._memory.adapter_effectiveness(adapter_id, default=default)

    def capability_score(self, capability: str, default: float = 0.5) -> float:
        return self._memory.capability_effectiveness(capability, default=default)

    def ranked_capabilities(self, domain: str | None, fallback: list[str]) -> list[str]:
        """The candidate capabilities reordered so the historically most effective come first."""
        return sorted(fallback, key=lambda c: self.capability_score(c), reverse=True)

    def expected_cost(self, capability: str, default: float = 0.0) -> float:
        return self._memory.expected_cost(capability, default=default)
