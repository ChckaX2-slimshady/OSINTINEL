"""Model & inference layer (doc 11).

A provider-agnostic, tier-routing gateway (flagship Anthropic reasoning · Hugging Face
embeddings + small models) with cost accounting, ledger-recorded calls, and record/replay over
the same cassette transport the adapters use — so model I/O is auditable and reproducible.
"""

from .config import (
    DEFAULT_TIER_MODELS,
    EMBED_MODEL,
    anthropic_available,
    build_gateway,
    gateway_status,
    huggingface_available,
)
from .gateway import Embedder, Provider, TieredGateway
from .types import ChatMessage, ChatRequest, EmbeddingResult, ModelResponse, Usage

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "DEFAULT_TIER_MODELS",
    "EMBED_MODEL",
    "Embedder",
    "EmbeddingResult",
    "ModelResponse",
    "Provider",
    "TieredGateway",
    "Usage",
    "anthropic_available",
    "build_gateway",
    "gateway_status",
    "huggingface_available",
]
