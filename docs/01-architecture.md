# 01 — System Architecture

## 1. Architectural Overview

OSINETENAL is a **quorum of cooperating specialist agents** coordinated by a deterministic
**Orchestration Runtime**, reading and writing a single shared **Knowledge Graph** that is
backed by an append-only **Provenance Ledger**. Tools reach the outside world only through
the **Adapter Framework**. **Investigation Memory** observes runs and informs strategy
without ever mutating evidence.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              INTERFACES                                         │
│            CLI            REST API (FastAPI)            Web Dashboard           │
└───────────────┬──────────────────┬──────────────────────────┬─────────────────┘
                │                  │                          │
                ▼                  ▼                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                       ORCHESTRATION RUNTIME                                     │
│  Investigation Controller · Recursive Loop Engine · Scheduler · Budget Governor│
│  Agent Bus (typed messages) · Termination Evaluator · Knowledge-State Tracker  │
└───────┬───────────────────────────────────────────────────────────┬───────────┘
        │ dispatches typed tasks / collects typed evidence           │
        ▼                                                            ▼
┌───────────────────────────────┐                   ┌────────────────────────────┐
│        AGENT QUORUM           │                   │   ADAPTER FRAMEWORK        │
│  Aggregation · Connections    │   Tool Selection  │  Registry · Capability map │
│  Evidence Planning · Tool Sel.│◀─── requests ────▶│  search/lookup/collect/    │
│  Acquisition · Synthesis      │      tools        │  parse/normalize           │
│  Skeptic · Confidence · Epist.│                   │  Geo · Infra · Identity ·  │
└───────┬───────────────────────┘                   │  Archive · Doc · Media     │
        │ all reads/writes are provenance-bound      └─────────────┬──────────────┘
        ▼                                                          │ external
┌──────────────────────────────────────────────────────────────┐  │ (HTTP, files)
│                     KNOWLEDGE SUBSTRATE                        │  ▼
│  Knowledge Graph  ◀──▶  Provenance Ledger (append-only)        │  Public sources
│  (nodes/edges, hypothesis sets, confidence history)           │
└───────────────────────────────┬──────────────────────────────┘
                                │ observed by (read-only of structure, not evidence)
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                    INVESTIGATION MEMORY                        │
│  Tool/agent effectiveness · Confidence calibration · Planner   │
│  performance · Successful evidence chains · Failed hypotheses  │
└──────────────────────────────────────────────────────────────┘
```

## 2. Component Responsibilities

### 2.1 Orchestration Runtime
The deterministic spine. It is *not* an LLM agent; it is ordinary code that sequences agents,
enforces invariants, and owns control flow. Subcomponents:

- **Investigation Controller** — creates/loads an `Investigation`, holds its configuration
  (budgets, thresholds, domain playbook), and exposes lifecycle (start, pause, resume,
  terminate, replay).
- **Recursive Loop Engine** — runs the Observe→…→Repeat cycle (§4) and records each cycle as
  an immutable iteration record.
- **Agent Bus** — typed, in-process (Phase 1) or queue-backed (later) message transport.
  Every message is a Pydantic model from [03-data-schemas.md](03-data-schemas.md); the bus
  validates `epistemic_class` and provenance on every hop.
- **Scheduler** — decides agent execution order within a cycle; supports parallel fan-out
  for independent acquisition tasks.
- **Budget Governor** — tracks token, wall-clock, money, and request budgets; can preempt the
  loop (see [08-compute-token-optimization.md](08-compute-token-optimization.md)).
- **Termination Evaluator** — applies stop conditions (§5).
- **Knowledge-State Tracker** — thin coordinator that asks the Epistemology Agent to refresh
  Knowns / Known Unknowns / UU-indicators and persists the result on the investigation.

### 2.2 Agent Quorum
Nine specialist agents (full contracts in [02-agents.md](02-agents.md)). Each agent:
is stateless between calls (state lives in the graph), declares an input and output schema,
and may *only* affect the world by returning typed objects to the bus — never by writing the
graph directly. The runtime persists results, which keeps provenance centralized and
auditable.

### 2.3 Knowledge Substrate
- **Knowledge Graph** — graph-native store of entities, evidence, hypotheses, and their
  relationships ([04-knowledge-graph.md](04-knowledge-graph.md)).
- **Provenance Ledger** — append-only event log. Every node/edge mutation, confidence change,
  hypothesis promotion/demotion, and agent action is an event. The graph is a *materialized
  view* over the ledger, which guarantees replay and full auditability. History is immutable.

### 2.4 Adapter Framework
Uniform `search/lookup/collect/parse/normalize` interface over interchangeable tools, with a
capability registry the Tool Selection Agent queries ([05-adapters.md](05-adapters.md)).

### 2.5 Investigation Memory
Learns *strategy* (which tools/agents/plans work) from completed investigations. It reads the
*structure* of past runs and metrics — never the evidence content of the active run in a way
that could bias it — and exposes priors to the planner. Strictly separated from evidence to
prevent contamination (the "may not rewrite evidentiary history" rule).

## 3. Control Flow vs. Data Flow

- **Control flow** is owned exclusively by the Orchestration Runtime (deterministic code).
  Agents never call other agents directly; they return to the bus and the runtime decides
  what happens next. This makes runs reproducible and replayable.
- **Data flow** is one-directional into the substrate: agents emit typed objects → runtime
  validates & persists (as ledger events) → graph view updates → next agent reads the graph
  through query services. No agent holds privileged mutable state.

This separation is the single most important structural decision: it is what makes the system
auditable and what lets the Skeptic and Confidence agents act as genuine gates rather than
advisory side-channels.

## 4. The Recursive Investigation Loop

```
            ┌────────────────────────── ITERATION N ──────────────────────────┐
            │                                                                  │
  ┌─────────▼─────────┐   ┌───────────────┐   ┌───────────────┐   ┌──────────▼─────────┐
  │     OBSERVE        │   │  HYPOTHESIZE  │   │     PLAN       │   │    INVESTIGATE      │
  │ Aggregation Agent  │──▶│ Connections   │──▶│ Evidence Plan  │──▶│ Tool Selection +    │
  │ ingest+normalize   │   │ competing     │   │ + Tool Select  │   │ Acquisition Agents  │
  │ → Observations     │   │ explanations  │   │ (max info-gain)│   │ → Evidence objects  │
  └────────────────────┘   └───────────────┘   └───────────────┘   └──────────┬─────────┘
                                                                               │
  ┌────────────────────┐   ┌───────────────┐   ┌───────────────┐   ┌──────────▼─────────┐
  │ UPDATE KNOWLEDGE    │   │UPDATE CONFID. │   │   CHALLENGE    │   │     SYNTHESIZE      │
  │ STATE               │◀──│ Confidence    │◀──│ Skeptic Agent  │◀──│ Synthesis Agent     │
  │ Epistemology Agent  │   │ Agent (calib.)│   │ (mandatory)    │   │ merge+provenance    │
  └─────────┬──────────┘   └───────────────┘   └───────────────┘   └────────────────────┘
            │
            ▼  Termination Evaluator → continue? ── yes ──▶ ITERATION N+1
                                              └── no ──▶ Insight Report
```

**Per-stage gating:**
- **Synthesize never fabricates.** If evidence is missing, it records a Known Unknown, not a
  guess.
- **Challenge is mandatory.** No major conclusion is promoted to `INSIGHT` or `EXTRAPOLATION`
  without passing through the Skeptic Agent. The Skeptic can spawn new hypotheses and force
  another iteration.
- **Confidence must be explainable.** The Confidence Agent returns a factor breakdown, not a
  scalar; the runtime rejects unexplained confidence.
- **Knowledge-state update closes the loop** by turning residual uncertainty into the next
  iteration's planning input.

Each cycle must *improve understanding* — measured as reduced hypothesis-set entropy,
increased calibrated confidence on the leading hypothesis, or net-new resolved Known
Unknowns. The loop engine records this delta; persistent non-improvement is itself a
termination signal (§5) and a memory signal.

## 5. Termination Conditions

The Termination Evaluator stops the loop when **any** holds:

1. **Confidence threshold reached** — the leading hypothesis exceeds the configured
   calibrated-confidence threshold *and* has survived Skeptic review since last gaining
   confidence.
2. **Resource threshold reached** — any budget (token / time / money / requests) is exhausted
   (Budget Governor).
3. **Probability-score termination** — the hypothesis-set probability distribution reaches a
   configured separation/stability threshold (a clear leader, stable across iterations), at
   which point the system terminates and reports back insights.
4. **No-improvement plateau** — N consecutive iterations with no understanding delta and no
   new discriminating evidence available (planner returns empty).
5. **Operator stop** — explicit pause/terminate.

On termination, the Synthesis Agent emits an **Insight Report**
([03-data-schemas.md](03-data-schemas.md) §Report) and Investigation Memory ingests the run.

## 6. Concurrency & Execution Model

- **Phase 1:** single-process `asyncio`. Agents are async callables; the bus is in-memory;
  the graph and ledger are embedded (SQLite + embedded graph engine). Fully runnable on a
  laptop.
- **Acquisition fan-out:** within the INVESTIGATE stage, independent acquisition tasks run
  concurrently with per-adapter rate limits and a global concurrency cap.
- **Later phases:** the Agent Bus and Acquisition workers can be promoted to a queue
  (e.g., Redis/RQ or NATS) and the graph to a server backend (Neo4j) *without changing agent
  contracts*, because agents only speak the typed schema.

## 7. Determinism, Replay & Idempotency

- Every external call is captured (request + raw response) in the Provenance Ledger, so a run
  can be **replayed** from the ledger without re-hitting the network.
- LLM calls record model id, prompt hash, sampling params, and a response hash; a `replay`
  mode serves recorded responses, enabling deterministic regression tests
  ([09-testing-methodology.md](09-testing-methodology.md)).
- Acquisition is keyed by `(adapter, normalized_query)`; duplicate requests within an
  investigation are de-duplicated and served from the ledger (idempotency + cost control).

## 8. Failure Handling

- **Adapter failure** is evidence about the world, not a crash: it is recorded (with error
  class) and surfaced to the planner, which may pick an alternate tool. Tool effectiveness is
  fed to Memory.
- **Agent failure / malformed output** is caught by bus validation; the runtime retries with
  a repair prompt once, then records a degraded-iteration event and continues. The loop never
  silently drops to a lower epistemic class.
- **Budget exhaustion** triggers graceful termination with a partial, clearly-labeled report.

## 9. Extension Points

| Need | Extend by |
|------|-----------|
| New data source | Add an Adapter implementing the standard interface (05) |
| New domain | Add a domain playbook (priors, cost model) + adapters; core unchanged |
| New reasoning capability | Add/replace an agent honoring its schema contract (02/03) |
| New storage backend | Implement the graph/ledger port; agents unaffected (04) |
| New interface | Consume the REST API / core service layer |

The invariant across all extensions: **typed schemas + provenance + epistemic class** are
non-negotiable contract boundaries.
