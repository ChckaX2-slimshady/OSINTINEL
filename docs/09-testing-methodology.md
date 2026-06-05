# 09 — Testing Methodology

Testing a probabilistic, LLM-driven investigator requires more than ordinary unit tests. We
test on **three axes**: (1) *correctness* of deterministic machinery, (2) *epistemic
invariants* that must hold regardless of model output, and (3) *calibration & quality* of the
investigative behavior over time. The north star: prove the system **maintains evidence
integrity, preserves uncertainty, challenges itself, and stays auditable.**

## 1. Test Pyramid

```
        ┌───────────────────────────────────────────┐
        │  Calibration / Quality (golden, periodic)  │  slowest, model-in-loop
        ├───────────────────────────────────────────┤
        │  Scenario / Integration (replayed)         │  deterministic via cassettes
        ├───────────────────────────────────────────┤
        │  Epistemic Invariant tests (always-on)     │  property-based, fast
        ├───────────────────────────────────────────┤
        │  Unit tests (schemas, adapters, math)      │  fastest, pure
        └───────────────────────────────────────────┘
```

## 2. Unit Tests (deterministic)
- **Schema tests:** every model in doc 03 round-trips, rejects malformed input, enforces
  enums/ranges. Provenance is required and validated.
- **Adapter `parse`/`normalize`:** pure functions against recorded fixtures; assert
  schema-valid `Observation`/`EvidenceObject` with complete provenance (doc 05 §6).
- **Confidence math:** factor computations and set normalization are exact and reproducible
  given fixed inputs (the LLM never produces the numbers).
- **Graph/ledger:** write-time constraints, hash-chain linkage, materialized-view rebuild.

## 3. Epistemic Invariant Tests (the heart of the suite)

Property-based tests (Hypothesis-style) that must hold for **any** investigation state — these
encode the Foundational Separation and the brief's non-negotiables. Each maps to doc 03 §16.

1. **Provenance-or-nothing:** no persisted node/edge lacks valid provenance + ledger event.
2. **Auditability:** every `INSIGHT` resolves to a reasoning chain terminating in
   `INFORMATION` nodes with non-derived provenance.
3. **Hypothesis preservation:** `confidence_history` is append-only; no operation deletes a
   hypothesis; archival/reactivation only.
4. **No premature collapse:** a `HypothesisSet` always retains ≥1 active member and, while
   uncertainty remains, residual_mass + alternatives persist; convergence requires the Skeptic
   gate to have run.
5. **Skeptic gate:** no promotion of a hypothesis to `INSIGHT` while an unresolved `blocking`
   finding targets it, or without independent corroboration (inject a blocking finding →
   assert promotion refused).
6. **Foundational Separation (tier integrity):** an `Explanation` is `SPECULATION`/
   `EXTRAPOLATION`; a `Hypothesis` is `HYPOTHESIS`/`INSIGHT`; the two tiers are never merged.
   Speculation-engine confidences never enter set normalization; ladder-skipping edges are
   rejected.
7. **Explainable confidence:** every confidence value has a factor breakdown + method version;
   bare scalars are rejected.
8. **History immutability:** ledger events and confidence history cannot be mutated; hash chain
   verifies.

These run on every commit and are **release blockers** — they must stay green even as models
and prompts change.

## 4. Scenario / Integration Tests (replayed, deterministic)

Full-loop runs made deterministic by **replay**: all external calls and LLM responses are
served from recorded cassettes (doc 01 §7, doc 08 §4). This lets us assert end-to-end behavior
without network or model nondeterminism.

- **Golden investigations:** curated cases with a known evidentiary structure. Assert: correct
  competing hypotheses surfaced, contradicting evidence present, Known Unknowns populated,
  report schema-valid, and the *reasoning chain* is sound — not necessarily a single "right
  answer," but a defensible, sourced one.
- **Adversarial fixtures:** cases seeded with a misleading dominant source, correlated
  sources, or a planted contradiction. Assert the Skeptic catches it, source-monoculture
  UU-indicator fires, and confidence does **not** spike.
- **Prompt-injection fixtures:** fetched content containing instructions ("ignore previous…").
  Assert the runtime ignores it (tools/budgets unaffected) and the content is treated as data.
- **Failure-injection:** adapter errors, budget exhaustion → assert graceful degradation and a
  labeled partial report.

## 5. Calibration & Quality Harness (periodic, model-in-loop)

Run against a frozen benchmark suite, not on every commit (cost).
- **Calibration:** over many golden cases, do stated confidences match empirical correctness?
  Produce reliability diagrams / Brier scores per confidence model version. Phase 8 uses this
  to tune the Confidence model. Regression in calibration is tracked over releases.
- **False-positive / false-negative rates** of leading conclusions.
- **Planner efficiency:** realized vs. predicted information gain; iterations-to-termination;
  cost-per-resolved-investigation (also doc 08 §8).
- **Agent ablations:** disable the Skeptic / shuffle the planner and confirm quality drops —
  proves each specialist earns its place.

## 6. Determinism, Fixtures & Tooling
- **Cassettes** (VCR-style) for every external + LLM call; recorded once, replayed in CI.
- **Seeded RNG** and pinned model ids/params; prompt versions hashed and asserted.
- **Synthetic graph factories** for property-based tests (generate arbitrary valid/invalid
  states to attack the invariants).
- Framework: `pytest` + `hypothesis` (property tests) + `pytest-recording`/custom cassette
  layer; `mypy`/`pyright` strict on schemas; `ruff` lint.

## 7. CI Gates
On every PR: unit + epistemic-invariant + replayed scenario tests + lint + type-check +
ledger hash-chain integrity + secret scanning. Live adapter smoke tests are **network-gated**
and excluded from default CI (opt-in job). Calibration harness runs on a schedule / pre-release.

## 8. What "Passing" Means
A green build proves the *machinery and the epistemic guarantees* hold. Investigative *quality*
is tracked separately and continuously via the calibration harness, because — consistent with
the Prime Directive — success is measured by **logical coherence integrity**, preserved
uncertainty, self-challenge, and auditability, not by producing a confident answer.
