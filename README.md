# OSINTINEL

**Open Source Intelligence Sentinel** — *Autonomous Aggregation :: Insight via Intelligence
:: Evolution via Recursive Improvement.*

OSINTINEL is a modular, multi-agent intelligence layer that transforms nuanced data
aggregated from expert methodology into auditable, uncertainty-aware insights through
investigation, adaptive planning, provenance tracking, structured skepticism, epistemic
scrutinizing, and recursive evaluation.

> **Prime Directive** — Use expert methodology to gather niche data through multi-agent
> orchestration, data structuring, and recursive critical analysis.

> **Success is measured** not by answer generation, but by the system's ability to maintain
> logical coherence integrity, preserve uncertainty, challenge itself, and produce auditable
> intelligence insights.

---

## Status

> **Paradigm: online, model-driven, and free to run.** OSINTINEL depends on live open-source
> data (the adapters) and a tiered model ensemble — **all of which can run locally and for $0**.
> Via one OpenAI-compatible interface the tiers point at **Ollama** (local: embeddings + small
> task models + reasoning, fully private) or, for heavier reasoning, a **free cloud tier**
> (Gemini / Groq / OpenRouter). Switching is one env var, not code. The deterministic,
> no-network path is retained **as the test/replay mode** (record live once → replay in CI), not
> the operating mode. Model & inference architecture: [`docs/11`](docs/11-model-inference-architecture.md).

**Phase 0 — Architecture: complete.** The full design corpus lives in [`docs/`](docs/).

**Phase 1 — Core orchestration framework: implemented & runnable.** The nine-agent quorum,
the recursive investigation loop, budget governance, an append-only hash-chained provenance
ledger, the epistemic-invariant guards, and a CLI are all in place and exercised by a
deterministic, offline, replayable demo investigation.

**Phase 2 — Knowledge graph & provenance engine: implemented.** The ledger is now durable
(append-only JSONL) and is the complete source of truth: every object is reconstructable from
the event log, so an investigation can be killed, reloaded from disk, and **replayed
byte-for-byte**. A `GraphStore` port with an embedded backend, write-time integrity
constraints (ladder, provenance-required, speculation-quarantine), and the doc-04 audit
queries materialize the knowledge graph as a view over the ledger.

**Phase 3 — Tool adapter framework: implemented.** Lawful, public-source reference adapters
(Nominatim, Overpass, Wayback, Wikidata, crt.sh) reach the world behind one Protocol, chosen
**by capability** (never a hardcoded path) with fallbacks. Every external call goes through a
**cassette transport** (replay-by-default), so a whole investigation runs offline and in CI;
live recording is opt-in (`OSINTINEL_RECORD=1`). The *integral storage decision* keeps the
ledger lean: heavy artifacts (e.g. a Wayback page snapshot) are written to a **content-addressed
store** and the ledger holds only a `raw_response` hash/ref — bytes never enter the event log,
so replay stays byte-identical regardless of data volume. Supplemental commercial sources
(Maltego, Pipl, PimEyes, Recorded Future, …) are modeled as **license-gated** adapters, off
unless the operator supplies credentials *and* attests to authorized use.

**Phase 4 — Investigation Memory: implemented.** The system now **learns strategy** from
completed runs — which adapters and capabilities actually resolve cases — and feeds those priors
to the planner and tool selector, so rerunning a solved case is measurably cheaper (the
benchmark falls from 13,200 to 1,700 tokens, ~87%, once Memory corrects a misleading default).
Learning is held behind a strict **evidence/strategy firewall**: Memory ingests only a
whitelisted `RunDigest` of metrics (never evidence content) and is handed to agents as a
read-only priors port with no path to read or rewrite evidentiary history.

**Phase 5 — Image Investigation Pipeline: implemented.** The flagship vertical geolocates an
uploaded image through the full stage sequence (EXIF → landmark → terrain → vegetation →
architecture → shadow → historical → satellite → hypothesis generation) and returns **ranked
location hypotheses with explicit supporting *and* contradicting evidence**, confidence, and
concrete next steps. A dependency-free EXIF codec round-trips real JPEG bytes (image → CAS),
and a NOAA solar-position calculation (`compute.symbolic`) predicts each candidate's shadow to
support or refute it. The Skeptic holds the leading location at HYPOTHESIS while it rests on a
single source and promotes it to INSIGHT only once independent groups corroborate it.

**Phase 6 — Geospatial Reasoning: implemented.** Beyond ranking discrete candidates, the system
narrows a location *continuously* by intersecting independent spatial constraints — sun
elevation, ground elevation, landmark bearing/distance, biome band — into a centroid with an
honest **uncertainty radius** and a calibrated confidence. On a global golden suite each case
narrows from ~1,500 km (one constraint) to ~10 km (five), the truth lands inside the radius
every time, and confidence collapses when constraints conflict. The result is a `Location` node
with a confidence radius (doc 04 §2).

**Phase 7 — Dashboard & Visualization: implemented.** `osintinel dashboard` renders any run into
a single **self-contained HTML console** — inline CSS/SVG and **CSS-only navigation (no
JavaScript)**, no external scripts, fonts, or network — so it works air-gapped, in sandboxed
previews, and is testable without a browser. It shows the knowledge graph (layered by epistemic
tier), the per-iteration timeline, investigation replay (any past iteration reconstructed from
the ledger), hypothesis & confidence evolution (sparklines from `confidence_history`), a source
explorer, and agent activity. A read-only JSON service layer (`interfaces/api`) is the REST
contract a FastAPI app would serve.

**Phase M — Model integration: complete.** A provider-agnostic
`InferenceGateway` routes the three tiers (`embed` · `task`/`nano`/`small` · `reason`/`large`)
through one **universal OpenAI-compatible client**, so the whole stack runs **free** on local
**Ollama** (or free cloud tiers — Gemini / Groq / OpenRouter) selected by *profile*, not code.
It does tier→model config, cost accounting into the Budget Governor, and **record/replay over the
same cassette transport the adapters use** — model calls are auditable (lean `model_call` ledger
events) and reproducible. Graceful degradation: live-local → live-cloud → recorded-replay →
deterministic (CI). The recommended hybrid keeps embeddings/tasks local (private) and routes only
reasoning to a free-cloud model. **All three agent tiers are wired:** the `task` tier drives
evidence→hypothesis **relevance judgment** (`agents/relevance.py`) — a `RelevanceJudge` port with
a heuristic default (CI-stable) and an LLM judge that falls back gracefully. The `embed` tier
detects **illusory source independence** — when "independent" sources are syndicated copies, it
collapses them so the Confidence gate isn't fooled, and the Skeptic raises a blocking finding
(`agents/semantic.py`, `osintinel independence`). The `reason` tier now lets the flagship model
do open-ended work — Connections proposes *additional* competing explanations and the Skeptic
authors adversarial critique (advisory; the computed gates still own blocking) — `agents/reasoning.py`,
`osintinel reason`. All three tiers degrade to deterministic behavior with no model present.
External I/O (adapters + model calls) shares one **transport with `replay`/`record`/`live` modes**
(`OSINTINEL_NET`) so cassettes are the recorded test corpus and production is one switch from
live; Skeptic↔Synthesis **model decorrelation** is a config knob (`OSINTINEL_SKEPTIC_PROFILE`). See
[`docs/06-roadmap.md`](docs/06-roadmap.md) and [`docs/11`](docs/11-model-inference-architecture.md).

**Phase 8 — Self-Improvement Systems: implemented.** The system tunes its own *strategy* across
versions — a calibration harness (ECE / Brier / reliability curve) fits a softmax **temperature**
that feeds the Confidence model, and the Phase 4 memory loop cuts planner cost. On a frozen
benchmark, calibration error drops **0.366 → 0.082** (accuracy preserved — temperature scaling
doesn't change which hypothesis leads) and planner cost **13,200 → 1,700 tokens/case**, v1 → v2.
A firewall **audit** proves self-improvement touches strategy artifacts only: the run's ledger
hash chain and every confidence history are byte-for-byte unchanged (and a rogue mutation is
detected). It's strategy improvement behind the evidence firewall — never self-modification of
evidence or code (`osintinel improve`, `osintinel/improvement/`).

**All phases (0–8 + Model Integration) are complete.** The build is online- and model-driven,
free/local-first, with deterministic record/replay as the test mode.

### Quickstart

```bash
pip install -e ".[dev]"        # Python 3.11+; runtime dep: pydantic v2 (model providers use stdlib HTTP)

# Models are free to run. Fully local & private via Ollama (recommended):
#   ollama serve && ollama pull qwen2.5:14b-instruct qwen2.5:3b-instruct nomic-embed-text
#   export OSINTINEL_INFERENCE_PROFILE=ollama
# Or keep embeddings/tasks local and route only reasoning to a free cloud tier:
#   export OSINTINEL_INFERENCE_PROFILE=ollama OSINTINEL_REASON_PROFILE=gemini GEMINI_API_KEY=...
# (No profile set ⇒ deterministic offline mode — the default for CI/tests.)

osintinel run                 # run the bundled demo investigation (human-readable report)
osintinel run --json          # same, as a schema-valid InsightReport JSON
osintinel verify              # run → persist ledger → reload → replay; prove byte-identical
                              #   graph + hash chain (Phase 2 durability guarantees)
osintinel audit               # print the evidence chain for the leading insight,
                              #   terminating in sourced INFORMATION nodes
osintinel adapters            # list lawful reference + license-gated supplemental adapters
osintinel slice               # Phase 3: capability-based selection + real (cassette) evidence
                              #   updating a hypothesis; shows the ledger/CAS storage split
osintinel memory              # Phase 4: learning benchmark — cost to solve the same case falls
                              #   as Investigation Memory learns which adapter actually works
osintinel image               # Phase 5: geolocate a sample image — ranked location hypotheses
                              #   with supporting AND contradicting evidence + next steps
osintinel geo                 # Phase 6: narrow a location across ≥3 independent geospatial
                              #   constraints — centroid + uncertainty radius, calibrated
osintinel dashboard --out d.html   # Phase 7: render the self-contained HTML console (offline)
osintinel models              # Phase M: show tier→model routing + exercise the inference gateway
osintinel independence        # Phase M: embed tier — collapse syndicated "independent" sources
osintinel reason              # Phase M: reason tier — model-generated explanations + critique
osintinel improve             # Phase 8: self-improvement — calibration + planner tuning, audited

pytest -q                      # unit + invariant + adapter + memory + geo + model + improvement
```

### Using it on your own questions

Beyond the demos, two **front doors** run your own investigations (pose a question, list the
competing answers, provide evidence; the system frames hypotheses, judges relevance, runs the
Skeptic gate, and returns a ranked, uncertainty-aware report):

```bash
# 1) Local web app — a browser UI (dark "console" theme), runs kept in memory
osintinel serve                      # → open http://127.0.0.1:8765

# 2) MCP server — drive it by chatting with Claude (Desktop or Code)
osintinel mcp                        # stdio MCP server exposing `investigate` + `models_status`

# 3) Autonomous web research — the system gathers its own evidence (offline demo)
osintinel research                   # search → fetch → extract → reason → ranked answer
```

**Autonomous research:** `autoresearch_investigation` (service layer) and the `web.search`/
`web.fetch` adapter let an investigation **search the open web, fetch results, and extract
evidence itself** — lawful free backends (Wikipedia default; DuckDuckGo for diverse domains),
grouped by domain so independent corroboration is real. The demo runs offline from a recorded
cassette; live is `OSINTINEL_NET=live`.

To plug the MCP server into **Claude Desktop** (`claude_desktop_config.json`) or Claude Code:

```json
{
  "mcpServers": {
    "osintinel": {
      "command": "osintinel",
      "args": ["mcp"],
      "env": { "OSINTINEL_INFERENCE_PROFILE": "ollama" }
    }
  }
}
```

Then just ask Claude: *"Use osintinel to investigate whether the ridge structure is a mast or a
turbine, given this evidence…"* — it calls the `investigate` tool and returns the report.

**Models are free & local.** Set `OSINTINEL_INFERENCE_PROFILE=ollama` (all local) — or add
`OSINTINEL_REASON_PROFILE=gemini` to route only the heavy reasoning to a free cloud tier. With no
model configured, tag each piece of evidence with the answer it supports and the deterministic
engine still reasons over it. *Today this is reasoning over a question + evidence you provide;
autonomous open-web research is the next capability (a general search/RAG adapter).*

The demo (the "circled structure" case) shows the full epistemic ladder — **information →
connection → explanation{speculation | extrapolation} → hypothesis → insight** — with the
system framing **competing explanations**, synthesizing them into competing **hypotheses**,
and the **Skeptic gate** holding promotion at `HYPOTHESIS` while a leader rests on a single
source. The leader is promoted to `INSIGHT` (the backed conclusion) only once an *independent*
source corroborates it — even though its backing explanation is already the high-confidence
type (`EXTRAPOLATION`). Every object carries provenance and the full reasoning chain is
reported. No network or model API key is required; Phase 1 is deterministic by design (docs 08–09).

### Implemented module map (Phases 1–8 + Model gateway)

| Area | Package | Doc |
|------|---------|-----|
| Canonical schemas | `osintinel/core/schemas/` | [03](docs/03-data-schemas.md) |
| Recursive loop, termination, controller | `osintinel/core/runtime/` | [01](docs/01-architecture.md) |
| Budget governor | `osintinel/core/budget/` | [08](docs/08-compute-token-optimization.md) |
| Epistemic invariants | `osintinel/core/invariants.py` | [09](docs/09-testing-methodology.md) |
| Durable hash-chained ledger + replay | `osintinel/ledger/` | [04](docs/04-knowledge-graph.md) |
| Investigation state (records → ledger) | `osintinel/core/state.py` | [04](docs/04-knowledge-graph.md) |
| Knowledge graph: port, backend, constraints, queries | `osintinel/graph/` | [04](docs/04-knowledge-graph.md) |
| Nine-agent quorum + Speculation Engine | `osintinel/agents/` | [02](docs/02-agents.md) |
| Adapters: cassette transport, content-addressed store, reference + license-gated adapters | `osintinel/adapters/` | [05](docs/05-adapters.md) |
| Investigation Memory: run digests, learned priors, evidence firewall | `osintinel/memory/` | [01](docs/01-architecture.md) |
| Image Investigation pipeline (EXIF codec, solar geometry, ranked geolocation) | `osintinel/pipelines/image_investigation.py`, `adapters/media`, `adapters/compute` | [06](docs/06-roadmap.md) |
| **Geospatial reasoning (multi-constraint narrowing, confidence radius)** | `osintinel/pipelines/geospatial_reasoning.py` | [06](docs/06-roadmap.md) |
| Insight report builder | `osintinel/reporting/` | [03](docs/03-data-schemas.md) |
| Dashboard service + self-contained HTML console | `osintinel/interfaces/api`, `osintinel/interfaces/dashboard` | [06](docs/06-roadmap.md) |
| Model & inference gateway (tiers, providers, record/replay, cost) | `osintinel/inference/` | [11](docs/11-model-inference-architecture.md) |
| **Self-improvement (calibration harness, strategy tuning, firewall audit)** | `osintinel/improvement/` | [06](docs/06-roadmap.md) |
| **Investigation input layer (run your own questions)** | `osintinel/service/` | — |
| **Autonomous web research (search/fetch/extract → evidence)** | `osintinel/adapters/web/` | [05](docs/05-adapters.md) |
| **Free infra/threat-intel adapters (Shodan InternetDB · URLScan · OTX)** | `osintinel/adapters/{infrastructure,threat}` | [05](docs/05-adapters.md) |
| **Front doors: CLI · local web app · MCP server** | `osintinel/interfaces/{cli,web,mcp}` | [10](docs/10-repository-structure.md) |

A later phase can swap the embedded `GraphStore` for a graph-native backend (SQLite/Neo4j)
behind the same port; the ledger, schemas, constraints, and agent contracts are already the
stable interface.

## Architecture Documents

| # | Document | Purpose |
|---|----------|---------|
| 00 | [Overview & Epistemics](docs/00-overview.md) | Vision, foundational separation principle, epistemic integrity layer, knowledge-state framework |
| 01 | [System Architecture](docs/01-architecture.md) | Component topology, orchestration runtime, recursive investigation loop, control & data flow |
| 02 | [Agent Specifications](docs/02-agents.md) | Contracts, responsibilities, I/O schemas, and prompts for every specialist agent |
| 03 | [Data Schemas](docs/03-data-schemas.md) | Canonical message, evidence, hypothesis, provenance, and report schemas |
| 04 | [Knowledge Graph Schema](docs/04-knowledge-graph.md) | Node/edge types, provenance binding, storage backend, query patterns |
| 05 | [Adapter Specifications](docs/05-adapters.md) | Tool adapter interface, registry, capability model, adapter catalogue |
| 06 | [Development Roadmap](docs/06-roadmap.md) | Phased, vertical-slice delivery plan with exit criteria |
| 07 | [Risk Analysis](docs/07-risk-analysis.md) | Epistemic, operational, legal/ethical, and security risks with mitigations |
| 08 | [Compute & Token Optimization](docs/08-compute-token-optimization.md) | Model routing, caching, budget governance, context economy |
| 09 | [Testing Methodology](docs/09-testing-methodology.md) | Test pyramid, epistemic invariants, golden investigations, calibration harness |
| 10 | [Repository Structure](docs/10-repository-structure.md) | Target package layout and module responsibilities |

A condensed, decision-oriented summary lives in
[`docs/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE_DECISIONS.md).

## Core Principles (at a glance)

1. **Foundational Separation** — Aggregation, Connections, Extrapolation/Speculation,
   Hypothesis, and Insight are never merged.
2. **Epistemic Provenance** — Every output is classified (`INFORMATION`, `CONNECTION`,
   `HYPOTHESIS`, `SPECULATION`, `EXTRAPOLATION`, `INSIGHT`) and traceable to source.
3. **Quorum of Specialists** — No agent has full authority; consensus emerges through
   investigation and mandatory skeptical challenge.
4. **Hypothesis Preservation** — Competing hypotheses are never deleted, only re-weighted;
   confidence history is recoverable.
5. **Uncertainty Visibility** — Every report exposes Known Unknowns and Unknown-Unknown
   indicators rather than concealing them.
6. **Lawful OSINT Only** — Publicly available information only; offensive/intrusive capability
   is out of scope by design.

## Safety

OSINTINEL is designed exclusively for **lawful open-source intelligence gathering** on
**publicly available information**. Credential theft, malware, unauthorized access,
authentication bypass, exploitation, and active intrusion are out of scope and explicitly
prohibited. See [`docs/07-risk-analysis.md`](docs/07-risk-analysis.md).
