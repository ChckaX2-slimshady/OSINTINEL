# 03 — Data Schemas (Canonical Contract)

These schemas are the contract that the orchestration runtime, agents, graph, and adapters
are all written against. They are presented as JSON Schema / typed-shape sketches intended to
be realized as **Pydantic v2 models** in `osinetenal/core/schemas/`. Field names here are
normative.

> Convention: all ids are UUIDv7 strings (time-sortable). All timestamps are RFC 3339 UTC.
> `confidence` is always a float in `[0.0, 1.0]`. Every persisted object carries `provenance`.

## 0. Shared Enums

```jsonc
EpistemicClass = "INFORMATION" | "CONNECTION" | "HYPOTHESIS"
               | "SPECULATION" | "EXTRAPOLATION" | "INSIGHT"

KnowledgeState = "KNOWN" | "KNOWN_UNKNOWN" | "UNKNOWN_UNKNOWN_INDICATOR"

AcquisitionMethod = "api" | "scrape" | "file_upload" | "archive_fetch"
                  | "reverse_image" | "computation" | "human_provided" | "derived"

AgentName = "aggregation" | "connections" | "evidence_planning" | "tool_selection"
          | "acquisition" | "synthesis" | "skeptic" | "confidence" | "epistemology"
```

## 1. Provenance (attached to everything)

The single most important schema. **Nothing enters the graph without it.**

```jsonc
Provenance = {
  "source": "string",            // human-readable source name / publisher
  "url": "string | null",        // canonical URL if applicable
  "timestamp": "rfc3339",        // when the datum was observed/acquired
  "acquisition_method": AcquisitionMethod,
  "tool_used": "string | null",  // adapter id, e.g. "osm.overpass"
  "agent_responsible": AgentName,
  "confidence": 0.0,             // source/acquisition confidence
  "investigation_id": "uuid",
  "ledger_event_id": "uuid",     // back-pointer into the append-only ledger
  "derived_from": ["uuid"],      // upstream object ids (evidence chain), may be empty
  "content_hash": "sha256",      // hash of raw captured content for integrity
  "license_note": "string | null"// usage/licensing note for the source
}
```

Every conclusion must be traceable to originating evidence via `derived_from` chains that
terminate in `INFORMATION` objects with a non-derived `Provenance`.

## 2. Observation (Aggregation Agent output) — `INFORMATION`

Matches the prompt's Aggregation output schema, extended with the mandatory envelope.

```jsonc
Observation = {
  "observation_id": "uuid",
  "epistemic_class": "INFORMATION",
  "source": "string",
  "type": "string",              // e.g. "exif", "ocr_text", "transcript", "metadata_field"
  "content": "any",              // normalized value (string/object/number)
  "modality": "image|video|audio|document|web|dataset|other",
  "confidence": 1.0,
  "provenance": Provenance,
  "tags": ["string"]
}
```

## 3. EvidenceObject (Acquisition Agent output)

Structured result of acquiring evidence in service of a plan.

```jsonc
EvidenceObject = {
  "evidence_id": "uuid",
  "epistemic_class": "INFORMATION",
  "kind": "map|image|satellite|public_record|infrastructure|archive|document|dataset|reference",
  "payload_ref": "string",       // path/URI to stored artifact (content-addressed)
  "summary": "string",           // normalized, model-readable digest
  "structured": { },             // adapter-normalized fields
  "supports": ["hypothesis_id"], // hypotheses this tends to support (with weights below)
  "contradicts": ["hypothesis_id"],
  "weights": { "hypothesis_id": 0.0 }, // signed strength in [-1,1] per related hypothesis
  "addresses_query": "evidence_request_id | null",
  "confidence": 0.0,
  "provenance": Provenance
}
```

## 4. Connection (Connections Agent) — `CONNECTION`

A verifiable link between information items that forms part of a possible explanation.

```jsonc
Connection = {
  "connection_id": "uuid",
  "epistemic_class": "CONNECTION",
  "subject_ref": "node_id",
  "object_ref": "node_id",
  "relation": "owns|associated_with|located_at|referenced_by|observed_in|...",
  "verification": "verified|plausible|unverified|refuted",
  "strength": 0.0,              // [0,1]
  "rationale": "string",
  "provenance": Provenance
}
```

## 5. Hypothesis (preserved, never deleted) — `HYPOTHESIS`/`SPECULATION`/`EXTRAPOLATION`

The central object of the system. A hypothesis lives in a **HypothesisSet** (competing
explanations for one question). Its `epistemic_class` is derived from its confidence band but
stored explicitly for auditing.

```jsonc
Hypothesis = {
  "hypothesis_id": "uuid",
  "set_id": "uuid",              // the competing-explanations group it belongs to
  "statement": "string",         // e.g. "summit marker"
  "epistemic_class": "HYPOTHESIS|SPECULATION|EXTRAPOLATION|INSIGHT",
  "confidence": 0.35,            // current calibrated probability within the set
  "status": "active|archived|reactivated",
  "supporting_evidence": ["evidence_id"],
  "contradicting_evidence": ["evidence_id"],
  "confidence_history": [        // append-only; NEVER overwritten
    { "iteration": 0, "confidence": 0.35, "delta_reason": "string",
      "by_agent": AgentName, "timestamp": "rfc3339", "ledger_event_id": "uuid" }
  ],
  "skeptic_findings": ["finding_id"],
  "origin": "connections|skeptic|speculation|reactivation",
  "provenance": Provenance
}

HypothesisSet = {
  "set_id": "uuid",
  "question": "string",          // the discriminandum, e.g. "What is the circled structure?"
  "hypotheses": ["hypothesis_id"],
  "normalized": true,            // confidences across active hypotheses sum to <= 1
  "residual_mass": 0.0,          // probability reserved for "none of the above" (UU signal)
  "provenance": Provenance
}
```

**Hypothesis Preservation Rule (enforced):** confidence may only be *raised, lowered, or
archived* — never deleted. `confidence_history` is append-only. Archived hypotheses may be
`reactivated` when new evidence arrives; reactivation is a logged event. `residual_mass`
holds the explicit "none of the current hypotheses" probability and is a first-class
Unknown-Unknown indicator.

## 6. SpeculationItem (Speculative Possibility Engine) — `SPECULATION`

Quarantined, separate confidence model, never auto-promoted.

```jsonc
SpeculationItem = {
  "speculation_id": "uuid",
  "epistemic_class": "SPECULATION",
  "statement": "string",
  "speculative_confidence": 0.0, // SEPARATE model; not comparable to hypothesis confidence
  "evidence_limitations": ["string"],   // explicit statement of what is missing
  "would_promote_if": ["string"],        // evidence that would justify promotion to Hypothesis
  "provenance": Provenance
}
```

## 7. EvidenceRequest (Evidence Planning Agent output)

The planner's discriminating-evidence proposals.

```jsonc
EvidenceRequest = {
  "evidence_request_id": "uuid",
  "question_ref": "set_id",
  "description": "string",                 // what evidence to get
  "discriminates_between": ["hypothesis_id"],
  "expected_information_gain": 0.0,        // est. bits / entropy reduction
  "estimated_cost": { "tokens": 0, "money_usd": 0.0, "seconds": 0, "requests": 0 },
  "score": 0.0,                            // info_gain / cost (planner ranking key)
  "candidate_capabilities": ["capability_tag"], // for Tool Selection Agent
  "priority": 0,
  "provenance": Provenance
}
```

## 8. ToolPlan (Tool Selection Agent output)

```jsonc
ToolPlan = {
  "tool_plan_id": "uuid",
  "evidence_request_id": "uuid",
  "selected_adapter": "string",     // e.g. "wayback.cdx"
  "operation": "search|lookup|collect|parse|normalize",
  "arguments": { },
  "fallback_adapters": ["string"],
  "rationale": "string",
  "expected_cost": { "tokens": 0, "money_usd": 0.0, "seconds": 0, "requests": 0 },
  "provenance": Provenance
}
```

## 9. SkepticFinding (Skeptic Agent) 

```jsonc
SkepticFinding = {
  "finding_id": "uuid",
  "target_ref": "hypothesis_id | insight_id | connection_id",
  "category": "contradiction|hidden_assumption|reasoning_weakness|source_dependency|alt_explanation|overfit",
  "description": "string",
  "severity": "low|medium|high|blocking",
  "proposed_alternative": "hypothesis_statement | null",
  "evidence_refs": ["evidence_id"],
  "resolved": false,
  "provenance": Provenance
}
```

A `blocking` finding prevents promotion to `INSIGHT`/`EXTRAPOLATION` until resolved or
explicitly accepted-with-caveat (logged).

## 10. ConfidenceAssessment (Confidence Agent) — explainable, never a bare scalar

```jsonc
ConfidenceAssessment = {
  "assessment_id": "uuid",
  "target_ref": "hypothesis_id",
  "confidence": 0.0,
  "factors": {
    "source_quality": 0.0,
    "evidence_diversity": 0.0,
    "evidence_quantity": 0.0,
    "contradiction_penalty": 0.0,
    "source_independence": 0.0,
    "temporal_relevance": 0.0
  },
  "method": "string",            // formula/version used; must be reproducible
  "explanation": "string",       // natural-language justification of the score
  "calibration_model_version": "string",
  "provenance": Provenance
}
```

## 11. KnowledgeStateSnapshot (Epistemology Agent)

```jsonc
KnowledgeStateSnapshot = {
  "snapshot_id": "uuid",
  "investigation_id": "uuid",
  "iteration": 0,
  "knowns": [ { "statement": "string", "evidence_refs": ["evidence_id"] } ],
  "known_unknowns": [ { "question": "string", "blocking": false,
                        "suggested_capabilities": ["capability_tag"] } ],
  "unknown_unknown_indicators": [
    { "signal": "source_monoculture|temporal_gap|unexplained_residual|contradiction_cluster|...",
      "detail": "string", "severity": "low|medium|high" }
  ],
  "hidden_assumptions": ["string"],
  "provenance": Provenance
}
```

## 12. AgentMessage (the bus envelope)

Every inter-agent message rides this envelope; the bus validates it on every hop.

```jsonc
AgentMessage = {
  "message_id": "uuid",
  "investigation_id": "uuid",
  "iteration": 0,
  "from_agent": AgentName | "runtime",
  "to_agent": AgentName | "runtime",
  "intent": "task|result|challenge|error",
  "epistemic_class": EpistemicClass | null,  // class of the payload, if it is evidence
  "payload": { },                            // one of the schemas above
  "payload_type": "Observation|EvidenceObject|Hypothesis|...",
  "budget_snapshot": { "tokens_used": 0, "money_usd": 0.0, "seconds": 0 },
  "timestamp": "rfc3339"
}
```

## 13. LedgerEvent (append-only provenance ledger)

```jsonc
LedgerEvent = {
  "event_id": "uuid",            // UUIDv7, total order
  "investigation_id": "uuid",
  "iteration": 0,
  "type": "node_add|edge_add|confidence_change|hypothesis_promote|hypothesis_archive|"
        + "hypothesis_reactivate|agent_call|tool_call|external_response|report_emit",
  "actor": AgentName | "runtime" | "adapter:<id>",
  "payload": { },                // type-specific; includes content hashes
  "prev_event_hash": "sha256",   // hash chain for tamper-evidence
  "event_hash": "sha256",
  "timestamp": "rfc3339"
}
```

The graph is a **materialized view** over this log. Replaying events reconstructs the graph
exactly. Events are immutable; the hash chain makes evidentiary history tamper-evident — this
operationalizes "the system may not rewrite evidentiary history."

## 14. Investigation

```jsonc
Investigation = {
  "investigation_id": "uuid",
  "title": "string",
  "objective": "string",
  "domain": "string | null",     // optional playbook selector
  "inputs": [ /* Observation seeds, uploaded artifacts, prompts */ ],
  "config": {
    "confidence_threshold": 0.85,
    "probability_separation_threshold": 0.5,
    "no_improvement_patience": 3,
    "budgets": { "tokens": 0, "money_usd": 0.0, "seconds": 0, "requests": 0 }
  },
  "status": "created|running|paused|terminated|completed|error",
  "current_iteration": 0,
  "hypothesis_sets": ["set_id"],
  "knowledge_state": "snapshot_id",
  "report_ref": "report_id | null",
  "created_at": "rfc3339"
}
```

## 15. InsightReport (final deliverable) — `INSIGHT`

Mirrors the Insight Reports Framework. Every report **exposes** uncertainty.

```jsonc
InsightReport = {
  "report_id": "uuid",
  "investigation_id": "uuid",
  "epistemic_class": "INSIGHT",
  "executive_summary": "string",
  "information_summary": "string",
  "connective_probability_scores": [
    { "set_id": "uuid", "question": "string",
      "ranked_hypotheses": [ { "hypothesis_id": "uuid", "statement": "string",
                               "confidence": 0.0, "epistemic_class": "..." } ],
      "residual_mass": 0.0 }
  ],
  "hypotheses": ["hypothesis_id"],
  "known_unknowns": [ /* from KnowledgeStateSnapshot */ ],
  "unknown_unknown_indicators": [ /* from KnowledgeStateSnapshot */ ],
  "speculations": ["speculation_id"],          // clearly segregated
  "reasoning_chain": [                          // ordered, each step cites evidence
    { "step": 0, "claim": "string", "epistemic_class": "...",
      "supports": ["evidence_id|hypothesis_id"], "agent": AgentName }
  ],
  "recommended_next_investigations": ["string"],
  "source_appendix": [ /* one entry per source: Provenance + access notes */ ],
  "confidence_calibration_note": "string",
  "generated_at": "rfc3339"
}
```

## 16. Validation Invariants (enforced by the runtime, not by convention)

1. Every persisted object has a valid `Provenance` with a real `ledger_event_id`.
2. `epistemic_class` is present and consistent with the object type and confidence band.
3. No `INSIGHT` exists whose `reasoning_chain` fails to terminate in `INFORMATION` nodes with
   non-derived provenance (auditability check).
4. `Hypothesis.confidence_history` is append-only and monotonically ordered by iteration.
5. `SpeculationItem` confidences never enter hypothesis-set normalization.
6. A `HypothesisSet` is never reduced below one active member by deletion; archival only.
7. Any object promoted across epistemic classes has a corresponding ledger promotion event.

These invariants are tested as **epistemic invariants** in
[09-testing-methodology.md](09-testing-methodology.md).
