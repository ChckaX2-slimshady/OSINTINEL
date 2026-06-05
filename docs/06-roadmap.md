# 06 — Development Roadmap

**Strategy:** do *not* build the whole system at once. Deliver in phases, each producing a
**functional, runnable system before advancing**. Favor **vertical slices** over architectural
completeness — *working intelligence is preferable to perfect architecture.*

Each phase below lists: goal, scope, the vertical slice that proves it, and **exit criteria**
(must all pass to advance). Phases map to the brief's Phase 1–8.

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

## Phase 4 — Investigation Memory
**Goal:** learn strategy without contaminating evidence.
**Scope:** persist completed runs · tool/agent effectiveness metrics · confidence-calibration
records · planner-performance metrics · successful evidence chains & failed hypotheses ·
expose priors to the planner & tool selector. **Strict evidence/strategy firewall.**
**Vertical slice:** "After N runs, the planner reorders evidence requests and the selector
prefers historically effective adapters; rerunning a solved case is measurably cheaper."
**Exit criteria:**
- Memory measurably improves planner ranking / cost on a benchmark suite.
- Firewall test: Memory cannot read or alter active-run evidence or past confidence values
  (the "may not rewrite evidentiary history" guarantee).

## Phase 5 — Image Investigation Pipeline
**Goal:** the flagship vertical (doc references "Image Investigation Mode").
**Scope:** pipeline: metadata → EXIF → landmark → terrain → vegetation → architecture →
atmospheric → shadow → historical retrieval → satellite comparison → geospatial hypothesis
generation. Output: ranked location hypotheses with supporting + contradicting evidence,
confidence scores, recommended next steps.
**Vertical slice:** "Upload an image; receive ranked geolocation hypotheses with an explicit
contradicting-evidence section and recommended next investigations."
**Exit criteria:**
- Image mode produces ranked location hypotheses with supporting AND contradicting evidence.
- Shadow/sun-angle and terrain reasoning use the `compute.symbolic`/geo adapters with
  provenance.
- Skeptic actively challenges the leading location; no single-source conclusions promoted.

## Phase 6 — Geospatial Reasoning
**Goal:** deepen spatial inference quality.
**Scope:** terrain/vegetation/architecture cross-referencing · satellite vs. ground
comparison · multi-constraint location narrowing · confidence radii on `Location` nodes.
**Exit criteria:**
- Demonstrated location-narrowing across ≥3 independent geospatial constraints on golden
  cases, with calibrated confidence and uncertainty radius.

## Phase 7 — Dashboard & Visualization
**Goal:** make the investigation legible and replayable.
**Scope (REST API + Web Dashboard):** Knowledge Graph visualization · Timeline · Investigation
Replay · Hypothesis Evolution tracking · Confidence Evolution tracking · Source Explorer ·
Agent Activity Monitoring.
**Exit criteria:**
- Live and historical investigations render as an explorable graph + timeline.
- Replay reconstructs any past iteration from the ledger.
- Hypothesis & confidence evolution are visualized from `confidence_history`.

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
