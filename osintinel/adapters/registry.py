"""Adapter Registry (doc 05 §3). Maps capability -> adapters with cost/effectiveness priors."""

from __future__ import annotations

from .base import Adapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}
        # effectiveness priors (seeded; refined by Investigation Memory in Phase 4)
        self._effectiveness: dict[str, float] = {}

    def register(self, adapter: Adapter, effectiveness: float = 0.5) -> None:
        self._adapters[adapter.id] = adapter
        self._effectiveness[adapter.id] = effectiveness

    def get(self, adapter_id: str) -> Adapter:
        return self._adapters[adapter_id]

    def by_capability(self, tag: str) -> list[Adapter]:
        return [a for a in self._adapters.values() if tag in a.capabilities]

    def effectiveness(self, adapter_id: str) -> float:
        return self._effectiveness.get(adapter_id, 0.5)

    def all(self) -> list[Adapter]:
        return list(self._adapters.values())
