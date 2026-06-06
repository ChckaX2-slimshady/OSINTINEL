"""Provider-agnostic request/response types for the inference gateway (doc 11 §3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier: str
    role: str                          # the agent role making the call (for prompts/provenance)
    model: str | None = None           # resolved by the gateway from the tier
    system: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    max_tokens: int = 1024
    temperature: float = 0.0           # default 0 → reproducible / replayable
    response_schema: dict | None = None  # optional JSON schema for structured output


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    model: str
    usage: Usage = Field(default_factory=Usage)
    structured: dict | None = None
    finish_reason: str | None = None


class EmbeddingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vectors: list[list[float]]
    model: str
    dims: int = 0


def approx_tokens(text: str) -> int:
    """A cheap, deterministic token estimate (~4 chars/token) for offline accounting."""
    return max(1, len(text) // 4)
