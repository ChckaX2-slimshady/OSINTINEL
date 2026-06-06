"""Deterministic, no-network provider + embedder (doc 11 §4).

The default when no API keys are present and the test double for CI: reproducible responses and
bag-of-words embeddings, so the whole system runs offline and deterministically without a
provider. Real reasoning quality comes from the live providers; this keeps the seam exercised.
"""

from __future__ import annotations

import hashlib
import math
import re

from ..types import ChatRequest, EmbeddingResult, ModelResponse, Usage, approx_tokens

_WORD = re.compile(r"[a-z0-9]+")


def _canonical(request: ChatRequest) -> str:
    msgs = "|".join(f"{m.role}:{m.content}" for m in request.messages)
    return f"{request.tier}/{request.role}/{request.system or ''}/{msgs}"


class DeterministicProvider:
    """Echoes a stable, hash-derived response — identical input → identical output."""

    def __init__(self, model: str = "deterministic-1") -> None:
        self.model = model

    def chat(self, request: ChatRequest) -> ModelResponse:
        digest = hashlib.sha256(_canonical(request).encode("utf-8")).hexdigest()
        text = f"[{request.role}@{request.tier}] deterministic response {digest[:16]}"
        in_tokens = approx_tokens(_canonical(request))
        return ModelResponse(
            text=text, model=self.model,
            usage=Usage(input_tokens=in_tokens, output_tokens=approx_tokens(text)),
            structured={"role": request.role, "tier": request.tier, "digest": digest[:16]},
            finish_reason="stop")


class DeterministicEmbedder:
    """Hashing bag-of-words embeddings: reproducible and similarity-meaningful (token overlap)."""

    def __init__(self, dims: int = 64, model: str = "det-embed-64") -> None:
        self.dims = dims
        self.model = model

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        for tok in _WORD.findall(text.lower()):
            idx = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16) % self.dims
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [round(v / norm, 6) for v in vec]

    def embed(self, texts: list[str]) -> EmbeddingResult:
        return EmbeddingResult(vectors=[self._vector(t) for t in texts], model=self.model,
                               dims=self.dims)
