# 06 — Development Roadmap

**Strategy:** do *not* build the whole system at once. Deliver in phases, each producing a
**functional, runnable system before advancing**. Favor **vertical slices** over architectural
completeness — *working intelligence is preferable to perfect architecture.*

Each phase below lists: goal, scope, the vertical slice that proves it, and **exit criteria**
(must all pass to advance). Phases map to the brief's Phase 1–8.

> **Paradigm correction (post-Phase 7).** OSINTENAL is **online and model-driven**: it depends on
> live open-source data and a tiered model ensemble (doc 11). The deterministic, no-network,
> no-key behavior built through Phases 1–7 is retained **as the test/replay mode**, not the
> product's operating mode. Model integration is tracked as **Phase M** (below), slotted before
> Phase 8 (Self-Improvement), which depends on it.

---

## Phase 0 — Architecture (this corpus) ✅
**Goal:** complete, internally-consistent design before implementation.
**Exit:** all 10 deliverables present, cross-referenced, and self-consistent (this `docs/`
set). No implementation begins until this holds.

## Phase 1 — Core Orchestration Framework
**Goal:** a runnable recursive loop with the agent quorum, using mock/stub adapters.
**Scope:** schemas (doc 03) as Pydantic models · in-memory Agent Bus · Recursive Loop Engine ·
Termination Evaluator · Budget Governor (token/time/request) · all nine agents wired (LLM-
backed where required, deterministic where possible) · CLI to start an investigation.
**Vertical slice:** "Given three seed observations and a stub evidence source, run the full
Observe→…→Repeat loop and emit an `InsightReport` with ranked competing hypotheses, Known
Unknowns, and a reasoning chain."
**Exit criteria:**
- `osintenal run` executes end-to-end and emits a schema-valid `InsightReport`.
- Loop honors all termination conditions (doc 01 §5).
- Skeptic gate provably blocks promotion on a `blocking` finding (tested).
- Competing hypotheses preserved; `confidence_history` append-only (epistemic-invariant tests
  green, doc 09).
- Every emitted object carries valid provenance.

## Phase 2 — Knowledge Graph & Provenance Engine ✅
**Goal:** durable, auditable state.
**Scope:** `GraphStore` port + embedded backend (doc 04) · append-only Provenance Ledger with
hash chain · materialized-view rebuild/replay · write-time integrity constraints (ladder,
provenance-required, append-only).
**Vertical slice:** "Run an investigation, kill the process, reload from the ledger, and get a
byte-identical graph; produce a full evidence chain for any insight." — delivered as
`osintenal verify` (persist → reload → replay → byte-identical graph) and `osintenal audit`.
**Exit criteria:**
- Graph fully reconstructable from the ledger (replay test). ✅ `tests/graph/test_replay.py`
- Ladder & provenance constraints reject malformed writes. ✅ `tests/graph/test_constraints.py`
- Audit query returns a complete evidence chain terminating in sourced `INFORMATION` nodes.
  ✅ `tests/graph/test_audit.py`
- Hash-chain integrity check passes in CI (verified on every load). ✅
  `tests/graph/test_ledger_persistence.py`

**Implementation note:** the ledger is now the complete source of truth — each event's payload
carries a full object snapshot, so `replay_state()` reconstructs an `InvestigationState`
byte-for-byte (timestamps and confidence history included), and `build_graph()` projects it
into the constraint-checked property graph. The durable store is append-only JSONL (zero new
dependencies); a SQLite/Neo4j backend can replace the embedded one behind the same port.

## Phase 3 — Tool Adapter Framework ✅
**Goal:** real, interchangeable data sources.
**Scope:** Adapter interface + Registry + capability map (doc 05) · 5 reference adapters
(Wayback[timemap+snapshot], Nominatim, Overpass, Wikidata, crt.sh/CT) · cassette transport for
record/replay · content-addressed artifact store · license-gated supplemental framework ·
live smoke tests (network-gated, opt-in via `OSINTENAL_RECORD=1`).
**Vertical slice:** "Tool Selection picks an archive adapter by capability, Acquisition fetches
a real snapshot, evidence updates a hypothesis — all replayable from cassettes." — delivered as
`osintenal slice` (and `osintenal adapters`).
**Exit criteria:**
- ≥4 adapters pass contract + parse/normalize tests; outputs schema-valid with provenance.
  ✅ 5 adapters, `tests/adapters/test_reference_adapters.py`
- Tool Selection chooses by capability with no hardcoded path; fallbacks work.
  ✅ `tests/adapters/test_archive_slice.py`
- A run is fully replayable offline from recorded cassettes.
  ✅ `tests/adapters/` + the slice replays byte-identically from the ledger.

**The integral storage decision (versatility vs. data volume).** Phase 2 made every ledger
event a byte-for-byte object snapshot; left unchecked, heavy adapter payloads would bloat the
log and slow replay. Resolution: heavy bytes go to a **content-addressed store** (deduped by
SHA-256) and the ledger records only a lean `raw_response` event holding the content hash — the
bytes never enter the ledger, so state/graph still replay byte-identically no matter how large
the artifact. This lets the catalogue favour **broad, light, structured adapters** for
versatility at ~zero storage cost while the heavy path (Wayback page snapshot) is proven once
through the CAS. EXIF/image-binary is deliberately deferred to Phase 5 (image investigation).

## Phase 4 — Investigation Memory ✅
**Goal:** learn strategy without contaminating evidence.
**Scope:** persist completed runs (JSONL of `RunDigest`s) · tool/adapter effectiveness metrics
(Laplace-smoothed success rate) · confidence-calibration records · planner-performance metrics ·
capability sequences · expose priors to the planner & tool selector via a read-only
`StrategyPriors` port. **Strict evidence/strategy firewall.**
**Vertical slice:** "After N runs, the planner reorders evidence requests and the selector
prefers historically effective adapters; rerunning a solved case is measurably cheaper." —
delivered as `osintenal memory` (the learning benchmark) and `scenarios/learning_benchmark.py`.
**Exit criteria:**
- Memory measurably improves planner ranking / cost on a benchmark suite. ✅
  `tests/memory/test_learning.py` — a misleading seed picks the noisy adapter first (13,200
  tokens); Memory learns and switches to the reliable adapter, holding at 1,700 tokens (~87%
  cheaper) and stable.
- Firewall test: Memory cannot read or alter active-run evidence or past confidence values. ✅
  `tests/memory/test_firewall.py` — digests carry no evidence content, ingest rejects
  non-digests, the priors view exposes no mutation surface, and a run's ledger + confidence
  history are provably untouched by any Memory activity.

**Design.** Memory ingests only a `RunDigest` — a whitelist of strategy/outcome metrics built by
`build_run_digest` (the sole bridge from a live run), enforced by `memory/firewall.py`. The
planner/selector consume a `MemoryPriors` view through the `StrategyPriors` port (agents depend
on the Protocol, not the `memory` package), so learning influences *how* the system
investigates while remaining structurally unable to rewrite evidentiary history. An adapter is
credited only when it supported the leader of a **resolved** run (reached the confidence
threshold / a gate-cleared insight), so weak or single-source feeds decay out of preference.

## Phase 5 — Image Investigation Pipeline ✅
**Goal:** the flagship vertical (doc references "Image Investigation Mode").
**Scope:** pipeline: metadata → EXIF → landmark → terrain → vegetation → architecture →
atmospheric → shadow → historical retrieval → satellite comparison → geospatial hypothesis
generation. Output: ranked location hypotheses with supporting + contradicting evidence,
confidence scores, recommended next steps.
**Vertical slice:** "Upload an image; receive ranked geolocation hypotheses with an explicit
contradicting-evidence section and recommended next investigations." — delivered as
`osintenal image` and `pipelines/image_investigation.py`.
**Exit criteria:**
- Image mode produces ranked location hypotheses with supporting AND contradicting evidence. ✅
  `tests/pipelines/test_image_pipeline.py`
- Shadow/sun-angle and terrain reasoning use the `compute.symbolic`/geo adapters with
  provenance. ✅ a real NOAA solar-position calc (`adapters/compute/solar.py`) predicts each
  candidate's shadow and supports/contradicts it; geo corroboration via Overpass/Wikidata.
- Skeptic actively challenges the leading location; no single-source conclusions promoted. ✅
  the leader is held at HYPOTHESIS under a blocking source-dependency finding while it rests on
  EXIF alone, and promoted to INSIGHT only once independent groups corroborate it.

**New capabilities.** `media.exif` is the image-binary path deferred from Phase 3: a
dependency-free TIFF/EXIF codec (`adapters/media/exif.py`) round-trips real JPEG bytes, which
are stored in the content-addressed store while only the small GPS/timestamp structure becomes
evidence. `compute.symbolic` solar geometry turns capture time + an observed shadow into
support/contradiction per candidate. Evidence→hypothesis linking remains a deterministic
relevance rule standing in for a vision/LLM model (the loop stays model-free through Phase 5).

## Phase 6 — Geospatial Reasoning ✅
**Goal:** deepen spatial inference quality.
**Scope:** terrain/vegetation/architecture cross-referencing · satellite vs. ground
comparison · multi-constraint location narrowing · confidence radii on `Location` nodes.
**Vertical slice:** a golden suite where independent constraints (sun elevation, ground
elevation, landmark bearing/distance, biome band) intersect to a centroid + radius — delivered
as `osintenal geo` and `pipelines/geospatial_reasoning.py`.
**Exit criteria:**
- Demonstrated location-narrowing across ≥3 independent geospatial constraints on golden
  cases, with calibrated confidence and uncertainty radius. ✅
  `tests/pipelines/test_geospatial.py` — four global golden cases each narrow from ~1,500 km
  (one constraint) to ~10 km (five), the truth lands inside the radius in every case (100%
  coverage), confidence is ~0.96 when constraints agree and collapses to ~0.06 when they
  conflict, and the result maps to a `Location` node carrying `confidence_radius_km`.

**Design.** A deterministic, dependency-free hierarchical grid solver: each constraint is a
likelihood field over the surface; their product is the posterior. A coarse global pass finds
the basin, a descent re-centres on the MAP, and an adaptive pass sized to hold ~95% of the mass
yields the centroid, the 95%-mass radius (floored at grid resolution — no sub-grid overclaim),
and a confidence equal to constraint *agreement* × an independence factor. "Independent" is
counted by distinct source groups, so the sun's elevation and azimuth count once. Reuses the
Phase 5 `compute.symbolic` solar model; a `SyntheticDEM` stands in for a real elevation adapter.

## Phase 7 — Dashboard & Visualization ✅
**Goal:** make the investigation legible and replayable.
**Scope (REST API + Web Dashboard):** Knowledge Graph visualization · Timeline · Investigation
Replay · Hypothesis Evolution tracking · Confidence Evolution tracking · Source Explorer ·
Agent Activity Monitoring.
**Vertical slice:** `osintenal dashboard` renders a run into one self-contained HTML console;
the JSON service payload (`interfaces/api`) is the REST contract.
**Exit criteria:**
- Live and historical investigations render as an explorable graph + timeline. ✅
  `interfaces/dashboard` renders a layered SVG knowledge graph + per-iteration timeline.
- Replay reconstructs any past iteration from the ledger. ✅ `replay_state(…, until_iteration=k)`
  / `replay_iteration`, covered by `tests/interfaces/test_dashboard.py`.
- Hypothesis & confidence evolution are visualized from `confidence_history`. ✅ SVG sparklines
  per hypothesis, leader highlighted.

**Design.** To stay air-gapped, deterministic, and testable without a browser (the discipline
held since Phase 1), Phase 7 is a **static-site generator** rather than a live SPA: a read-only
service layer (`interfaces/api/service.py`) projects a run into a JSON-serializable
`DashboardData` (the REST contract — a FastAPI app would just return it), and a renderer
(`interfaces/dashboard/render.py`) emits one HTML document with **inline** CSS/SVG/vanilla-JS and
**zero external resources** (no CDNs, web fonts, or network). The colour language *is* the
epistemic ladder, so the visuals encode the Foundational Separation rather than decorate it.
Tests assert the offline guarantee (no `http(s)://`, `src=`, `<link>`, `@import`) and that the
graph/timeline/evolution sections are present and replayable. Navigation is **CSS-only (no
JavaScript)** so tabs work even where scripts are stripped.

## Phase M — Model Integration (cross-cutting; before Phase 8) — gateway ◑
**Goal:** make OSINTENAL model-driven over live data (doc 11), with auditable, replayable,
cost-accounted model calls.
**Scope:** `InferenceGateway` + `Embedder` ports · tier→model routing (`embed`=HF, `task/nano/
small`=HF specialized, `reason/large`=Anthropic) · providers over the cassette transport
(record/replay) · cost into the Budget Governor · lean `model_call` ledger events · graceful
degradation (live → replay → deterministic).
**Vertical slice:** `osintenal models` shows the routing and exercises the gateway; live runs
record model I/O and replay offline.
**Milestones / exit criteria:**
- ✅ **Gateway foundation** — ports, providers (deterministic + Anthropic + Hugging Face),
  record/replay, cost accounting, `model_call` events, `osintenal models`, credentials never in
  cassettes. `tests/inference/test_gateway.py`.
- **Wire agents tier-by-tier** — each behind the gateway, each recorded for replay:
  - ◑ **`task`** — evidence→hypothesis **relevance judgment** (`agents/relevance.py`):
    `RelevanceJudge` port with a `HeuristicRelevanceJudge` (default; reproduces the prior
    stand-ins, keeps CI byte-identical) and an `LLMRelevanceJudge` (task tier; JSON output,
    embedded-JSON extraction, graceful fallback to the heuristic on bad/unreachable model). The
    gateway is threaded through the controller/loop to `AgentContext.llm`. Next: extraction +
    query formulation. `tests/inference/test_relevance.py`.
  - ◑ **`embed`** — true source-independence (`agents/semantic.py`): embeds supporting evidence
    and collapses declared groups whose content is near-duplicate (syndication/wire copy), so
    illusory corroboration can't fool the Confidence gate. The Skeptic raises a BLOCKING
    `illusory_independence` finding when effective independence drops below the minimum, resolved
    when a genuinely distinct source arrives (`osintenal independence`,
    `tests/inference/test_semantic.py`). Gated on an embedder being present, so deterministic
    runs are unaffected. Next: semantic dedup + retrieval over large corpora.
  - ◑ **`reason`** — open-ended model reasoning (`agents/reasoning.py`): Connections asks the
    reason tier for *additional* competing explanations (hypothesis generation beyond the given
    candidates), and the Skeptic asks it for adversarial critique (hidden assumptions / reasoning
    weaknesses). Model output is advisory — severity is capped below `blocking`, so the computed
    gates (source-dependency, illusory-independence) remain the only blockers. Gated on a gateway;
    deterministic runs are the floor (`osintenal reason`, `tests/inference/test_reasoning.py`).
    Next: model-authored Synthesis/Confidence prose, and Skeptic↔Synthesis model **decorrelation**
    (per-role model override) per doc 08 §1.
- ◻ **Online-first defaults** — adapters live by default; cassettes become the recorded test
  corpus; golden runs recorded once and replayed in CI.

## Phase 8 — Self-Improvement Systems
**Goal:** recursively improve investigative strategy — **without rewriting evidentiary
history.**
**Scope:** track tool effectiveness, agent effectiveness, investigation success rates, false-
positive rates, confidence-calibration accuracy · calibration harness (doc 09) feeding the
Confidence model · planner/strategy tuning loop.
**Exit criteria:**
- Calibration accuracy and planner efficiency improve over a frozen benchmark across versions.
- Self-improvement touches *strategy artifacts only*; an audit proves no evidence/ledger
  mutation.

---

## Cross-Phase Definition of Done
For **every** phase: schema-valid I/O · provenance on every object · epistemic-invariant tests
green (doc 09) · runnable demo command · updated docs. A phase is not done until its vertical
slice runs.

## Sequencing Rationale
Schemas+loop (1) before storage (2) so the contract is proven first; storage before real
adapters (3) so evidence is durable when real data arrives; memory (4) before the heavy image
vertical (5/6) so the flagship benefits from learned priors; UI (7) before self-improvement
(8) so improvement is observable. Each step is a usable system on its own.
