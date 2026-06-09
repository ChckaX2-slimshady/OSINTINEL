"""Hugging Face providers (doc 11 §4) — embeddings + small/nano specialized tasks.

Thin wrappers over the cassette ``HttpClient`` against the HF Inference API (``HF_TOKEN``), so
they record/replay like everything else. Models are discoverable via the Hugging Face MCP.
"""

from __future__ import annotations

import json
import os

from ...adapters.transport import HttpClient
from ..types import ChatRequest, EmbeddingResult, ModelResponse, Usage, approx_tokens

FEATURE_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/{model}"
TEXTGEN_URL = "https://api-inference.huggingface.co/models/{model}"
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def hf_headers() -> dict[str, str]:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
    return {"authorization": f"Bearer {token}", "content-type": "application/json"} if token \
        else {"content-type": "application/json"}


class HuggingFaceEmbedder:
    def __init__(self, http: HttpClient, model: str = DEFAULT_EMBED_MODEL) -> None:
        self.http = http
        self.model = model

    def embed(self, texts: list[str]) -> EmbeddingResult:
        raw = self.http.post_text(FEATURE_URL.format(model=self.model),
                                  data=json.dumps({"inputs": texts}), headers=hf_headers())
        try:
            vectors = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return EmbeddingResult(vectors=[], model=self.model, dims=0)
        if vectors and isinstance(vectors[0], (int, float)):  # single-text APIs return one vector
            vectors = [vectors]
        return EmbeddingResult(vectors=vectors, model=self.model,
                               dims=len(vectors[0]) if vectors else 0)


class HuggingFaceProvider:
    """Small/nano task models via HF text-generation."""

    def __init__(self, http: HttpClient, model: str) -> None:
        self.http = http
        self.model = model

    def chat(self, request: ChatRequest) -> ModelResponse:
        prompt = "\n".join(
            ([request.system] if request.system else []) + [m.content for m in request.messages])
        body = {"inputs": prompt,
                "parameters": {"max_new_tokens": request.max_tokens,
                               "temperature": max(request.temperature, 0.01),
                               "return_full_text": False}}
        raw = self.http.post_text(TEXTGEN_URL.format(model=request.model or self.model),
                                  data=json.dumps(body), headers=hf_headers())
        try:
            data = json.loads(raw)
            text = (data[0].get("generated_text", "") if isinstance(data, list) and data
                    else data.get("generated_text", "") if isinstance(data, dict) else "")
        except (json.JSONDecodeError, ValueError, AttributeError, IndexError, KeyError):
            text = ""  # garbage / empty / error body → degrade to deterministic floor
        return ModelResponse(
            text=text, model=request.model or self.model,
            usage=Usage(input_tokens=approx_tokens(prompt), output_tokens=approx_tokens(text)),
            finish_reason="stop")
