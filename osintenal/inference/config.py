"""Gateway construction & model config (doc 11 §4–§5).

``build_gateway`` assembles a tier-routed gateway from a *profile* (doc 11): ``deterministic`` by
default (no network, CI), or a free/local profile (Ollama, Gemini, Groq, OpenRouter, …) selected
via ``OSINTENAL_INFERENCE_PROFILE``. Selecting a live profile implies live calls (which also
record to a cassette for later offline replay) unless ``OSINTENAL_RECORD=0``. A second knob,
``OSINTENAL_REASON_PROFILE``, routes *only* the reasoning tier to a different profile — the
local-embeddings + free-cloud-reasoning hybrid (doc 11 §2).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ..adapters.transport import Cassette, HttpClient
from .gateway import Provider, TieredGateway
from .profiles import Profile, resolve_profile
from .providers import (
    AnthropicProvider,
    DeterministicEmbedder,
    DeterministicProvider,
    HuggingFaceEmbedder,
    HuggingFaceProvider,
)
from .providers.openai_compat import OpenAICompatibleEmbedder, OpenAICompatibleProvider

# Prices are $0 for the local/free profiles; the Budget Governor still tracks tokens + latency.
PRICES = {
    "claude-opus-4-8": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "_default": (0.0, 0.0),
}

_TIER_TO_MODEL_ATTR = {"reason": "reason_model", "large": "reason_model",
                       "small": "small_model", "task": "task_model", "nano": "task_model"}


def anthropic_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _record_default(record: bool | None, profile_name: str) -> bool:
    if record is not None:
        return record
    if "OSINTENAL_RECORD" in os.environ:
        return os.environ["OSINTENAL_RECORD"] == "1"
    return profile_name != "deterministic"  # selecting a live profile implies live calls


def _deterministic_gateway(governor, ledger, investigation_id) -> TieredGateway:
    det = DeterministicProvider()
    providers = {t: det for t in ("reason", "large", "small", "task", "nano")}
    return TieredGateway(providers, embedder=DeterministicEmbedder(), prices=PRICES,
                         governor=governor, ledger=ledger, investigation_id=investigation_id,
                         models={t: "deterministic-1" for t in providers})


def _chat_provider(profile: Profile, model: str, http: HttpClient) -> Provider:
    if profile.kind == "anthropic":
        return AnthropicProvider(http, model)
    if profile.kind == "huggingface":
        return HuggingFaceProvider(http, model)
    return OpenAICompatibleProvider(http, model, profile.base_url, key_env=profile.key_env,
                                    name=profile.name)


def build_gateway(*, profile: str | None = None, cassette_dir: str | Path | None = None,
                  record: bool | None = None, governor=None, ledger=None,
                  investigation_id: str = "inference") -> TieredGateway:
    p = resolve_profile(profile)
    if p.kind == "deterministic":
        return _deterministic_gateway(governor, ledger, investigation_id)

    record = _record_default(record, p.name)
    base = Path(cassette_dir) if cassette_dir else Path(tempfile.mkdtemp())

    def http(name: str) -> HttpClient:
        return HttpClient(Cassette(base / f"{name}.json"), record=record)

    # one HTTP client per backend host is enough; tiers differ only by model in the body
    chat_http = http(p.name)
    providers: dict[str, Provider] = {}
    models: dict[str, str] = {}
    for tier, attr in _TIER_TO_MODEL_ATTR.items():
        model = getattr(p, attr)
        providers[tier] = _chat_provider(p, model, chat_http)
        models[tier] = model

    # Hybrid: route only the reasoning tier to a different (e.g. free-cloud) profile.
    reason_override = os.environ.get("OSINTENAL_REASON_PROFILE")
    if reason_override:
        rp = resolve_profile(reason_override)
        rhttp = http(f"{rp.name}_reason")
        for tier in ("reason", "large"):
            providers[tier] = _chat_provider(rp, rp.reason_model, rhttp)
            models[tier] = rp.reason_model

    # embedder
    if p.embed_kind == "huggingface":
        embedder = HuggingFaceEmbedder(http("hf_embed"), p.embed_model)
    elif p.embed_kind == "deterministic":
        embedder = DeterministicEmbedder()
    else:
        embedder = OpenAICompatibleEmbedder(http("embed"), p.embed_model, p.embed_base_url,
                                            key_env=p.embed_key_env)

    return TieredGateway(providers, embedder=embedder, models=models, prices=PRICES,
                         governor=governor, ledger=ledger, investigation_id=investigation_id)


def gateway_status(profile: str | None = None) -> dict[str, object]:
    """Active profile, per-tier routing, key presence, and mode (for the CLI / diagnostics)."""
    p = resolve_profile(profile)
    return {
        "profile": p.name,
        "kind": p.kind,
        "local": p.local,
        "free": p.free,
        "note": p.note,
        "base_url": p.base_url,
        "tier_models": {"reason": p.reason_model, "small": p.small_model, "task": p.task_model},
        "embed": {"kind": p.embed_kind, "model": p.embed_model, "base_url": p.embed_base_url},
        "key_env": p.key_env,
        "key_present": bool(os.environ.get(p.key_env)) if p.key_env else True,
        "reason_override": os.environ.get("OSINTENAL_REASON_PROFILE"),
        "record_mode": os.environ.get("OSINTENAL_RECORD"),
    }
