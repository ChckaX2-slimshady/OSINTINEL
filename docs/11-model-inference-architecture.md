# 11 — Model & Inference Architecture

> **Paradigm:** OSINTINEL is an **online, model-driven** system. It depends on live open-source
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

| Tier | Default backend (free) | Jobs | Agents |
|------|------------------------|------|--------|
| **`embed`** | **local Ollama** (`nomic-embed-text`) | semantic memory & retrieval; evidence dedup; **source-independence by near-duplicate detection**; reverse-image/text similarity; RAG over fetched corpora | Memory, Synthesis, Acquisition |
| **`task`** (`nano`/`small`) | **local Ollama** small model (`qwen2.5:3b`) | EXIF/caption/OCR interpretation; entity & claim extraction; **evidence→hypothesis relevance** (replaces the deterministic `_relevance_link` stand-ins); query formulation; confidence prose | Aggregation, Tool Selection, Acquisition, Confidence |
| **`reason`** (`large`) | **local Ollama** big model *or* a **free cloud tier** (Gemini/Groq/OpenRouter) | framing competing explanations; synthesis; adversarial challenge; meta-reasoning; speculation | Connections, Synthesis, Skeptic, Epistemology, Speculation |

> Backends are profile config, not code (§4b). The default operating profile is `ollama`
> (everything local & free); the recommended hybrid keeps `embed`+`task` local and routes only
> `reason` to a free cloud model for extra horsepower.

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

## 4. Providers — universal, free, local-first (zero new hard dependencies)

The primary backend is **one `OpenAICompatibleProvider` / `OpenAICompatibleEmbedder`**, because
Ollama, llama.cpp, LM Studio, vLLM, and the free cloud tiers (Gemini, Groq, OpenRouter) all
speak the OpenAI Chat Completions / Embeddings API. Switching providers is therefore *config,
not code*: a `base_url`, a `model`, and an optional key env var. Two provider-specific wrappers
(`AnthropicProvider`, `HuggingFaceProvider`) remain for those non-OpenAI shapes, and
`DeterministicProvider`/`DeterministicEmbedder` is the no-network default + CI double. All are
thin wrappers over the cassette `HttpClient` (stdlib HTTP) — **no new dependency**, full
record/replay, and the API key rides a header so it never enters a cassette.

### 4b. Profiles (`inference/profiles.py`)

A *profile* presets the three tiers onto an endpoint. The default is `deterministic`; selecting a
real profile is one env var. Every non-paid profile is **free**:

| Profile | reason / task | embed | cost | notes |
|---|---|---|---|---|
| **`ollama`** (recommended) | local Ollama (`qwen2.5:14b` / `3b`) | local `nomic-embed-text` | **$0, private** | fully local; pick the reason model to fit your VRAM |
| `gemini` | Gemini 2.0 Flash / Flash-Lite | `text-embedding-004` | free tier | key, no card |
| `groq` | Llama-3.3-70B / 3.1-8B | local Ollama | free tier | fast 70B; no native embeddings |
| `openrouter` | DeepSeek-R1 / Llama `:free` | local Ollama | free tier | rotating free models |
| `anthropic` / `huggingface` | Claude / HF models | — / MiniLM | paid / free-rl | optional |
| `deterministic` | hash-derived | bag-of-words | $0 | offline / CI default |

**The recommended hybrid (doc-optimal for cost *and* privacy):** run `ollama` for `embed`+`task`
(local, unlimited, evidence never leaves the machine) and route **only the reasoning tier** to a
free cloud profile via `OSINTINEL_REASON_PROFILE=gemini` (or `groq`/`openrouter`). Per-tier model
overrides: `OSINTINEL_{REASON,SMALL,TASK,EMBED}_MODEL`.

**Graceful degradation** (`config.py::build_gateway`): a live profile calls its endpoint (and
records to a cassette for later replay); `OSINTINEL_RECORD=0` forces replay from a committed
cassette; the `deterministic` profile needs neither network nor keys. The same code path runs
live-local, live-cloud, recorded-replay, or fully offline.

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
- **Decorrelation**: the Skeptic runs on a different model than Synthesis/Connections, so the
  challenge layer's errors are less correlated (doc 08 §1). It is a config knob —
  `OSINTINEL_SKEPTIC_PROFILE=<profile>` routes the Skeptic role to that profile's model via the
  gateway's per-role override (`role_providers`/`role_models`).

### 5a. Transport modes (online-first)

External I/O (adapters *and* model calls) shares one cassette transport with three modes, set by
`OSINTINEL_NET`:

| Mode | Behavior | Use |
|---|---|---|
| `replay` (default) | serve from cassette; error if missing | CI / offline / reproducible |
| `record` | serve from cassette if present, else fetch live and persist | build the recorded corpus |
| `live` | fetch every call, ignore cassette | online-first production |

Cassettes are therefore the **recorded test corpus**: record a golden run once
(`OSINTINEL_NET=record`), commit the cassettes, and CI replays them deterministically. The
default is `replay` (not `live`) so no environment depends on egress unless it opts in.

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

- **Local-first needs no key and no internet** beyond `localhost`: install [Ollama](https://ollama.com),
  `ollama pull qwen2.5:14b-instruct qwen2.5:3b-instruct nomic-embed-text`, then
  `OSINTINEL_INFERENCE_PROFILE=ollama`. Nothing leaves the machine.
- **Free cloud tiers** are environment variables only, never committed:
  `GEMINI_API_KEY` (Google AI Studio), `GROQ_API_KEY`, `OPENROUTER_API_KEY` — and the optional
  `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`, `HF_TOKEN`. Request **headers carry the key; the
  cassette key hashes only method+URL+body**, so recordings never leak credentials.
- **Network egress** to whichever endpoints you choose (and the OSINT sources) must be permitted
  by the deployment's network policy; for `ollama` only `localhost` is needed.
- **Lawful-use & ToS** (doc 05/07) are unchanged and apply to model providers too.

### 7a. Quick start (free)

```bash
# fully local & private (recommended)
ollama serve &
ollama pull qwen2.5:14b-instruct qwen2.5:3b-instruct nomic-embed-text
export OSINTINEL_INFERENCE_PROFILE=ollama

# or: local bulk + heavier free-cloud reasoning (one extra knob)
export OSINTINEL_INFERENCE_PROFILE=ollama
export OSINTINEL_REASON_PROFILE=gemini GEMINI_API_KEY=...

osintinel models           # shows the active routing
```

## 8. Rollout (doc 06 placement)

Introduced as **Phase M (Model Integration)**, slotted before Phase 8 (Self-Improvement), which
depends on it for calibration of model-produced confidence:

1. **Gateway foundation** — ports, providers (deterministic + Anthropic + HF), record/replay,
   cost, the `model_call` ledger event, `osintinel models`. *(this milestone)*
2. **Wire agents tier-by-tier** — `task` first (relevance linking, extraction, query
   formulation), then `embed` (Memory/dedup/independence), then `reason` (Connections, Synthesis,
   Skeptic, Epistemology) — each behind the gateway, each recorded for replay.
3. **Online-first defaults** — adapters live by default; cassettes become the test corpus
   (record live → replay in CI).
