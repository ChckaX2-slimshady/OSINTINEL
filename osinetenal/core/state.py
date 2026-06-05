"""In-memory investigation state (Phase 1 stand-in for the knowledge graph).

Every mutation is mediated here and mirrored to the append-only ledger, so the working
state and the evidentiary history stay consistent. This module enforces the structural
guarantees that doc 04 §7 assigns to graph write-time constraints:

* provenance-or-nothing (objects carry a Provenance with a ledger_event_id),
* hypothesis preservation (no deletion; confidence_history is append-only),
* set minimum (a HypothesisSet never drops below one active member),
* speculation quarantine (speculations never enter set normalization).

Phase 2 replaces this with a graph-native ``GraphStore`` honoring the same contract.
"""

from __future__ import annotations

from ..ledger import Ledger
from .schemas import (
    AgentName,
    ConfidenceHistoryEntry,
    EvidenceObject,
    Hypothesis,
    HypothesisSet,
    KnowledgeStateSnapshot,
    Observation,
    SkepticFinding,
    SpeculationItem,
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
        self.hypotheses: dict[str, Hypothesis] = {}
        self.speculations: dict[str, SpeculationItem] = {}
        self.findings: dict[str, SkepticFinding] = {}
        self.snapshots: list[KnowledgeStateSnapshot] = []
        # Distinct sources seen, grouped for the independence factor (doc 04 §6).
        self.sources: dict[str, str] = {}  # source name -> independence_group

    # -- generic persistence ------------------------------------------------
    def _record(self, iteration: int, type_: str, actor: str, payload: dict) -> str:
        event = self.ledger.append(
            investigation_id=self.investigation_id,
            iteration=iteration,
            type=type_,
            actor=actor,
            payload=payload,
        )
        return event.event_id

    # -- observations & evidence -------------------------------------------
    def add_observation(self, obs: Observation, iteration: int) -> None:
        eid = self._record(iteration, "node_add", obs.provenance.agent_responsible.value,
                            {"node_type": "Observation", "id": obs.observation_id})
        obs.provenance.ledger_event_id = eid
        self.observations[obs.observation_id] = obs
        self._register_source(obs.source)

    def add_evidence(self, ev: EvidenceObject, iteration: int) -> None:
        eid = self._record(iteration, "node_add", ev.provenance.agent_responsible.value,
                            {"node_type": "EvidenceObject", "id": ev.evidence_id,
                             "supports": ev.supports, "contradicts": ev.contradicts})
        ev.provenance.ledger_event_id = eid
        self.evidence[ev.evidence_id] = ev
        self._register_source(ev.provenance.source, ev.structured.get("independence_group"))

    def _register_source(self, name: str, group: str | None = None) -> None:
        if name not in self.sources:
            self.sources[name] = group or name

    # -- hypothesis sets & hypotheses --------------------------------------
    def add_set(self, hs: HypothesisSet, iteration: int) -> None:
        eid = self._record(iteration, "node_add", AgentName.CONNECTIONS.value,
                            {"node_type": "HypothesisSet", "id": hs.set_id})
        hs.provenance.ledger_event_id = eid
        self.hypothesis_sets[hs.set_id] = hs

    def add_hypothesis(self, h: Hypothesis, iteration: int) -> None:
        eid = self._record(iteration, "node_add", h.provenance.agent_responsible.value,
                            {"node_type": "Hypothesis", "id": h.hypothesis_id,
                             "set_id": h.set_id, "statement": h.statement})
        h.provenance.ledger_event_id = eid
        self.hypotheses[h.hypothesis_id] = h
        if h.hypothesis_id not in self.hypothesis_sets[h.set_id].hypotheses:
            self.hypothesis_sets[h.set_id].hypotheses.append(h.hypothesis_id)

    def update_confidence(
        self, hypothesis_id: str, confidence: float, reason: str,
        by_agent: AgentName, iteration: int,
    ) -> None:
        """Append-only confidence update — the Hypothesis Preservation Rule."""
        h = self.hypotheses[hypothesis_id]
        eid = self._record(iteration, "confidence_change", by_agent.value,
                            {"hypothesis_id": hypothesis_id, "from": h.confidence,
                             "to": confidence, "reason": reason})
        h.confidence_history.append(
            ConfidenceHistoryEntry(iteration=iteration, confidence=confidence,
                                   delta_reason=reason, by_agent=by_agent,
                                   ledger_event_id=eid)
        )
        h.confidence = confidence

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
        eid = self._record(iteration, "node_add", AgentName.SKEPTIC.value,
                            {"node_type": "SkepticFinding", "id": f.finding_id,
                             "severity": f.severity, "target": f.target_ref})
        f.provenance.ledger_event_id = eid
        self.findings[f.finding_id] = f
        if f.target_ref in self.hypotheses:
            self.hypotheses[f.target_ref].skeptic_findings.append(f.finding_id)

    def resolve_finding(self, finding_id: str, reason: str, iteration: int) -> None:
        f = self.findings[finding_id]
        self._record(iteration, "finding_resolved", AgentName.SKEPTIC.value,
                     {"finding_id": finding_id, "reason": reason})
        f.resolved = True

    def add_speculation(self, sp: SpeculationItem, iteration: int) -> None:
        eid = self._record(iteration, "node_add", AgentName.SPECULATION.value,
                            {"node_type": "Speculation", "id": sp.speculation_id})
        sp.provenance.ledger_event_id = eid
        self.speculations[sp.speculation_id] = sp

    def add_snapshot(self, snap: KnowledgeStateSnapshot) -> None:
        eid = self._record(snap.iteration, "node_add", AgentName.EPISTEMOLOGY.value,
                           {"node_type": "KnowledgeStateSnapshot", "id": snap.snapshot_id})
        snap.provenance.ledger_event_id = eid
        self.snapshots.append(snap)

    # -- queries -----------------------------------------------------------
    def active_hypotheses(self, set_id: str) -> list[Hypothesis]:
        return [self.hypotheses[hid] for hid in self.hypothesis_sets[set_id].hypotheses
                if self.hypotheses[hid].status != "archived"]

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
