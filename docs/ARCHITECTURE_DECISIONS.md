# Architecture Decisions (Condensed)

A decision-oriented digest of the OSINTENAL architecture. Each entry: **decision →
rationale → consequence**. Full detail in the numbered docs.

## AD-1 · Deterministic runtime owns control flow; agents only emit typed evidence
**Why:** auditability and replay require that the *order of operations* be code, not model
output. **Consequence:** agents never call each other or write the graph directly; the runtime
persists their results as ledger events. (doc 01 §3)

## AD-2 · Append-only Provenance Ledger; graph is a materialized view
**Why:** "may not rewrite evidentiary history" must be a structural guarantee, not a policy.
**Consequence:** hash-chained events → tamper-evidence, exact replay, corruption recovery by
rebuild. (doc 03 §13, doc 04)

## AD-3 · Foundational Separation: Explanation is a distinct tier between Connection and Hypothesis
**Why:** Speculation and Extrapolation are the *two types of explanation* (low/high
confidence), and **both synthesize into hypotheses** — they are not bands of a hypothesis.
The five categories must never merge; convention is not enough. **Consequence:** a distinct
`Explanation` object (class always `SPECULATION`/`EXTRAPOLATION`); hypotheses are always
`HYPOTHESIS`/`INSIGHT`; the ladder `INFORMATION → CONNECTION → EXPLANATION → HYPOTHESIS →
INSIGHT` is enforced by a tier invariant + ladder-skipping edge rejection at write time.
(doc 00 §3–4, doc 03 §4b/§5, doc 04 §3/§7)

## AD-4 · Hypotheses are preserved, never deleted; confidence_history is append-only
**Why:** resist premature convergence; allow reactivation on new evidence. **Consequence:**
sets carry explicit `residual_mass`; archival/reactivation are logged events. (doc 03 §5,
doc 04 §5)

## AD-5 · Skeptic is a hard gate, not advice
**Why:** "no major conclusion bypasses Skeptic review." **Consequence:** a `blocking` finding
(and a missing independent-corroboration requirement) mechanically prevents promotion of a
hypothesis to INSIGHT until resolved. (doc 02 §7, doc 09 §3.5)

## AD-6 · Confidence is explainable and (mostly) deterministic
**Why:** "confidence must be explainable." **Consequence:** factors are computed in code; the
LLM only authors the explanation; model version recorded for calibration. (doc 02 §8, doc 03 §10)

## AD-7 · The Speculative Possibility Engine is kept separate from conclusions
**Why:** speculation expands the possibility space, it does not establish truth. (Distinct
from the in-flow `SPECULATION` explanation type, which *does* feed hypotheses.)
**Consequence:** possibility-engine items use a separate confidence model, never enter set
normalization, and never flow into insights un-re-derived. (doc 02 §10, doc 03 §6)

## AD-8 · Planner optimizes information-gain-per-cost (discriminate, don't accumulate)
**Why:** fewer, sharper iterations → integrity *and* cost control. **Consequence:** the
biggest token lever is epistemic, not infrastructural. (doc 02 §3, doc 08 §6)

## AD-9 · Tools are interchangeable adapters chosen by capability
**Why:** "never hardcode investigative paths." **Consequence:** uniform
search/lookup/collect/parse/normalize; selection by capability + independence + effectiveness.
(doc 05)

## AD-10 · Explicit `Source` nodes with independence groups
**Why:** make source independence and source monoculture *computable*, not guessed.
**Consequence:** a key Confidence factor and a key UU-indicator are graph queries. (doc 04 §6)

## AD-11 · Knowledge-State (Knowns / Known Unknowns / UU-indicators) is live, planner-driving state
**Why:** preserve uncertainty visibility and turn it into next actions. **Consequence:** the
Epistemology Agent refreshes it every iteration; reports must expose it. (doc 00 §5, doc 02 §9)

## AD-12 · Investigation Memory learns strategy behind an evidence firewall
**Why:** improve *how* we investigate without contaminating *what* we found.
**Consequence:** Memory reads metrics/structure and feeds priors; it cannot mutate evidence or
past confidence. (doc 06 Phase 4)

## AD-13 · Model tiering + prompt caching + replay
**Why:** a recursive multi-agent loop is token-hungry. **Consequence:** route to cheapest
adequate tier; cache stable prompts; replay recorded calls for deterministic, free tests.
(doc 08)

## AD-14 · Python + asyncio + Pydantic; embedded graph (Phase 1) behind ports → Neo4j (later)
**Why:** OSINT tooling ecosystem + laptop-runnable Phase 1 + clean scale path.
**Consequence:** swap backends/transport without touching agent contracts. (doc 01 §6/§9, doc 04 §1)

## AD-15 · Lawful, public-source-only; intrusive capability excluded by design
**Why:** binding safety constraint. **Consequence:** capability model has no intrusive verbs;
commercial/PII tools are license-gated and off by default. (doc 05 §4, doc 07 §3)

## AD-16 · Vertical slices over architectural completeness
**Why:** "working intelligence is preferable to perfect architecture." **Consequence:** every
phase ships a runnable system with a proving demo; schemas+loop first, then storage, adapters,
memory, the image vertical, UI, self-improvement. (doc 06)

## Open Questions (to revisit during implementation)
- Embedded graph engine choice (Kùzu vs. SQLite property-graph layer) — benchmark in Phase 2.
- Whether the Agent Bus moves to a queue in Phase 5 or later depending on acquisition volume.
- Confidence-model functional form (linear vs. learned) — driven by calibration data (Phase 8).
- Reverse-image / similarity adapter sourcing under lawful, ToS-compliant constraints.
