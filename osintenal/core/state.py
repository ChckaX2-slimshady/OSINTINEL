"""Investigation state — the working knowledge graph, mirrored to the provenance ledger.

Every mutation is mediated here and recorded as an append-only ledger event whose payload
carries enough to **reconstruct the object byte-for-byte**. The ledger is therefore the
single source of truth; this in-memory state is a *materialized view* over it (doc 04 §8).
``osintenal.ledger.replay`` rebuilds an identical ``InvestigationState`` from the events alone.

This module enforces the structural guarantees doc 04 §7 assigns to graph write-time
constraints: provenance-or-nothing, hypothesis preservation (append-only confidence history,
no deletion), set-minimum (a HypothesisSet never drops below one active member), and
speculation quarantine. The graph projection (``osintenal.graph``) is built from this state.
"""

from __future__ import annotations

from ..ledger import Ledger
from .schemas import (
    AgentName,
    ConfidenceHistoryEntry,
    EpistemicClass,
    EvidenceObject,
    Explanation,
    Hypothesis,
    HypothesisSet,
    KnowledgeStateSnapshot,
    Observation,
    SkepticFinding,
    SpeculationItem,
    explanation_type_for_confidence,
)


class StatePreservationError(RuntimeError):
    """Raised on an attempt to violate a preservation/integrity guarantee."""


class InvestigationState:
    def __init__(self, investigation_id: str, ledger: Ledger) -> None:
        self.investigation_id = investigation_id
        self.ledger = ledger
        self.observations: dict[str, Observation] = {}
        self.evidence: dict[str, EvidenceObject] = {}
        self.hypothesis_sets: dict[str, HypothesisSet] = {}
        self.explanations: dict[str, Explanation] = {}
        self.hypotheses: dict[str, Hypothesis] = {}
        self.speculations: dict[str, SpeculationItem] = {}
        self.findings: dict[str, SkepticFinding] = {}
        self.snapshots: list[KnowledgeStateSnapshot] = []
        # Distinct sources seen, grouped for the independence factor (doc 04 §6).
        self.sources: dict[str, str] = {}  # source name -> independence_group

    # -- generic persistence ------------------------------------------------
    def _record(self, iteration: int, type_: str, actor: str, payload: dict):
        return self.ledger.append(
            investigation_id=self.investigation_id,
            iteration=iteration,
            type=type_,
            actor=actor,
            payload=payload,
        )

    def _record_id(self, iteration: int, type_: str, actor: str, payload: dict) -> str:
        return self._record(iteration, type_, actor, payload).event_id

    @staticmethod
    def _node_payload(node_type: str, node_id: str, obj) -> dict:
        # The full object dump makes the ledger a complete, replayable source of truth.
        return {"node_type": node_type, "id": node_id, "object": obj.model_dump(mode="json")}

    # -- observations & evidence (record → index) --------------------------
    def add_observation(self, obs: Observation, iteration: int) -> None:
        eid = self._record_id(iteration, "node_add", obs.provenance.agent_responsible.value,
                           self._node_payload("Observation", obs.observation_id, obs))
        obs.provenance.ledger_event_id = eid
        self._index_observation(obs)

    def _index_observation(self, obs: Observation) -> None:
        self.observations[obs.observation_id] = obs
        self._register_source(obs.source)

    def add_evidence(self, ev: EvidenceObject, iteration: int) -> None:
        eid = self._record_id(iteration, "node_add", ev.provenance.agent_responsible.value,
                           self._node_payload("EvidenceObject", ev.evidence_id, ev))
        ev.provenance.ledger_event_id = eid
        self._index_evidence(ev)

    def _index_evidence(self, ev: EvidenceObject) -> None:
        self.evidence[ev.evidence_id] = ev
        self._register_source(ev.provenance.source, ev.structured.get("independence_group"))

    def _register_source(self, name: str, group: str | None = None) -> None:
        if name not in self.sources:
            self.sources[name] = group or name

    # -- hypothesis sets, explanations & hypotheses ------------------------
    def add_set(self, hs: HypothesisSet, iteration: int) -> None:
        eid = self._record_id(iteration, "node_add", AgentName.CONNECTIONS.value,
                           self._node_payload("HypothesisSet", hs.set_id, hs))
        hs.provenance.ledger_event_id = eid
        self._index_set(hs)

    def _index_set(self, hs: HypothesisSet) -> None:
        self.hypothesis_sets[hs.set_id] = hs

    def add_explanation(self, ex: Explanation, iteration: int) -> None:
        """Persist a competing explanation (the SPECULATION/EXTRAPOLATION tier)."""
        eid = self._record_id(iteration, "node_add", ex.provenance.agent_responsible.value,
                           self._node_payload("Explanation", ex.explanation_id, ex))
        ex.provenance.ledger_event_id = eid
        self._index_explanation(ex)

    def _index_explanation(self, ex: Explanation) -> None:
        self.explanations[ex.explanation_id] = ex
        if ex.explanation_id not in self.hypothesis_sets[ex.set_id].explanations:
            self.hypothesis_sets[ex.set_id].explanations.append(ex.explanation_id)

    def add_hypothesis(self, h: Hypothesis, iteration: int) -> None:
        eid = self._record_id(iteration, "node_add", h.provenance.agent_responsible.value,
                           self._node_payload("Hypothesis", h.hypothesis_id, h))
        h.provenance.ledger_event_id = eid
        self._index_hypothesis(h)

    def _index_hypothesis(self, h: Hypothesis) -> None:
        self.hypotheses[h.hypothesis_id] = h
        if h.hypothesis_id not in self.hypothesis_sets[h.set_id].hypotheses:
            self.hypothesis_sets[h.set_id].hypotheses.append(h.hypothesis_id)
        # Link the synthesized hypothesis back to its explanation(s).
        for ex_id in h.derived_from_explanations:
            if ex_id in self.explanations:
                self.explanations[ex_id].hypothesis_id = h.hypothesis_id

    def reclassify_explanation(self, explanation_id: str, confidence: float,
                               iteration: int) -> None:
        """Mirror a hypothesis' confidence onto its backing explanation and re-type it.

        Recorded whenever the confidence (and hence possibly the SPECULATION/EXTRAPOLATION
        type) changes, so the explanation tier is faithfully replayable.
        """
        ex = self.explanations[explanation_id]
        if ex.confidence == confidence:
            return
        before, after = ex.epistemic_class, explanation_type_for_confidence(confidence)
        self._record(iteration, "explanation_reclassify", AgentName.CONFIDENCE.value,
                     {"explanation_id": explanation_id, "from": before.value,
                      "to": after.value, "confidence": confidence})
        self._apply_reclassify(explanation_id, confidence)

    def _apply_reclassify(self, explanation_id: str, confidence: float) -> None:
        ex = self.explanations[explanation_id]
        ex.confidence = confidence
        ex.classify()

    def update_confidence(
        self, hypothesis_id: str, confidence: float, reason: str,
        by_agent: AgentName, iteration: int,
    ) -> None:
        """Append-only confidence update — the Hypothesis Preservation Rule."""
        h = self.hypotheses[hypothesis_id]
        event = self._record(iteration, "confidence_change", by_agent.value,
                             {"hypothesis_id": hypothesis_id, "from": h.confidence,
                              "to": confidence, "reason": reason})
        # Bind the history entry's timestamp to its ledger event so replay is byte-identical.
        self._apply_confidence(hypothesis_id, confidence, reason, by_agent, iteration,
                               event.event_id, event.timestamp)

    def _apply_confidence(self, hypothesis_id: str, confidence: float, reason: str,
                          by_agent: AgentName, iteration: int, eid: str, timestamp) -> None:
        h = self.hypotheses[hypothesis_id]
        h.confidence_history.append(
            ConfidenceHistoryEntry(iteration=iteration, confidence=confidence,
                                   delta_reason=reason, by_agent=by_agent,
                                   timestamp=timestamp, ledger_event_id=eid)
        )
        h.confidence = confidence

    def set_epistemic_class(self, hypothesis_id: str, new_class: EpistemicClass,
                            iteration: int, by_agent: AgentName) -> None:
        """Record a hypothesis tier change (e.g. promotion to INSIGHT) as a ledger event.

        Satisfies doc 03 §16.7 ("promotion across tiers has a ledger event") and keeps the
        class replayable rather than an out-of-band in-memory write.
        """
        h = self.hypotheses[hypothesis_id]
        if h.epistemic_class is new_class:
            return
        self._record(iteration, "hypothesis_promote", by_agent.value,
                     {"hypothesis_id": hypothesis_id, "from": h.epistemic_class.value,
                      "to": new_class.value})
        h.epistemic_class = new_class

    def set_residual_mass(self, set_id: str, value: float, iteration: int) -> None:
        """Record a set's residual ('none of the above') mass change as a ledger event."""
        hs = self.hypothesis_sets[set_id]
        if hs.residual_mass == value:
            return
        self._record(iteration, "residual_mass_change", AgentName.CONFIDENCE.value,
                     {"set_id": set_id, "from": hs.residual_mass, "to": value})
        hs.residual_mass = value

    def archive_hypothesis(self, hypothesis_id: str, iteration: int) -> None:
        """Archive (never delete). A set must keep >=1 active member (doc 04 §7.4)."""
        h = self.hypotheses[hypothesis_id]
        active = [hid for hid in self.hypothesis_sets[h.set_id].hypotheses
                  if self.hypotheses[hid].status != "archived"]
        if len(active) <= 1 and h.status != "archived":
            raise StatePreservationError(
                "cannot archive the last active hypothesis in a set"
            )
        self._record(iteration, "hypothesis_archive", AgentName.SYNTHESIS.value,
                     {"hypothesis_id": hypothesis_id})
        h.status = "archived"

    def reactivate_hypothesis(self, hypothesis_id: str, reason: str, iteration: int) -> None:
        h = self.hypotheses[hypothesis_id]
        self._record(iteration, "hypothesis_reactivate", AgentName.SKEPTIC.value,
                     {"hypothesis_id": hypothesis_id, "reason": reason})
        h.status = "reactivated"

    # -- findings, speculation, snapshots ----------------------------------
    def add_finding(self, f: SkepticFinding, iteration: int) -> None:
        eid = self._record_id(iteration, "node_add", AgentName.SKEPTIC.value,
                           self._node_payload("SkepticFinding", f.finding_id, f))
        f.provenance.ledger_event_id = eid
        self._index_finding(f)

    def _index_finding(self, f: SkepticFinding) -> None:
        self.findings[f.finding_id] = f
        if f.target_ref in self.hypotheses:
            self.hypotheses[f.target_ref].skeptic_findings.append(f.finding_id)

    def resolve_finding(self, finding_id: str, reason: str, iteration: int) -> None:
        self._record(iteration, "finding_resolved", AgentName.SKEPTIC.value,
                     {"finding_id": finding_id, "reason": reason})
        self.findings[finding_id].resolved = True

    def add_speculation(self, sp: SpeculationItem, iteration: int) -> None:
        eid = self._record_id(iteration, "node_add", AgentName.SPECULATION.value,
                           self._node_payload("Speculation", sp.speculation_id, sp))
        sp.provenance.ledger_event_id = eid
        self._index_speculation(sp)

    def _index_speculation(self, sp: SpeculationItem) -> None:
        self.speculations[sp.speculation_id] = sp

    def add_snapshot(self, snap: KnowledgeStateSnapshot) -> None:
        eid = self._record_id(snap.iteration, "node_add", AgentName.EPISTEMOLOGY.value,
                           self._node_payload("KnowledgeStateSnapshot", snap.snapshot_id, snap))
        snap.provenance.ledger_event_id = eid
        self._index_snapshot(snap)

    def _index_snapshot(self, snap: KnowledgeStateSnapshot) -> None:
        self.snapshots.append(snap)

    # -- evidence relinking (pure projection over recorded evidence) -------
    def relink_evidence(self) -> None:
        """Recompute each hypothesis' supporting/contradicting evidence from the evidence
        graph. A pure function of recorded ``EvidenceObject.supports/contradicts`` — used by
        both the Synthesis Agent and ledger replay so the two produce identical state."""
        for h in self.hypotheses.values():
            h.supporting_evidence = [e.evidence_id for e in self.evidence.values()
                                     if h.hypothesis_id in e.supports]
            h.contradicting_evidence = [e.evidence_id for e in self.evidence.values()
                                        if h.hypothesis_id in e.contradicts]

    # -- queries -----------------------------------------------------------
    def active_hypotheses(self, set_id: str) -> list[Hypothesis]:
        return [self.hypotheses[hid] for hid in self.hypothesis_sets[set_id].hypotheses
                if self.hypotheses[hid].status != "archived"]

    def active_explanations(self, set_id: str) -> list[Explanation]:
        return [self.explanations[eid] for eid in self.hypothesis_sets[set_id].explanations
                if self.explanations[eid].status != "archived"]

    def unsynthesized_explanations(self, set_id: str) -> list[Explanation]:
        """Explanations not yet synthesized into a hypothesis (Synthesis Agent input)."""
        return [ex for ex in self.active_explanations(set_id) if ex.hypothesis_id is None]

    def evidence_for(self, hypothesis_id: str) -> list[EvidenceObject]:
        return [e for e in self.evidence.values()
                if hypothesis_id in e.supports or hypothesis_id in e.contradicts]

    def independent_source_groups(self, hypothesis_id: str) -> set[str]:
        groups: set[str] = set()
        for e in self.evidence_for(hypothesis_id):
            groups.add(self.sources.get(e.provenance.source, e.provenance.source))
        return groups

    def unresolved_blocking_findings(self, target_ref: str) -> list[SkepticFinding]:
        return [f for f in self.findings.values()
                if f.target_ref == target_ref and f.severity == "blocking" and not f.resolved]

    # -- byte-identical comparison (replay verification, doc 06 Phase 2) ---
    def snapshot(self) -> dict:
        """A canonical, order-stable dump of all state for byte-identical comparison."""
        def dump_map(m: dict) -> dict:
            return {k: m[k].model_dump(mode="json") for k in sorted(m)}
        return {
            "investigation_id": self.investigation_id,
            "observations": dump_map(self.observations),
            "evidence": dump_map(self.evidence),
            "hypothesis_sets": dump_map(self.hypothesis_sets),
            "explanations": dump_map(self.explanations),
            "hypotheses": dump_map(self.hypotheses),
            "speculations": dump_map(self.speculations),
            "findings": dump_map(self.findings),
            "snapshots": [s.model_dump(mode="json") for s in self.snapshots],
            "sources": dict(sorted(self.sources.items())),
        }
