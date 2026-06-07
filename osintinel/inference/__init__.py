"""Model & inference layer (doc 11).

A provider-agnostic, tier-routing gateway over a universal OpenAI-compatible client, so the
whole stack runs on **free, local-first** backends (Ollama / llama.cpp / LM Studio) or free
cloud tiers (Gemini / Groq / OpenRouter) — selected by *profile*, not code. Cost accounting,
ledger-recorded calls, and record/replay over the same cassette transport the adapters use.
"""

from .config import anthropic_available, build_gateway, gateway_status
from .gateway import Embedder, Provider, TieredGateway
from .profiles import DEFAULT_PROFILE, PROFILES, Profile, resolve_profile
from .types import ChatMessage, ChatRequest, EmbeddingResult, ModelResponse, Usage

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "DEFAULT_PROFILE",
    "Embedder",
    "EmbeddingResult",
    "ModelResponse",
    "PROFILES",
    "Profile",
    "Provider",
    "TieredGateway",
    "Usage",
    "anthropic_available",
    "build_gateway",
    "gateway_status",
    "resolve_profile",
]
