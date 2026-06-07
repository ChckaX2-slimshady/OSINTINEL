"""Anthropic Claude provider (doc 11 §4) — the flagship reasoning tier.

A thin wrapper over the cassette ``HttpClient`` (stdlib HTTP, no new dependency), so it inherits
record/replay: live when recording with a key, served from a cassette in CI. Supports an API
key (``ANTHROPIC_API_KEY``) or an OAuth bearer token (``ANTHROPIC_AUTH_TOKEN``). The cassette key
hashes only method+URL+body, so credentials in headers never enter recordings.
"""

from __future__ import annotations

import json
import os

from ...adapters.transport import HttpClient
from ..types import ChatRequest, ModelResponse, Usage

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


def auth_headers() -> dict[str, str]:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return {"x-api-key": os.environ["ANTHROPIC_API_KEY"]}
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return {"authorization": f"Bearer {os.environ['ANTHROPIC_AUTH_TOKEN']}"}
    return {}


def _maybe_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return None


class AnthropicProvider:
    def __init__(self, http: HttpClient, model: str) -> None:
        self.http = http
        self.model = model

    def chat(self, request: ChatRequest) -> ModelResponse:
        body = {
            "model": request.model or self.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.system:
            body["system"] = request.system
        headers = {"anthropic-version": API_VERSION, "content-type": "application/json",
                   **auth_headers()}
        raw = self.http.post_text(API_URL, data=json.dumps(body, sort_keys=True), headers=headers)
        data = json.loads(raw)
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
        usage = data.get("usage", {})
        return ModelResponse(
            text=text, model=data.get("model", self.model),
            usage=Usage(input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0)),
            structured=_maybe_json(text), finish_reason=data.get("stop_reason"))
