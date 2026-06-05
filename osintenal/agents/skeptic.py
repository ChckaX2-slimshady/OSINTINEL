"""Skeptic Agent (doc 02 §7) — the mandatory challenge layer and a true gate.

No major conclusion bypasses Skeptic review. In Phase 1 the Skeptic enforces two concrete
challenges that exercise the gate mechanism:

* **Source dependency (blocking):** a hypothesis approaching promotion while supported by
  fewer than two *independent* source groups gets a BLOCKING finding. The Confidence Agent
  then refuses to promote it past HYPOTHESIS until the finding is resolved — which the
  Skeptic does once independent corroboration arrives.
* **Premature convergence (non-blocking):** a dominant leader with no contradicting evidence
  and little residual mass gets flagged, and (once per set, early) the Skeptic injects an
  alternative explanation so the space stays open.
"""

from __future__ import annotations

from ..core.schemas import (
    AcquisitionMethod,
    AgentName,
    EpistemicClass,
    Hypothesis,
    SkepticFinding,
)
from .base import AgentContext

PROMOTION_WATCH = 0.60  # confidence at which the promotion gate becomes relevant
MIN_INDEPENDENT_SOURCES = 2


class SkepticAgent:
    name = AgentName.SKEPTIC

    def run(self, ctx: AgentContext) -> list[SkepticFinding]:
        findings: list[SkepticFinding] = []
        for hs in ctx.state.hypothesis_sets.values():
            active = ctx.state.active_hypotheses(hs.set_id)
            if not active:
                continue
            leader = max(active, key=lambda h: h.confidence)
            findings += self._challenge_source_dependency(ctx, leader)
            findings += self._challenge_premature_convergence(ctx, hs, leader, active)
        return findings

    def _existing_open(self, ctx, target_ref, category) -> SkepticFinding | None:
        for f in ctx.state.findings.values():
            if f.target_ref == target_ref and f.category == category and not f.resolved:
                return f
        return None

    def _challenge_source_dependency(self, ctx: AgentContext, leader: Hypothesis):
        out: list[SkepticFinding] = []
        groups = ctx.state.independent_source_groups(leader.hypothesis_id)
        open_finding = self._existing_open(ctx, leader.hypothesis_id, "source_dependency")
        if leader.confidence >= PROMOTION_WATCH and len(groups) < MIN_INDEPENDENT_SOURCES:
            if open_finding is None:
                prov = ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.8)
                f = SkepticFinding(
                    target_ref=leader.hypothesis_id,
                    category="source_dependency",
                    description=(
                        f"Leading hypothesis {leader.statement!r} is approaching promotion "
                        f"but rests on {len(groups)} independent source group(s); "
                        f"{MIN_INDEPENDENT_SOURCES} required before promotion."
                    ),
                    severity="blocking",
                    evidence_refs=leader.supporting_evidence,
                    provenance=prov,
                )
                ctx.state.add_finding(f, ctx.iteration)
                out.append(f)
        elif open_finding is not None and len(groups) >= MIN_INDEPENDENT_SOURCES:
            ctx.state.resolve_finding(
                open_finding.finding_id,
                f"independent corroboration reached ({len(groups)} source groups)",
                ctx.iteration,
            )
        return out

    def _challenge_premature_convergence(self, ctx, hs, leader, active):
        out: list[SkepticFinding] = []
        any_contradiction = any(h.contradicting_evidence for h in active)
        injected_alt = any(h.origin == "skeptic" for h in active)
        if (
            leader.confidence >= 0.5
            and not any_contradiction
            and not injected_alt
            and ctx.iteration <= 1
        ):
            prov = ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.5)
            f = SkepticFinding(
                target_ref=leader.hypothesis_id,
                category="alt_explanation",
                description="Leader dominates with no contradicting evidence; injecting an "
                            "alternative explanation to resist premature convergence.",
                severity="medium",
                proposed_alternative="unconsidered alternative explanation",
                provenance=prov,
            )
            ctx.state.add_finding(f, ctx.iteration)
            out.append(f)

            alt_prov = ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.3)
            alt = Hypothesis(
                set_id=hs.set_id,
                statement="unconsidered alternative explanation",
                confidence=0.0,
                epistemic_class=EpistemicClass.HYPOTHESIS,
                origin="skeptic",
                provenance=alt_prov,
            )
            ctx.state.add_hypothesis(alt, ctx.iteration)
            ctx.state.update_confidence(
                alt.hypothesis_id, 0.01, "skeptic-injected alternative (low prior)",
                self.name, ctx.iteration,
            )
        return out
