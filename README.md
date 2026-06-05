# OSINTENAL

**Open Source Intelligence Sentinel** — *Autonomous Aggregation :: Insight via Intelligence
:: Evolution via Recursive Improvement.*

OSINTENAL is a modular, multi-agent intelligence layer that transforms nuanced data
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
live recording is opt-in (`OSINTENAL_RECORD=1`). The *integral storage decision* keeps the
ledger lean: heavy artifacts (e.g. a Wayback page snapshot) are written to a **content-addressed
store** and the ledger holds only a `raw_response` hash/ref — bytes never enter the event log,
so replay stays byte-identical regardless of data volume. Supplemental commercial sources
(Maltego, Pipl, PimEyes, Recorded Future, …) are modeled as **license-gated** adapters, off
unless the operator supplies credentials *and* attests to authorized use. See
[`docs/06-roadmap.md`](docs/06-roadmap.md) for what each phase delivers.

### Quickstart

```bash
pip install -e ".[dev]"        # Python 3.11+; only dependency is pydantic v2

osintenal run                 # run the bundled demo investigation (human-readable report)
osintenal run --json          # same, as a schema-valid InsightReport JSON
osintenal verify              # run → persist ledger → reload → replay; prove byte-identical
                              #   graph + hash chain (Phase 2 durability guarantees)
osintenal audit               # print the evidence chain for the leading insight,
                              #   terminating in sourced INFORMATION nodes
osintenal adapters            # list lawful reference + license-gated supplemental adapters
osintenal slice               # Phase 3: capability-based selection + real (cassette) evidence
                              #   updating a hypothesis; shows the ledger/CAS storage split

pytest -q                      # unit + epistemic-invariant + adapter + replayed scenario tests
```

The demo (the "circled structure" case) shows the full epistemic ladder — **information →
connection → explanation{speculation | extrapolation} → hypothesis → insight** — with the
system framing **competing explanations**, synthesizing them into competing **hypotheses**,
and the **Skeptic gate** holding promotion at `HYPOTHESIS` while a leader rests on a single
source. The leader is promoted to `INSIGHT` (the backed conclusion) only once an *independent*
source corroborates it — even though its backing explanation is already the high-confidence
type (`EXTRAPOLATION`). Every object carries provenance and the full reasoning chain is
reported. No network or model API key is required; Phase 1 is deterministic by design (docs 08–09).

### Implemented module map (Phases 1–3)

| Area | Package | Doc |
|------|---------|-----|
| Canonical schemas | `osintenal/core/schemas/` | [03](docs/03-data-schemas.md) |
| Recursive loop, termination, controller | `osintenal/core/runtime/` | [01](docs/01-architecture.md) |
| Budget governor | `osintenal/core/budget/` | [08](docs/08-compute-token-optimization.md) |
| Epistemic invariants | `osintenal/core/invariants.py` | [09](docs/09-testing-methodology.md) |
| Durable hash-chained ledger + replay | `osintenal/ledger/` | [04](docs/04-knowledge-graph.md) |
| Investigation state (records → ledger) | `osintenal/core/state.py` | [04](docs/04-knowledge-graph.md) |
| Knowledge graph: port, backend, constraints, queries | `osintenal/graph/` | [04](docs/04-knowledge-graph.md) |
| Nine-agent quorum + Speculation Engine | `osintenal/agents/` | [02](docs/02-agents.md) |
| **Adapters: cassette transport, content-addressed store, reference + license-gated adapters** | `osintenal/adapters/` | [05](docs/05-adapters.md) |
| Insight report builder | `osintenal/reporting/` | [03](docs/03-data-schemas.md) |
| CLI | `osintenal/interfaces/cli/` | [10](docs/10-repository-structure.md) |

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

OSINTENAL is designed exclusively for **lawful open-source intelligence gathering** on
**publicly available information**. Credential theft, malware, unauthorized access,
authentication bypass, exploitation, and active intrusion are out of scope and explicitly
prohibited. See [`docs/07-risk-analysis.md`](docs/07-risk-analysis.md).
