"""The tier-routing inference gateway (doc 11 §3).

Routes each agent call to the provider for its tier, charges the Budget Governor with real
usage, and records a lean ``model_call`` ledger event (hashes + token counts — never the prompt
bytes, which live in the cassette/CAS). ``complete`` is LLMClient-compatible, so it drops into
``AgentContext.llm`` without changing any agent contract.
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol, runtime_checkable

from .types import ChatMessage, ChatRequest, EmbeddingResult, ModelResponse


@runtime_checkable
class Provider(Protocol):
    def chat(self, request: ChatRequest) -> ModelResponse: ...


@runtime_checkable
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> EmbeddingResult: ...


# Tier fallback: if a tier has no provider, fall back along the ladder.
_FALLBACK = {"reason": "large", "large": "small", "small": "nano", "nano": "task", "task": "small"}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class TieredGateway:
    """Maps tiers → providers; accounts cost and records every call. LLMClient-compatible."""

    def __init__(self, providers: dict[str, Provider], *, embedder: Embedder | None = None,
                 models: dict[str, str] | None = None, prices: dict | None = None,
                 governor=None, ledger=None, investigation_id: str = "inference") -> None:
        self.providers = providers
        self.embedder = embedder
        self.models = models or {}
        self.prices = prices or {}
        self._governor = governor
        self._ledger = ledger
        self.investigation_id = investigation_id
        self.iteration = 0
        self.calls: list[dict] = []  # in-memory audit trail (also used by tests)

    # -- routing -----------------------------------------------------------
    def _provider(self, tier: str) -> Provider:
        seen = set()
        t = tier
        while t and t not in seen:
            if t in self.providers:
                return self.providers[t]
            seen.add(t)
            t = _FALLBACK.get(t)
        if self.providers:
            return next(iter(self.providers.values()))
        raise RuntimeError("no providers configured")

    def _build_request(self, tier: str, role: str, payload: dict) -> ChatRequest:
        if payload.get("messages"):
            messages = [ChatMessage(**m) for m in payload["messages"]]
        else:
            messages = [ChatMessage(role="user", content=str(payload.get("prompt", "")))]
        return ChatRequest(
            tier=tier, role=role, model=payload.get("model") or self.models.get(tier),
            system=payload.get("system"), messages=messages,
            max_tokens=int(payload.get("max_tokens", 1024)),
            temperature=float(payload.get("temperature", 0.0)),
            response_schema=payload.get("response_schema"))

    # -- public (LLMClient-compatible) -------------------------------------
    def complete(self, *, tier: str, role: str, payload: dict) -> dict[str, Any]:
        request = self._build_request(tier, role, payload)
        response = self._provider(tier).chat(request)
        self._account(tier, role, request, response)
        return {
            "text": response.text, "structured": response.structured, "model": response.model,
            "tier": tier, "role": role,
            "usage": {"input_tokens": response.usage.input_tokens,
                      "output_tokens": response.usage.output_tokens},
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.embedder is None:
            raise RuntimeError("no embedder configured")
        result = self.embedder.embed(texts)
        tokens = sum(len(t) // 4 + 1 for t in texts)
        self._charge(result.model, input_tokens=tokens, output_tokens=0)
        self.calls.append({"kind": "embed", "model": result.model, "n": len(texts),
                           "dims": result.dims, "input_tokens": tokens})
        return result.vectors

    # -- accounting + recording -------------------------------------------
    def _price(self, model: str) -> tuple[float, float]:
        return self.prices.get(model, self.prices.get("_default", (0.0, 0.0)))

    def _charge(self, model: str, *, input_tokens: int, output_tokens: int) -> float:
        pin, pout = self._price(model)
        money = (input_tokens * pin + output_tokens * pout) / 1_000_000
        if self._governor is not None:
            self._governor.charge(tokens=input_tokens + output_tokens, money_usd=money,
                                  requests=1)
        return round(money, 6)

    def _account(self, tier: str, role: str, request: ChatRequest,
                 response: ModelResponse) -> None:
        money = self._charge(response.model, input_tokens=response.usage.input_tokens,
                             output_tokens=response.usage.output_tokens)
        prompt_hash = _hash((request.system or "") + "|".join(m.content for m in request.messages))
        record = {
            "kind": "chat", "tier": tier, "role": role, "model": response.model,
            "prompt_hash": prompt_hash, "response_hash": _hash(response.text),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens, "money_usd": money,
        }
        self.calls.append(record)
        # lean ledger event: references only, never prompt/response bytes (doc 11 §3)
        if self._ledger is not None:
            self._ledger.append(investigation_id=self.investigation_id, iteration=self.iteration,
                                type="model_call", actor=role, payload=record)

    # -- cost summary ------------------------------------------------------
    def cost_summary(self) -> dict[str, float | int]:
        chat = [c for c in self.calls if c.get("kind") == "chat"]
        return {
            "calls": len(self.calls),
            "input_tokens": sum(c.get("input_tokens", 0) for c in self.calls),
            "output_tokens": sum(c.get("output_tokens", 0) for c in chat),
            "money_usd": round(sum(c.get("money_usd", 0.0) for c in chat), 6),
        }
