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

**Phase 0 — Architecture.** This repository currently contains the *complete architecture
design*. Per the Prime Directive, no implementation code is written until the architecture is
complete and internally consistent. See [`docs/`](docs/) for the full design corpus and
[`docs/06-roadmap.md`](docs/06-roadmap.md) for the path to a runnable Phase 1.

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
