# 11 — Model & Inference Architecture

> **Paradigm:** OSINTENAL is an **online, model-driven** system. It depends on live open-source
> data (the adapters, doc 05) and on a tiered ensemble of models for reasoning. The earlier
> "runs fully offline with no model" property is retained **only as the test/replay mode** — it
> is how CI stays deterministic and free, not how the product operates.

This document defines how models enter the system: the tiers, the provider-agnostic gateway,
embeddings, how nondeterministic/paid calls remain auditable and replayable, and how secrets and
network are handled. It complements doc 08 (which pins the tiers and the deterministic-first
principle) and reuses the ports already in the codebase (`agents/llm.py`, the cassette transport
in `adapters/transport.py`, the ledger, the Budget Governor).

## 1. Why this fits the existing architecture

Three seams already anticipated models, so this is a re-defaulting plus three net-new pieces,
not a rewrite:

- **`LLMClient` port** (`agents/llm.py`): agents accept a model via `complete(tier, role,
  payload)` without contract changes.
- **doc 08 §1 tiering**: `large → claude-opus-4-8`, `small → sonnet`, `nano → haiku`, with
  "model diversity for decorrelation" (Skeptic on a different model than Synthesis).
- **Cassette transport** (`adapters/transport.py`): already records/replays live HTTP. Model
  calls are just HTTPS POSTs, so they ride the *same* VCR mechanism.

Net-new: (1) embeddings as a first-class tier, (2) the `InferenceGateway`/`Embedder` ports with
tier routing + cost + recording, (3) online-first defaults with model-call replay.

## 2. The three tiers

| Tier | Default provider/model | Jobs | Agents |
|------|------------------------|------|--------|
| **`embed`** | Hugging Face (open embedding model) | semantic memory & retrieval; evidence dedup; **source-independence by near-duplicate detection**; reverse-image/text similarity; RAG over fetched corpora | Memory, Synthesis, Acquisition |
| **`task`** (`nano`/`small`) | Hugging Face small models; provider small tier | EXIF/caption/OCR interpretation; entity & claim extraction; **evidence→hypothesis relevance** (replaces the deterministic `_relevance_link` stand-ins); query formulation; confidence prose | Aggregation, Tool Selection, Acquisition, Confidence |
| **`reason`** (`large`) | Anthropic Claude (Opus/Sonnet) via API key or OAuth | framing competing explanations; synthesis; adversarial challenge; meta-reasoning; speculation | Connections, Synthesis, Skeptic, Epistemology, Speculation |

The **deterministic-first principle (doc 08 §2) still holds**: all arithmetic (confidence
factors, normalization, info-gain ranking, graph queries) stays in code; models supply judgment
and prose, never the numbers.

## 3. The `InferenceGateway` and `Embedder` ports

```python
class Provider(Protocol):              # one model backend
    def chat(self, request: ChatRequest) -> ModelResponse: ...

class Embedder(Protocol):
    def embed(self, texts: list[str]) -> EmbeddingResult: ...

class InferenceGateway(Protocol):      # tier router; LLMClient-compatible
    def complete(self, *, tier: str, role: str, payload: dict) -> dict: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

`TieredGateway` maps each tier to a `Provider`, and on every call it:
1. builds a `ChatRequest` (system prompt for the agent role + task-scoped context, doc 08 §3);
2. routes to the tier's provider;
3. **charges the Budget Governor** (tokens + a per-model price table → money);
4. **records a lean `model_call` ledger event** (`tier, role, provider, model, prompt_hash,
   response_hash, input/output tokens`) — never the full prompt/response bytes, which live in
   the cassette/CAS (mirrors the `raw_response` pattern, doc 05 §5.7);
5. returns a structured dict validated against the agent's expected pydantic schema.

## 4. Providers (zero new hard dependencies)

All live providers are thin wrappers over the existing cassette `HttpClient` (stdlib `urllib`),
so they inherit record/replay and add **no new dependency**:

- **`AnthropicProvider`** — POSTs the Messages API; supports an API key (`ANTHROPIC_API_KEY`) or
  an OAuth bearer token. Structured output via tool/JSON mode.
- **`HuggingFaceProvider` / `HuggingFaceEmbedder`** — HF Inference API (`HF_TOKEN`); models
  discoverable via the Hugging Face MCP. Open embedding + small task models.
- **`DeterministicProvider` / `DeterministicEmbedder`** — no network; reproducible hash-derived
  responses and bag-of-words embeddings. The **default** when no keys are present and the test
  double for CI.

**Graceful degradation** (`inference/config.py::build_gateway`): live provider when a key is
present *and* recording is enabled; else replay from a committed cassette if one exists; else the
deterministic provider. So the same code runs live, in recorded-replay, or fully offline.

## 5. Determinism, replay & cost (the guarantees that now matter more)

- **Replay survives nondeterminism** by recording model I/O: temperature 0 where possible,
  responses cached in a model cassette keyed by a canonical request hash. A run replays from
  recorded responses with no provider calls — doc 10's `ledger/replay.py # replay … LLM calls`.
- **Auditability**: every model call is a ledger event with model id, prompt hash, sampling
  params, and response hash; the report's reasoning chain can cite which model produced which
  step.
- **Cost control**: the Budget Governor already tracks tokens/money/requests; the gateway feeds
  it real usage, and the planner/Memory priors (doc 06 Phase 4) can learn cheap-but-effective
  tier/model choices.
- **Decorrelation**: the Skeptic runs on a different model (or distinct prompt+sampling) than
  Synthesis, so the challenge layer's errors are less correlated (doc 08 §1).

## 6. Embeddings: semantic memory, dedup & true source independence

Embeddings unlock capabilities the deterministic loop only approximated:

- **Source independence** is currently grouped by a declared `independence_group` string. With
  embeddings we additionally detect **near-duplicate content across nominally-independent
  sources** (syndication, copy-paste) and *collapse* their independence — a real OSINT failure
  mode the Confidence factor should not be fooled by.
- **Evidence dedup & clustering**, **semantic retrieval** over large fetched corpora (RAG), and
  **reverse-image/text similarity** (`media.similarity`).
- **Firewall (doc 06 Phase 4) preserved**: per-investigation evidence embeddings are fine;
  cross-investigation Memory stays strategy-only and never ingests evidence vectors.

## 7. Secrets & network (operator responsibilities)

- **Network egress** to the inference provider and OSINT endpoints must be permitted by the
  deployment's network policy. In the hosted sandbox this is the environment's network policy;
  in production it is ordinary outbound HTTPS.
- **Secrets** are environment variables only, never committed: `ANTHROPIC_API_KEY` *or*
  `ANTHROPIC_AUTH_TOKEN` (OAuth), and `HF_TOKEN`. Request **headers carry the key; the cassette
  key hashes only method+URL+body**, so recordings never leak credentials.
- **Lawful-use & ToS** (doc 05/07) are unchanged and apply to model providers too.

## 8. Rollout (doc 06 placement)

Introduced as **Phase M (Model Integration)**, slotted before Phase 8 (Self-Improvement), which
depends on it for calibration of model-produced confidence:

1. **Gateway foundation** — ports, providers (deterministic + Anthropic + HF), record/replay,
   cost, the `model_call` ledger event, `osintenal models`. *(this milestone)*
2. **Wire agents tier-by-tier** — `task` first (relevance linking, extraction, query
   formulation), then `embed` (Memory/dedup/independence), then `reason` (Connections, Synthesis,
   Skeptic, Epistemology) — each behind the gateway, each recorded for replay.
3. **Online-first defaults** — adapters live by default; cassettes become the test corpus
   (record live → replay in CI).
