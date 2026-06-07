"""OpenAI-compatible chat + embedding provider (doc 11 §4) — the universal local/free path.

A single client for every endpoint that speaks the OpenAI Chat Completions / Embeddings API:
**Ollama** and **llama.cpp / LM Studio / vLLM** (local, free, private) and the free cloud tiers
**Google Gemini**, **Groq**, and **OpenRouter** (`:free` models). Configured purely by
``base_url`` + ``model`` + an optional API-key env var, so switching providers is config, not
code. A thin wrapper over the cassette ``HttpClient`` (stdlib HTTP, no new dependency), so it
records/replays like everything else; the API key rides a header and never enters the cassette.
"""

from __future__ import annotations

import json
import os

from ...adapters.transport import HttpClient
from ..types import ChatRequest, EmbeddingResult, ModelResponse, Usage, approx_tokens


def _bearer(key_env: str | None) -> dict[str, str]:
    token = os.environ.get(key_env) if key_env else None
    return {"authorization": f"Bearer {token}"} if token else {}


def _maybe_json(text: str) -> dict | None:
    s = text.strip()
    # tolerate models that fence JSON in ```json ... ```
    if s.startswith("```"):
        s = s.strip("`")
        s = s[4:] if s.lower().startswith("json") else s
        s = s.strip()
    if s.startswith("{"):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None
    return None


class OpenAICompatibleProvider:
    def __init__(self, http: HttpClient, model: str, base_url: str, *,
                 key_env: str | None = None, name: str = "openai-compatible") -> None:
        self.http = http
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.key_env = key_env
        self.name = name

    def chat(self, request: ChatRequest) -> ModelResponse:
        messages = ([{"role": "system", "content": request.system}] if request.system else []) \
            + [{"role": m.role, "content": m.content} for m in request.messages]
        body: dict = {"model": request.model or self.model, "messages": messages,
                      "max_tokens": request.max_tokens, "temperature": request.temperature,
                      "stream": False}
        if request.response_schema is not None:
            body["response_format"] = {"type": "json_object"}
        headers = {"content-type": "application/json", **_bearer(self.key_env)}
        raw = self.http.post_text(f"{self.base_url}/chat/completions",
                                  data=json.dumps(body, sort_keys=True), headers=headers)
        data = json.loads(raw)
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "") or ""
        usage = data.get("usage") or {}
        return ModelResponse(
            text=text, model=data.get("model", request.model or self.model),
            usage=Usage(input_tokens=usage.get("prompt_tokens", approx_tokens(str(messages))),
                        output_tokens=usage.get("completion_tokens", approx_tokens(text))),
            structured=_maybe_json(text), finish_reason=choice.get("finish_reason"))


class OpenAICompatibleEmbedder:
    def __init__(self, http: HttpClient, model: str, base_url: str, *,
                 key_env: str | None = None) -> None:
        self.http = http
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.key_env = key_env

    def embed(self, texts: list[str]) -> EmbeddingResult:
        headers = {"content-type": "application/json", **_bearer(self.key_env)}
        raw = self.http.post_text(f"{self.base_url}/embeddings",
                                  data=json.dumps({"model": self.model, "input": texts}),
                                  headers=headers)
        data = json.loads(raw)
        vectors = [row["embedding"] for row in data.get("data", [])]
        return EmbeddingResult(vectors=vectors, model=data.get("model", self.model),
                               dims=len(vectors[0]) if vectors else 0)
