# OSINETENAL

**Open Source Intelligence Sentinel** — an Autonomous Evidence Intelligence Operating System.

OSINETENAL is a modular, multi-agent intelligence layer that transforms nuanced data
aggregated from expert sources and methodology into auditable, uncertainty-aware insights
through recursive investigation, adaptive planning, provenance tracking, structured
skepticism, and epistemic scrutiny.

> **Prime Directive** — Use expert methodology to gather niche data through multi-agent
> orchestration, data structuring, and recursive critical analysis.

> **Success is measured** not by answer generation, but by the system's ability to maintain
> evidence integrity, preserve uncertainty, challenge itself, and produce auditable
> intelligence insights.

---

## Status

**Phase 0 — Architecture: complete.** The full design corpus lives in [`docs/`](docs/).

**Phase 1 — Core orchestration framework: implemented & runnable.** The nine-agent quorum,
the recursive investigation loop, budget governance, an append-only hash-chained provenance
ledger, the epistemic-invariant guards, and a CLI are all in place and exercised by a
deterministic, offline, replayable demo investigation. See
[`docs/06-roadmap.md`](docs/06-roadmap.md) for what each phase delivers.

### Quickstart

```bash
pip install -e ".[dev]"        # Python 3.11+; only dependency is pydantic v2

osinetenal run                 # run the bundled demo investigation (human-readable report)
osinetenal run --json          # same, as a schema-valid InsightReport JSON
osinetenal verify              # run it and verify the provenance ledger hash chain

pytest -q                      # unit + epistemic-invariant + replayed scenario tests
```

The demo (the "circled structure" case) shows the system framing **competing hypotheses**,
the **Skeptic gate** holding promotion at `HYPOTHESIS` while a leader rests on a single
source, and promotion to `EXTRAPOLATION` only once an *independent* source corroborates it —
with every object carrying provenance and the full reasoning chain reported. No network or
model API key is required; Phase 1 is deterministic by design (docs 08–09).

### Implemented module map (Phase 1)

| Area | Package | Doc |
|------|---------|-----|
| Canonical schemas | `osinetenal/core/schemas/` | [03](docs/03-data-schemas.md) |
| Recursive loop, termination, controller | `osinetenal/core/runtime/` | [01](docs/01-architecture.md) |
| Budget governor | `osinetenal/core/budget/` | [08](docs/08-compute-token-optimization.md) |
| Epistemic invariants | `osinetenal/core/invariants.py` | [09](docs/09-testing-methodology.md) |
| Append-only provenance ledger | `osinetenal/ledger/` | [04](docs/04-knowledge-graph.md) |
| Investigation state (graph stand-in) | `osinetenal/core/state.py` | [04](docs/04-knowledge-graph.md) |
| Nine-agent quorum + Speculation Engine | `osinetenal/agents/` | [02](docs/02-agents.md) |
| Adapter framework + deterministic stub | `osinetenal/adapters/` | [05](docs/05-adapters.md) |
| Insight report builder | `osinetenal/reporting/` | [03](docs/03-data-schemas.md) |
| CLI | `osinetenal/interfaces/cli/` | [10](docs/10-repository-structure.md) |

Phase 2 replaces the in-memory state store with the graph-native backend behind the same
contract; the ledger, schemas, and agent contracts are already the Phase-2 interface.

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

OSINETENAL is designed exclusively for **lawful open-source intelligence gathering** on
**publicly available information**. Credential theft, malware, unauthorized access,
authentication bypass, exploitation, and active intrusion are out of scope and explicitly
prohibited. See [`docs/07-risk-analysis.md`](docs/07-risk-analysis.md).
