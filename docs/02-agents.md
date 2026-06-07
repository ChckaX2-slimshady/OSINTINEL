# 02 — Agent Specifications

The agent quorum implements the cooperating-specialists model: **no agent possesses full
authority; each contributes evidence; consensus emerges through investigation.** Every agent
is a stateless function `(typed input, graph view, budget) -> typed output` that communicates
only via the bus and never mutates the graph directly (the runtime persists results as ledger
events). All payload types reference [03-data-schemas.md](03-data-schemas.md).

## Common Agent Contract

```
class Agent(Protocol):
    name: AgentName
    input_type: type[BaseModel]
    output_type: type[BaseModel]
    requires_llm: bool
    default_model_tier: "nano" | "small" | "large"   # see doc 08

    async def run(self, ctx: AgentContext) -> AgentResult: ...
```

`AgentContext` provides: the triggering `AgentMessage`, a **read-only** `GraphView` (query
API, never write), the current `KnowledgeStateSnapshot`, the budget snapshot, and a
provenance-stamping helper. `AgentResult` carries the typed payload + any new
`EvidenceRequest`s + a self-reported confidence and cost. The runtime validates
`epistemic_class` and provenance before persisting.

**Universal rules:** (1) never fabricate evidence — emit a Known Unknown instead;
(2) always attach provenance; (3) never collapse competing hypotheses; (4) declare model tier
so the Budget Governor can route (doc 08); (5) be idempotent given identical input + graph.

---

## 1. Aggregation Agent — *produces `INFORMATION`*

**Mission:** turn raw inputs into normalized, nuanced `Observation`s. Expertly aggregated
data becomes nuanced information.

**Responsibilities:** image analysis · OCR · metadata extraction · EXIF extraction · video
frame extraction · audio transcription · web content parsing · document parsing.

It does *not* interpret. It produces facts with provenance; meaning is the Connections
Agent's job (Foundational Separation).

- **Input:** `AgentMessage{intent:task}` referencing raw inputs / artifacts.
- **Process:** route each input to the right adapter (`parse`/`normalize` ops), capture raw
  content hash, emit one `Observation` per extracted datum.
- **Output:** `list[Observation]`.
- **Model tier:** `small` for orchestration; heavy lifting is in adapters (OCR, EXIF,
  transcription) which are mostly non-LLM.
- **Failure mode:** unparseable input → `Observation` of type `parse_error` (still
  provenance-stamped) + a Known Unknown.

---

## 2. Connections Agent — *produces `CONNECTION` + competing `EXPLANATION`s*

**Mission:** generate **competing explanations** and verifiable connections. Information is
used to make connections; verifiable connections logically sequenced are possible
*explanations*. Each explanation is one of the two types — `SPECULATION` (low-confidence) or
`EXTRAPOLATION` (high-confidence) — derived from its confidence (doc 00 §3).

**Hard requirements (from the prime spec):** preserve multiple hypotheses; resist premature
convergence; maintain alternative explanations.

- **Input:** current `Observation`s / `EvidenceObject`s + existing `HypothesisSet`s.
- **Process:** (a) propose `Connection`s between graph nodes with a `verification` status;
  (b) for each open question, propose/extend a set of *competing* `Explanation`s (initially
  low-confidence, hence `SPECULATION`). It must propose **≥2** alternatives whenever it
  proposes any, and is penalized by the Skeptic for monoculture. The Synthesis Agent then
  synthesizes these competing explanations *into* hypotheses (§6).
- **Output:** `list[Connection]`, `list[Explanation]` (set-grouped). It does **not** create
  hypotheses directly — that is the synthesis step.
- **Anti-convergence mechanism:** the agent is prompted and post-checked to keep
  `residual_mass > 0` and to surface a deliberately different "left-field" alternative each
  time a set's leader exceeds a confidence band, forcing the Skeptic/planner to test it.
- **Example output:** competing explanations `summit marker (0.35)` /
  `communications structure (0.28)` / `image artifact (0.17)` with residual mass `0.20`.
- **Model tier:** `large` (this is core reasoning).

---

## 3. Evidence Planning Agent — *produces `EvidenceRequest`*

**Mission:** answer *"What evidence would most efficiently differentiate the competing
hypotheses?"* — **discriminate, don't accumulate.**

- **Input:** active `HypothesisSet`s + `KnowledgeStateSnapshot` (Known Unknowns) + Memory
  priors (tool cost/effectiveness).
- **Process:** for each set, estimate each candidate evidence's **expected information gain**
  (entropy reduction over the set) and **cost**, then rank by `score = info_gain / cost`.
  Optimizes for information gain, cost efficiency, confidence improvement, investigation
  speed. Prefers evidence that *splits* the leading alternatives over evidence that merely
  reinforces the leader.
- **Output:** ranked `list[EvidenceRequest]` with `candidate_capabilities` (capability tags,
  not concrete tools — tool choice is the next agent's job).
- **Model tier:** `large` for scoring rationale; the arithmetic ranking is deterministic code.

---

## 4. Tool Selection Agent — *produces `ToolPlan`*

**Mission:** choose tools **dynamically**. Never hardcode investigative paths; select tools
according to evidence requirements; tools remain interchangeable.

- **Input:** top `EvidenceRequest`s + Adapter Registry capability map + Memory tool-
  effectiveness metrics + remaining budget.
- **Process:** match `candidate_capabilities` → registered adapters supporting that
  capability; pick the best by (effectiveness prior, cost, rate-limit headroom, source
  independence vs. already-used sources); set `fallback_adapters`.
- **Output:** `list[ToolPlan]`.
- **Independence bias:** prefers an adapter whose source is *independent* from sources already
  used for the same hypothesis (directly improves the Confidence Agent's
  `source_independence` factor and guards against source monoculture UU-indicators).
- **Model tier:** `small` (mostly a constrained matching task) — escalates to `large` only on
  ambiguous capability matches.

---

## 5. Information Acquisition Agent — *produces `EvidenceObject` (`INFORMATION`)*

**Mission:** execute `ToolPlan`s and collect structured evidence: maps, images, satellite
imagery, public records, infrastructure data, historical archives, documents, public
datasets, open-source references.

- **Input:** `list[ToolPlan]`.
- **Process:** call adapters (`search`/`lookup`/`collect`), store raw artifacts content-
  addressed, record the external request+response as a `LedgerEvent` (for replay), then
  `normalize` into `EvidenceObject`s. Computes initial `supports`/`contradicts`/`weights`
  against the hypotheses named in the originating request (weak signal; the Synthesis +
  Confidence agents arbitrate).
- **Output:** `list[EvidenceObject]`.
- **Resilience:** on adapter failure, try `fallback_adapters`, record the failure as evidence
  about tool effectiveness (→ Memory), and surface a Known Unknown if all fail.
- **Model tier:** `nano`/none for execution; `small` only to normalize messy payloads.

---

## 6. Synthesis Agent — *synthesizes `EXPLANATION`s into `HYPOTHESIS`/`INSIGHT`*

**Mission:** synthesize competing explanations into hypotheses, merge evidence, update
confidence inputs, preserve provenance, generate findings. **Never fabricate missing
evidence.**

- **Input:** competing `Explanation`s + new `EvidenceObject`s + current `HypothesisSet`s +
  prior `SkepticFinding`s.
- **Process:** (a) **synthesize** the competing explanations framed by the Connections Agent
  *into* `Hypothesis` objects (both `SPECULATION` and `EXTRAPOLATION` explanations feed this,
  per doc 00 §3), each carrying a `derived_from_explanations` back-reference; (b) attach
  evidence to hypotheses (`supports`/`contradicts`) and recompute set structure. It does
  **not** finalize confidence — it requests a `ConfidenceAssessment` from the Confidence Agent
  and must pass the Skeptic before any promotion to `INSIGHT`. Missing evidence becomes a
  Known Unknown, never a guess. At termination it composes the `InsightReport`.
- **Output:** `Hypothesis` objects (synthesized from explanations), draft findings, and (on
  termination) `InsightReport`.
- **Model tier:** `large`.

---

## 7. Skeptic Agent — *mandatory challenge layer*

**Mission:** challenge the emerging consensus. **No major conclusion bypasses Skeptic
review.**

**Responsibilities:** search for contradictions · identify assumptions · detect reasoning
weaknesses · generate alternative explanations · challenge emerging consensus.

- **Input:** the leading hypothesis/insight candidate + its evidence + reasoning chain.
- **Process:** actively attempt to *falsify* the leader. Produce `SkepticFinding`s
  (contradiction / hidden_assumption / reasoning_weakness / source_dependency / alt_explanation
  / overfit). May inject a brand-new `Hypothesis` into the set (origin=`skeptic`) and may
  reactivate an archived one. A `blocking` finding halts promotion until resolved.
- **Output:** `list[SkepticFinding]`, optional new/reactivated `Hypothesis`.
- **Gate:** the runtime will not let a hypothesis be promoted to `INSIGHT` while an
  unresolved `blocking` finding targets it. This makes the Skeptic a true gate, not advice.
- **Model tier:** `large`, run with an adversarial system prompt and (optionally) a different
  model than Synthesis to decorrelate errors (doc 08 §model diversity).

---

## 8. Confidence Agent — *explainable confidence*

**Mission:** compute calibrated, **explainable** confidence. Confidence must be explainable —
never a bare scalar.

**Factors:** source quality · evidence diversity · evidence quantity · contradictions ·
source independence · temporal relevance.

- **Input:** a `Hypothesis` + its evidence set + source metadata.
- **Process:** compute each factor deterministically where possible (diversity, quantity,
  independence, temporal relevance are computable from the graph; source quality uses a
  maintained source-reputation table; contradiction penalty from contradicting evidence and
  blocking findings), combine via a versioned, reproducible model, and renormalize the
  hypothesis set. Emits a factor breakdown + natural-language explanation.
- **Output:** `ConfidenceAssessment` per hypothesis; updated set normalization (writes a
  `confidence_change` ledger event with `delta_reason`).
- **Calibration:** the model version is recorded so calibration accuracy can be measured and
  improved by Memory (doc 09 calibration harness). This agent also **re-types each hypothesis'
  backing explanation** by confidence — `SPECULATION` (low) or `EXTRAPOLATION` (high) — and
  promotes the gate-cleared, threshold-meeting leader to `INSIGHT`.
- **Model tier:** `small` + deterministic code; `large` only to author the explanation.

---

## 9. Epistemology Agent — *protects against false certainty*

**Mission:** track what is known, unknown, assumed, and possibly missing; preserve
uncertainty visibility.

**Responsibilities:** detect hidden assumptions · monitor uncertainty · flag possible blind
spots · preserve uncertainty visibility.

- **Input:** full investigation state at end of each iteration.
- **Process:** refresh the `KnowledgeStateSnapshot` — recompute **Knowns** (evidence-backed
  claims), **Known Unknowns** (open questions, feeding the planner), and **Unknown-Unknown
  Indicators** (source monoculture, temporal gaps, unexplained residual mass, contradiction
  clusters, single-tool dependence). Surfaces `hidden_assumptions` the rest of the quorum is
  treating as given.
- **Output:** `KnowledgeStateSnapshot` (persisted; drives next-iteration planning and the
  report's uncertainty sections).
- **Model tier:** `large` (meta-reasoning) but small context (operates on summaries + metrics).

---

## 10. Speculative Possibility Engine — *produces `SPECULATION` (kept separate from conclusions)*

Not part of the mandatory per-iteration quorum; invoked on demand (e.g., when the planner
runs dry, or to expand the possibility space, or on operator request). Distinct from the
in-flow `SPECULATION` explanation type: this engine deliberately generates *separate*,
clearly-labeled low-confidence probabilities that are kept out of conclusions.

**Mission:** generate low-confidence probabilities to expand the investigative space —
**not to establish truth.**

- **Requirements:** every item clearly labeled `SPECULATION`; separate confidence model;
  explicit `evidence_limitations`; `would_promote_if` conditions; never auto-flows into an
  `INSIGHT`.
- **Output:** `list[SpeculationItem]` (segregated storage; excluded from set normalization).
- **Model tier:** `large` with a high-temperature, explicitly-flagged "divergent" prompt.

---

## Agent Interaction Summary (one iteration)

```
runtime ─task→ Aggregation ─Observations→ runtime
runtime ─task→ Connections ─Connections+competing Explanations→ runtime
runtime ─task→ Synthesis(synthesize) ─Hypotheses from Explanations→ runtime
runtime ─task→ EvidencePlanning ─ranked EvidenceRequests→ runtime
runtime ─task→ ToolSelection ─ToolPlans→ runtime
runtime ─task→ InformationAcquisition ─EvidenceObjects→ runtime   (fan-out, concurrent)
runtime ─task→ Synthesis(merge) ─evidence linked to hypotheses→ runtime
runtime ─challenge→ Skeptic ─SkepticFindings(+new Hypo)→ runtime   (GATE)
runtime ─task→ Confidence ─ConfidenceAssessments(+explanation re-typing)→ runtime  (explainable)
runtime ─task→ Epistemology ─KnowledgeStateSnapshot→ runtime
runtime: Termination Evaluator → continue | emit InsightReport
```

The runtime — not the agents — owns this ordering, which is what keeps runs deterministic,
replayable, and auditable (doc 01 §3).

## Per-Agent Prompt Discipline (LLM agents)

Each LLM agent ships with a system prompt that encodes its contract and, critically, the
**universal rules** above. Prompts are versioned in `osintinel/agents/<name>/prompt.md`,
hashed into the ledger on every call (doc 01 §7), and covered by golden tests (doc 09). The
Skeptic and Connections prompts in particular hardcode the anti-premature-convergence and
no-fabrication constraints so they survive model changes.
