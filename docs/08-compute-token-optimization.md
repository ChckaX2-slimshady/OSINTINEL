# 08 — Compute & Token Optimization Plan

A recursive multi-agent loop is intrinsically token-hungry. This plan keeps OSINTINEL
*affordable and fast* without compromising the epistemic guarantees. The governing idea:
**spend tokens where reasoning quality changes the outcome; spend deterministic code
everywhere else.**

## 1. Model Tiering & Routing

Three logical tiers; the Budget Governor routes each agent call to the cheapest tier that
preserves quality. Concrete model ids are pinned in config and recorded per call in the
ledger.

| Tier | Use | Example role |
|------|-----|--------------|
| `nano` | trivial classification, extraction, routing | normalize messy payloads, capability matching |
| `small` | structured reasoning with tight scope | Aggregation orchestration, Tool Selection, Confidence explanation |
| `large` | core open-ended reasoning | Connections, Synthesis, Skeptic, Epistemology, Speculation |

Defaults (overridable in config), using current Claude family:
- `large` → `claude-opus-4-8` (deep reasoning, Skeptic/Synthesis/Connections)
- `small` → `claude-sonnet-4-6`
- `nano`  → `claude-haiku-4-5-20251001`

**Model diversity for decorrelation:** the Skeptic should run on a *different* model (or
distinct prompt+sampling) from Synthesis so their errors are less correlated — a cheap way to
make the challenge layer genuinely adversarial.

## 2. Deterministic-First Principle

Anything that can be computed without an LLM, is:
- Confidence factor arithmetic, set normalization, info-gain/cost ranking (the LLM only writes
  the *explanation*, not the numbers).
- Capability→adapter matching, dedup, idempotency keys, hash chaining.
- Graph queries for diversity / independence / monoculture / contradiction clusters.

This both cuts cost and improves auditability (numbers are reproducible).

## 3. Context Economy

The loop's biggest cost driver is re-sending growing state. Mitigations:

1. **Summarized working context, not raw graph.** Agents receive a compact, task-scoped view:
   the relevant `HypothesisSet`(s), top-k evidence by weight, the current
   `KnowledgeStateSnapshot`, and budgets — *not* the whole graph. The `GraphView` exposes
   pre-summarized projections.
2. **Reference-by-id.** Evidence/observations are passed as ids + short digests; an agent can
   request a full artifact only when needed (lazy hydration).
3. **Rolling iteration memo.** Each iteration produces a small structured memo; old iterations
   are referenced via memo, not re-expanded.
4. **Per-agent context budgets.** The Budget Governor caps tokens per call; overflow triggers
   summarization, never silent truncation of evidence.

## 4. Prompt & Response Caching

- **Prompt caching** for the stable parts of each agent's system prompt + shared investigation
  preamble (versioned, hashed) — large savings across the many calls in a loop.
- **Response/replay cache** keyed by `(model, prompt_hash, params)` — serves recorded
  responses in `replay`/test mode and deduplicates identical in-run calls (doc 01 §7).
- **Acquisition cache** keyed by `(adapter, normalized_query)` — identical fetches dedupe and
  serve from the ledger; content-addressed artifacts dedupe bytes (doc 05 §5).

## 5. Budget Governance

`Budgets = { tokens, money_usd, seconds, requests }` per investigation, enforced by the Budget
Governor:
- Pre-flight estimate per agent/tool call (from cost models); refuse calls that would exceed a
  hard cap.
- **Adaptive depth:** as budget depletes, the loop biases toward the single most discriminating
  evidence request and toward termination; low-value branches are pruned.
- **Graceful degradation:** on exhaustion, emit a partial, clearly-labeled report (doc 01 §8)
  rather than failing.
- Every `AgentMessage` carries a `budget_snapshot` for full cost auditability.

## 6. Planning for Information Gain (the biggest lever)

The single most effective optimization is the Evidence Planning Agent's mandate to
**discriminate, not accumulate** (doc 02 §3). Maximizing information gain per cost minimizes
the number of iterations — and therefore the number of expensive `large`-tier calls — needed
to reach the termination threshold. Memory-supplied effectiveness priors further cut wasted
acquisitions (Phase 4).

## 7. Concurrency for Latency (not cost)

Independent acquisition tasks fan out concurrently (doc 01 §6) with per-adapter rate limits and
a global cap. This reduces wall-clock without increasing token spend. LLM agent calls within an
iteration are mostly sequential by design (they gate each other), but independent
hypothesis-set processing can parallelize when budget allows.

## 8. Measurement & Continuous Optimization

Tracked per run and fed to Investigation Memory (Phase 8):
- tokens & money per iteration, per agent, per tier
- iterations-to-termination and understanding-delta per iteration
- cache hit rates (prompt, response, acquisition)
- planner efficiency (info-gain realized vs. predicted)
- cost of solved vs. unsolved investigations

Targets are defined per benchmark case; regressions in cost-per-resolved-investigation are
tracked alongside the epistemic-invariant suite. **Optimization may never weaken an epistemic
guarantee** — the Skeptic gate, provenance, and hypothesis preservation are not negotiable for
cost.
