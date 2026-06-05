# 00 — Overview, Foundational Separation & Epistemic Integrity

## 1. What OSINETENAL Is

OSINETENAL (Open Source Intelligence Sentinel) is an **Autonomous Evidence Intelligence
Operating System**: a layer that orchestrates specialist agents and tool adapters to
*query, aggregate, investigate, synthesize, and continuously refine* insights from niche,
publicly available data.

It is deliberately **more** than any of its parts:

- More than **data queries** — it reasons about what evidence would *discriminate* between
  explanations, not merely retrieve facts.
- More than a **collection of OSINT scripts** — tools are interchangeable adapters behind a
  uniform contract; investigative paths are never hardcoded.
- More than a **powerful autonomous framework** — its defining feature is *epistemic
  discipline*: it tracks the difference between what is known, connected, hypothesized, and
  speculated, and it can always explain why it believes what it believes.

## 2. Prime Directive

> Use expert methodology to gather niche data through multi-agent orchestration, data
> structuring, and recursive critical analysis.

Every architectural decision in this corpus is justified against this directive and against
the success criterion: **evidence integrity, preserved uncertainty, self-challenge, and
auditable insight** — not raw answer generation.

## 3. Foundational Separation Principle

These five categories **must never be merged**. They form a strict, directional epistemic
ladder. Each rung is a *different kind of object* with its own schema, storage, and
confidence semantics.

```
                 (raises/lowers confidence of)
   AGGREGATION ──▶ CONNECTION ──▶ HYPOTHESIS ──▶ INSIGHT
                                     ▲   ▲
                                     │   │
                          SPECULATION┘   └EXTRAPOLATION
                       (low-confidence)   (high-confidence)
```

The chain of reasoning the system is built to honor:

1. **Aggregation of data is simply information.** Raw, expertly gathered observations.
2. **Information makes connections**, and verifiable connections logically sequenced are
   *possible explanations*.
3. **Explanations strengthen or weaken hypotheses.**
4. **Assumption is low-confidence probability.** **Extrapolation is high-confidence
   probability.**
5. **High-confidence probabilities can be synthesized into hypotheses.**
6. **Competing hypotheses lead to insight.**

No component may bypass these distinctions. In implementation terms this is enforced by:

- **Type separation** — distinct schemas (`Observation`, `Connection`, `Hypothesis`,
  `Speculation`, `Insight`) that cannot be silently coerced into one another (see
  [03-data-schemas.md](03-data-schemas.md)).
- **Transition rules** — an object may only be promoted up the ladder through an explicit,
  logged operation that records the supporting evidence and the agent responsible.
- **Graph-level constraints** — edge types encode the relationship (`supports`,
  `contradicts`, `derived_from`) so that an `INSIGHT` node is *never* directly attached to a
  raw source without the intervening hypothesis/connection chain (see
  [04-knowledge-graph.md](04-knowledge-graph.md)).

## 4. Epistemic Integrity Layer

Every output produced by OSINETENAL — internal or user-facing — carries an explicit
**epistemic class**:

| Class | Definition | Confidence semantics | Produced by |
|-------|------------|----------------------|-------------|
| `INFORMATION` | Expertly aggregated data → nuanced information | Per-observation source confidence | Aggregation Agent |
| `CONNECTION` | Information that is *verifiably* connected; builds confidence scores for competing explanations | Connection strength + verification status | Connections Agent |
| `HYPOTHESIS` | Competing explanations synthesized into a more complex hypothesis | Aggregate probability over supporting/contradicting evidence | Synthesis Agent (proposed by Connections) |
| `SPECULATION` | A hypothesis with a **low** probability confidence score | Separate, explicitly-bounded confidence model | Speculative Possibility Engine |
| `EXTRAPOLATION` | A hypothesis with a **high** probability confidence score | High-confidence probability | Synthesis + Confidence Agents |
| `INSIGHT` | A conclusion with full epistemic provenance backing it | Calibrated, explainable confidence | Synthesis Agent after Skeptic + Confidence review |

**Rules of the layer:**

- Nothing is emitted without a class. The class is a first-class field on every message and
  every graph node (`epistemic_class`).
- **Speculation is quarantined.** It uses a separate confidence model, is always labeled, and
  is never allowed to flow into an `INSIGHT` without being re-derived as a hypothesis with
  supporting evidence. Speculation exists to *expand the investigative possibility space*,
  not to establish truth.
- Promotion across classes is an audited event (who, when, on what evidence). Demotion is
  equally audited.
- Every `INSIGHT` must resolve to a reasoning chain that terminates in `INFORMATION` nodes,
  each of which has provenance. This is the **auditability guarantee**.

## 5. Knowledge-State Framework

Alongside the evidence ladder, the system continuously maintains awareness of three
knowledge domains for every active investigation:

- **Knowns** — information supported by evidence.
- **Known Unknowns** — questions identified but unresolved (the planner's backlog).
- **Unknown-Unknown Indicators** — *conditions* suggesting hidden variables may exist (e.g.,
  unexplained residuals, source monocultures, temporal gaps, contradictions that neither
  hypothesis predicts).

The **Epistemology Agent** owns this framework and updates it on every loop iteration. The
framework is not a static report section — it is live state that *drives planning*: Known
Unknowns become candidate evidence-acquisition tasks; Unknown-Unknown indicators trigger
diversification and skeptical probes.

```
            ┌──────────────────────────────────────────┐
            │              KNOWLEDGE STATE               │
            ├───────────────┬───────────────┬───────────┤
            │    KNOWNS      │ KNOWN UNKNOWNS│  UU-INDIC. │
            │ (evidence-     │ (open ques-   │ (hidden-   │
            │  backed)       │  tions)       │  variable  │
            │                │               │  signals)  │
            └───────┬────────┴───────┬───────┴─────┬─────┘
                    │ feeds          │ feeds       │ triggers
                    ▼                ▼             ▼
               Synthesis        Evidence       Skeptic +
                                Planning       Diversify
```

## 6. Primary Mission Domains

The architecture is **domain-agnostic**. Domain knowledge lives in adapters, prompts, and
optional domain "playbooks" — never in the orchestration core. Reference domains:

- Geolocation · Image investigations · Historical reconstruction
- Corporate infrastructure mapping · Timeline analysis · Public records investigations
- Open-source threat intelligence · Entity resolution · Identity correlation
- Research investigations · Archive reconstruction · Relationship mapping · Event reconstruction

A new domain is onboarded by adding adapters and (optionally) a playbook of priors and
evidence-cost estimates; the core loop, schemas, and epistemic layer are unchanged.

## 7. Design Tenets

1. **Quorum, not autocracy.** No agent possesses full authority. Each contributes evidence;
   consensus emerges through investigation and is gated by mandatory skeptical challenge.
2. **Preserve uncertainty by construction.** Confidence is always a distribution over
   competing hypotheses, never a single collapsed answer.
3. **Provenance or it didn't happen.** Nothing enters the knowledge graph without a source.
4. **Discriminate, don't accumulate.** The planner optimizes for *information gain per
   cost*, prioritizing evidence that separates hypotheses.
5. **Learn strategy, never rewrite history.** Investigation memory improves *how* the system
   investigates; it may never alter recorded evidence or past confidence values.
6. **Lawful and public only.** See safety constraints in [07-risk-analysis.md](07-risk-analysis.md).

## 8. Reading Order

For implementers: read 00 → 01 → 03 → 04 → 02 → 05, then 06–10. Schemas (03) and the graph
(04) are the contract that everything else depends on; agents (02) and adapters (05) are
written against them.
