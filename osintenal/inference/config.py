"""Gateway construction & model config (doc 11 §4–§5).

``build_gateway`` degrades gracefully: a live provider when a key is present *and* recording is
on; otherwise replay from a committed cassette if a directory is given; otherwise the
deterministic provider. The same call site therefore runs live, in recorded-replay, or fully
offline (the CI default).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ..adapters.transport import Cassette, HttpClient
from .gateway import TieredGateway
from .providers import (
    AnthropicProvider,
    DeterministicEmbedder,
    DeterministicProvider,
    HuggingFaceEmbedder,
    HuggingFaceProvider,
)

# Tier → model id (doc 08 §1; flagship = Anthropic, small/nano + embeddings = Hugging Face).
DEFAULT_TIER_MODELS = {
    "reason": "claude-opus-4-8",
    "large": "claude-opus-4-8",
    "small": "claude-sonnet-4-6",
    "task": "HuggingFaceH4/zephyr-7b-beta",
    "nano": "HuggingFaceH4/zephyr-7b-beta",
}
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Rough prices in USD per 1M tokens (input, output); refine in deployment config.
PRICES = {
    "claude-opus-4-8": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "HuggingFaceH4/zephyr-7b-beta": (0.1, 0.1),
    "_default": (0.5, 1.5),
}


def anthropic_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def huggingface_available() -> bool:
    return bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN"))


def _deterministic_gateway(governor, ledger, investigation_id) -> TieredGateway:
    det = DeterministicProvider()
    providers = {t: det for t in DEFAULT_TIER_MODELS}
    return TieredGateway(providers, embedder=DeterministicEmbedder(),
                         models=DEFAULT_TIER_MODELS, prices=PRICES, governor=governor,
                         ledger=ledger, investigation_id=investigation_id)


def build_gateway(*, cassette_dir: str | Path | None = None, record: bool | None = None,
                  governor=None, ledger=None, investigation_id: str = "inference",
                  force_deterministic: bool = False) -> TieredGateway:
    record = (os.environ.get("OSINTENAL_RECORD") == "1") if record is None else record

    # Deterministic default: no cassette directory and not recording (the offline/CI path).
    if force_deterministic or (cassette_dir is None and not record):
        return _deterministic_gateway(governor, ledger, investigation_id)

    base = Path(cassette_dir) if cassette_dir else Path(tempfile.mkdtemp())

    def http(name: str) -> HttpClient:
        return HttpClient(Cassette(base / f"{name}.json"), record=record)

    anthropic = AnthropicProvider(http("anthropic"), DEFAULT_TIER_MODELS["large"])
    hf_chat = HuggingFaceProvider(http("hf_chat"), DEFAULT_TIER_MODELS["task"])
    providers = {"reason": anthropic, "large": anthropic,
                 "small": hf_chat, "task": hf_chat, "nano": hf_chat}
    embedder = HuggingFaceEmbedder(http("hf_embed"), EMBED_MODEL)
    return TieredGateway(providers, embedder=embedder, models=DEFAULT_TIER_MODELS, prices=PRICES,
                         governor=governor, ledger=ledger, investigation_id=investigation_id)


def gateway_status() -> dict[str, object]:
    """Provider/key availability and tier→model mapping (for the CLI / diagnostics)."""
    return {
        "tier_models": dict(DEFAULT_TIER_MODELS),
        "embed_model": EMBED_MODEL,
        "anthropic_key": anthropic_available(),
        "huggingface_token": huggingface_available(),
        "record_mode": os.environ.get("OSINTENAL_RECORD") == "1",
    }
