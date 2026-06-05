"""Epistemology Agent (doc 02 §9) — protects against false certainty.

Refreshes the live knowledge state every iteration: Knowns (evidence-backed claims),
Known Unknowns (open questions that feed the planner), and Unknown-Unknown indicators
(source monoculture, high residual mass, contradiction clusters, single-tool dependence).
"""

from __future__ import annotations

from ..core.schemas import (
    AcquisitionMethod,
    AgentName,
    Known,
    KnowledgeStateSnapshot,
    KnownUnknown,
    UnknownUnknownIndicator,
)
from .base import AgentContext

MONOCULTURE_MIN_EVIDENCE = 2
HIGH_RESIDUAL = 0.15


class EpistemologyAgent:
    name = AgentName.EPISTEMOLOGY

    def run(self, ctx: AgentContext) -> KnowledgeStateSnapshot:
        knowns: list[Known] = []
        known_unknowns: list[KnownUnknown] = []
        uu: list[UnknownUnknownIndicator] = []
        hidden = ["Assumes the available open sources are representative of the ground truth."]

        for hs in ctx.state.hypothesis_sets.values():
            active = ctx.state.active_hypotheses(hs.set_id)
            if not active:
                continue
            leader = max(active, key=lambda h: h.confidence)

            for h in active:
                if h.confidence >= 0.75 and h.supporting_evidence:
                    knowns.append(Known(
                        statement=f"{h.statement!r} is well-supported (confidence {h.confidence:.2f})",
                        evidence_refs=h.supporting_evidence,
                    ))

            if leader.confidence < ctx.investigation.config.confidence_threshold:
                known_unknowns.append(KnownUnknown(
                    question=f"What additional evidence would resolve: {hs.question!r}?",
                    blocking=bool(ctx.state.unresolved_blocking_findings(leader.hypothesis_id)),
                    suggested_capabilities=["stub.evidence", "archive.snapshot", "geo.features"],
                ))

            total_ev = sum(len(ctx.state.evidence_for(h.hypothesis_id)) for h in active)
            groups = ctx.state.independent_source_groups(leader.hypothesis_id)
            if total_ev >= MONOCULTURE_MIN_EVIDENCE and len(groups) <= 1:
                uu.append(UnknownUnknownIndicator(
                    signal="source_monoculture",
                    detail=f"Leader rests on {len(groups)} independent source group(s) "
                           f"across {total_ev} evidence items.",
                    severity="high",
                ))
            if hs.residual_mass >= HIGH_RESIDUAL:
                uu.append(UnknownUnknownIndicator(
                    signal="unexplained_residual",
                    detail=f"Residual 'none of the above' mass is {hs.residual_mass:.2f} "
                           f"for {hs.question!r}.",
                    severity="medium",
                ))
            if any(h.contradicting_evidence for h in active):
                uu.append(UnknownUnknownIndicator(
                    signal="contradiction_cluster",
                    detail="Contradicting evidence is present within the set.",
                    severity="low",
                ))

        snap = KnowledgeStateSnapshot(
            investigation_id=ctx.investigation.investigation_id,
            iteration=ctx.iteration,
            knowns=knowns,
            known_unknowns=known_unknowns,
            unknown_unknown_indicators=uu,
            hidden_assumptions=hidden,
            provenance=ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.8),
        )
        ctx.state.add_snapshot(snap)
        return snap
