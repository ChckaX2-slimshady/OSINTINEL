# 10 — Repository Structure

Target layout for implementation. It mirrors the architecture: a deterministic **core**
(runtime, schemas, graph, ledger, budget), a stateless **agents** quorum, an **adapters**
framework, **memory**, **interfaces**, and **docs/tests**. The boundaries here are the same
ports described in docs 01–05, so each top-level package can be built and tested in isolation.

```
OSINTENAL/
├── README.md
├── pyproject.toml                 # packaging, deps, tool config (ruff/pyright/pytest)
├── LICENSE
├── .env.example                   # adapter keys (never committed), provider config
├── docs/                          # this architecture corpus (Phase 0 deliverable)
│   ├── 00-overview.md … 10-repository-structure.md
│   └── ARCHITECTURE_DECISIONS.md
│
├── osintenal/                    # the package
│   ├── __init__.py
│   ├── config.py                  # budgets, thresholds, model-tier → model id map
│   │
│   ├── core/                      # deterministic spine (NO LLM calls here)
│   │   ├── schemas/               # doc 03 — Pydantic models (the contract)
│   │   │   ├── enums.py           # EpistemicClass, explanation_type_for_confidence
│   │   │   ├── provenance.py
│   │   │   ├── observation.py     # Observation, EvidenceObject
│   │   │   ├── explanation.py     # Explanation (SPECULATION/EXTRAPOLATION tier, doc 03 §4b)
│   │   │   ├── hypothesis.py      # Hypothesis, HypothesisSet, SpeculationItem
│   │   │   ├── planning.py        # EvidenceRequest, ToolPlan
│   │   │   ├── findings.py        # SkepticFinding, ConfidenceAssessment
│   │   │   ├── epistemics.py      # KnowledgeStateSnapshot
│   │   │   ├── messages.py        # AgentMessage, LedgerEvent
│   │   │   ├── investigation.py   # Investigation
│   │   │   └── report.py          # InsightReport
│   │   ├── runtime/               # doc 01
│   │   │   ├── controller.py      # Investigation lifecycle
│   │   │   ├── loop.py            # Recursive Loop Engine (Observe→…→Repeat)
│   │   │   ├── bus.py             # typed Agent Bus + validation
│   │   │   ├── scheduler.py       # agent ordering, acquisition fan-out
│   │   │   ├── termination.py     # Termination Evaluator (doc 01 §5)
│   │   │   └── knowledge_state.py # Knowledge-State Tracker coordinator
│   │   ├── budget/                # doc 08
│   │   │   └── governor.py
│   │   ├── invariants.py          # epistemic invariants enforced at runtime (doc 03 §16)
│   │   └── ids.py                 # UUIDv7, content hashing
│   │
│   ├── graph/                     # doc 04 — materialized view over the ledger (Phase 2)
│   │   ├── store.py               # GraphStore port + Node/Edge value types
│   │   ├── builder.py             # build_graph(state): project state into the graph
│   │   ├── view.py                # read-only GraphView exposing the doc-04 §6 queries
│   │   ├── constraints.py         # write-time integrity (ladder, provenance, quarantine)
│   │   ├── queries.py             # evidence-chain/independence/monoculture/contradiction
│   │   └── backends/
│   │       ├── memory.py          # embedded in-memory store (Phase 2 default)
│   │       └── neo4j.py           # graph-native backend (later phase, same port)
│   │
│   ├── ledger/                    # doc 03 §13, doc 04 §1 — durable, append-only (Phase 2)
│   │   ├── ledger.py              # hash-chained event log + JSONL save/load
│   │   └── replay.py              # rebuild byte-identical state/graph from the event log
│   │
│   ├── agents/                    # doc 02 — stateless specialists
│   │   ├── base.py                # Agent protocol, AgentContext, AgentResult
│   │   ├── llm.py                 # model-tier client, prompt caching, replay hook (doc 08)
│   │   ├── aggregation/           # each: agent.py + prompt.md (versioned, hashed)
│   │   ├── connections/           # frames competing EXPLANATIONS
│   │   ├── evidence_planning/
│   │   ├── tool_selection/
│   │   ├── acquisition/           # Information Acquisition Agent
│   │   ├── synthesis/             # synthesizes explanations -> hypotheses; merges evidence
│   │   ├── skeptic/
│   │   ├── confidence/            # factors + explanation re-typing + INSIGHT promotion
│   │   ├── epistemology/
│   │   └── speculation/           # Speculative Possibility Engine (separate from conclusions)
│   │
│   ├── adapters/                  # doc 05 — tool framework
│   │   ├── base.py                # Adapter protocol (search/lookup/collect/parse/normalize)
│   │   ├── registry.py            # capability → adapters, cost/effectiveness priors
│   │   ├── capabilities.py        # CapabilityTag enum
│   │   ├── cassettes.py           # record/replay external calls (VCR-style)
│   │   ├── geospatial/            # nominatim, overpass, mapillary, satellite…
│   │   ├── infrastructure/        # dns, ct, asn, amass, subfinder
│   │   ├── identity/              # sherlock, profile discovery
│   │   ├── archives/              # wayback, archive_today, wikimedia, wikidata
│   │   ├── documents/             # ocr, metadata, pdf
│   │   ├── media/                 # exiftool, reverse_image, similarity
│   │   ├── reference/             # encyclopedic, open datasets, symbolic compute
│   │   └── commercial/            # license-gated, off by default (doc 05 §4)
│   │
│   ├── pipelines/                 # domain verticals built on the core loop
│   │   ├── image_investigation.py # doc 06 Phase 5 (EXIF→…→geo hypotheses)
│   │   └── geospatial_reasoning.py# doc 06 Phase 6
│   │
│   ├── memory/                    # doc 06 Phase 4 — strategy only, evidence firewall
│   │   ├── store.py               # runs, metrics, effectiveness, calibration records
│   │   ├── priors.py              # priors exposed to planner / tool selector
│   │   └── firewall.py            # enforces no evidence/ledger mutation
│   │
│   ├── reporting/
│   │   └── insight_report.py      # assemble InsightReport (doc 03 §15)
│   │
│   ├── playbooks/                 # optional per-domain priors & cost models (doc 00 §6)
│   │   └── README.md
│   │
│   └── interfaces/
│       ├── cli/                   # `osintenal run|replay|report|graph` (Phase 1)
│       ├── api/                   # FastAPI REST (Phase 7)
│       └── dashboard/             # web UI: graph/timeline/replay/evolution (Phase 7)
│
├── tests/                         # doc 09
│   ├── unit/                      # schemas, adapters, confidence math, graph/ledger
│   ├── epistemic/                 # property-based invariant tests (release blockers)
│   ├── scenario/                  # replayed full-loop golden + adversarial cases
│   ├── calibration/               # periodic quality/calibration harness
│   ├── fixtures/                  # cassettes, golden investigations, synthetic graphs
│   └── conftest.py
│
├── benchmarks/                    # frozen suites for calibration & cost tracking (doc 08/09)
├── scripts/                       # dev tooling, cassette recording, integrity checks
└── .github/workflows/             # CI gates (doc 09 §7)
```

## Module-Boundary Rules
1. **`core/` never imports `agents/` or `adapters/`** — the spine depends only on schemas and
   ports. Dependencies point inward (schemas are the center).
2. **Agents import schemas + ports only**, never a concrete backend or another agent.
3. **Adapters import schemas only** and emit canonical objects; no agent logic.
4. **`memory/` may read run metrics/structure but is firewalled from mutating evidence or the
   ledger** (doc 06 Phase 4 exit criterion).
5. **Interfaces depend on a thin service layer over the controller**, not on internals.

This structure makes each phase of doc 06 a set of additions within existing package
boundaries rather than a rewrite, and keeps the swappable ports (graph backend, bus transport,
model tier, adapters) exactly where docs 01–05 promise them.
