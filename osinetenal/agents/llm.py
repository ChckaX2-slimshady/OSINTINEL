"""LLM client port (doc 08 §1).

Phase 1 agents reason deterministically and do not require a model, which is what makes
the loop runnable and replayable with no API key. This port is the seam where real models
plug in for later phases: an ``AnthropicLLMClient`` (model-tier routed, prompt-cached,
ledger-recorded) can be supplied without changing any agent contract. A
``DeterministicLLMClient`` is provided so tests and offline runs are fully reproducible.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, *, tier: str, role: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a structured response for an agent role at a model tier."""
        ...


class DeterministicLLMClient:
    """A no-network client that echoes structured, reproducible responses.

    Phase 1 agents do not depend on this for their core logic; it exists so the seam is
    real and so future LLM-backed agents can be exercised in replay mode (doc 09).
    """

    def complete(self, *, tier: str, role: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"role": role, "tier": tier, "echo": payload}
