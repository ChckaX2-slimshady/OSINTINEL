# 07 — Risk Analysis

Risks are grouped into **epistemic**, **operational**, **legal/ethical & safety**, and
**security** classes. Each lists likelihood × impact, the mitigation, and where in the
architecture the mitigation lives. The system's *raison d'être* is logical coherence
integrity and preserved uncertainty, so epistemic risks are treated as first-class, not
afterthoughts.

## 1. Epistemic Risks (highest priority)

| Risk | L×I | Mitigation | Where |
|------|-----|-----------|-------|
| **False certainty** — system reports high confidence on thin/biased evidence | H×H | Mandatory Skeptic gate; explainable multi-factor confidence; Epistemology Agent flags blind spots; residual_mass + UU-indicators surfaced in every report | doc 02 §7–9, doc 03 §10/§11/§15 |
| **Premature convergence** — collapsing to one hypothesis too early | H×H | Hypothesis Preservation Rule (never delete); Connections must keep ≥2 alternatives + residual mass; Skeptic injects left-field alternatives; planner rewards *discriminating* evidence | doc 02 §2/§3/§7, doc 04 §5 |
| **Fabrication / hallucinated evidence** | M×H | "Never fabricate" is a universal agent rule; missing evidence becomes a Known Unknown; every claim must trace to sourced INFORMATION (auditability invariant) | doc 02 §6, doc 03 §16 |
| **Class confusion** — speculation treated as fact, extrapolation as observation | M×H | Foundational Separation enforced by distinct schemas + ladder constraint at graph write time; speculation quarantined with separate confidence model | doc 00 §3/§4, doc 04 §3/§7 |
| **Confidence miscalibration** | M×M | Versioned, reproducible confidence model; calibration harness; Memory tracks calibration accuracy and tunes it (Phase 8) | doc 02 §8, doc 09 |
| **Source monoculture / correlated sources masquerading as corroboration** | M×H | Explicit `Source` nodes + `independence_group`; source-independence factor; monoculture UU-indicator query; Tool Selection independence bias | doc 04 §6, doc 02 §4/§8 |
| **Confirmation bias in tool selection / planning** | M×M | Planner optimizes information gain not accumulation; Skeptic challenges the leader's supporting evidence specifically | doc 02 §3/§7 |
| **Unknown-unknowns invisible by definition** | M×H | UU *indicators* (residuals, gaps, contradiction clusters, monoculture) computed continuously; reports must expose them | doc 00 §5, doc 03 §11 |

## 2. Operational Risks

| Risk | L×I | Mitigation | Where |
|------|-----|-----------|-------|
| **Runaway cost / infinite loops** | M×H | Budget Governor (token/time/money/request) with hard preemption; no-improvement plateau termination; per-iteration improvement delta required | doc 01 §1/§5, doc 08 |
| **External source flakiness / rate limits / ToS blocks** | H×M | Adapters fail-as-data with fallbacks; rate-limit + polite backoff; effectiveness fed to Memory; replay from cassettes for tests | doc 05 §5, doc 01 §8 |
| **Non-determinism breaking reproducibility** | M×M | Ledger records all external + LLM calls (model id, prompt hash, params, response hash); replay mode | doc 01 §7 |
| **LLM provider/model drift** | M×M | Model tier abstraction + versioned prompts hashed into ledger; golden tests pin behavior; model is swappable | doc 02, doc 08, doc 09 |
| **Data/state corruption** | L×H | Append-only ledger + hash chain; graph rebuildable by replay; integrity check in CI/on load | doc 04 §7/§8 |
| **Scaling beyond single process** | L×M | Bus/graph behind ports; queue + Neo4j swap without changing agent contracts | doc 01 §6/§9 |

## 3. Legal, Ethical & Safety Risks

**Safety constraint (binding):** OSINTINEL is designed **exclusively for lawful open-source
intelligence gathering on publicly available information.**

**Prohibited and out of scope by design:** credential theft · malware deployment ·
unauthorized access · authentication bypass · exploitation · active intrusion.

| Risk | L×I | Mitigation | Where |
|------|-----|-----------|-------|
| **Misuse for intrusion/surveillance harm** | M×H | Capability model excludes any intrusive verb; adapters are public-source only; commercial/PII-heavy tools are license-gated, off by default, and require an authorized-use attestation | doc 05 §4/§5 |
| **ToS / robots violations via scraping** | M×M | Adapters honor robots.txt, ToS, rate limits; non-compliant patterns rejected at review; `license_note` on every provenance record | doc 05 §5 |
| **Privacy harm to individuals (PII, doxxing)** | M×H | Public-only sourcing; PII minimization in storage; person-data adapters gated; reports expose uncertainty to avoid false accusation; operator-use boundaries documented | doc 05 §4, this doc |
| **Over-trust by end users** | M×M | Reports lead with uncertainty (Known Unknowns, UU-indicators, calibration note); speculation clearly segregated and labeled | doc 03 §15 |
| **Licensing/attribution of source data** | L×M | `license_note` + source appendix in every report; provenance retains URL/timestamp/method | doc 03 §1/§15 |

**Operator responsibilities (documented, not enforced by code):** ensure authorization for any
license-gated source, comply with local law on data collection/retention, and treat outputs as
*investigative leads with stated uncertainty*, never as adjudicated fact.

## 4. Security Risks (of the system itself)

| Risk | L×I | Mitigation |
|------|-----|-----------|
| **Prompt injection via fetched content** | H×M | Fetched/external content is treated as *data, not instructions*; agents receive it inside clearly delimited, untrusted envelopes; the runtime (not the LLM) controls tool invocation and budgets, so injected "instructions" cannot trigger actions; Skeptic/Epistemology watch for anomalous content steering |
| **Secret/key leakage (adapter creds)** | M×H | Keys via env/secret store only, never in code or ledger payloads; provenance stores tool id, not credentials; secret scanning in CI |
| **Malicious artifact uploads (image/doc exploits)** | L×H | Parse in sandboxed workers with resource limits; content-addressed storage; no execution of fetched content |
| **Tampering with evidentiary history** | L×H | Hash-chained append-only ledger; integrity verification; self-improvement firewall forbids evidence mutation (Phase 8 audit) |
| **SSRF / network abuse via adapter targets** | M×M | Egress allowlist per adapter; block private IP ranges by default; per-adapter timeouts and concurrency caps |

## 5. Residual Risk & Monitoring

Unknown-unknowns are, by construction, never fully eliminated — the architecture's answer is
to make their *indicators* visible and to keep the possibility space open via hypothesis
preservation and the Speculative Possibility Engine. Phase 8's calibration and false-positive
tracking provide ongoing monitoring; any regression in epistemic-invariant tests (doc 09) is a
release blocker.
