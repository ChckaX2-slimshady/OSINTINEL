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
from .semantic import analyze_independence

PROMOTION_WATCH = 0.60  # confidence at which the promotion gate becomes relevant
MIN_INDEPENDENT_SOURCES = 2
SEMANTIC_DUP_THRESHOLD = 0.92  # cosine at/above which two sources are "the same content"


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
            findings += self._challenge_illusory_independence(ctx, leader)
            findings += self._challenge_with_model(ctx, leader)
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

    @staticmethod
    def _embed_fn(ctx: AgentContext):
        """The gateway's embed function, if a model layer is present (embed tier); else None."""
        gateway = ctx.llm
        embed = getattr(gateway, "embed", None) if gateway is not None else None
        return embed if callable(embed) else None

    def _challenge_illusory_independence(self, ctx: AgentContext, leader: Hypothesis):
        """Embed-tier challenge: collapse near-duplicate 'independent' sources (doc 11 §6).

        If the leader appears multi-source but its supporting evidence is near-duplicate content
        across declared groups, the independence is illusory — raise a BLOCKING finding so the
        Confidence gate refuses promotion until *genuinely* independent corroboration arrives.
        Only runs when an embedder is configured, so deterministic/offline runs are unaffected.
        """
        embed_fn = self._embed_fn(ctx)
        if embed_fn is None:
            return []
        support = [e for e in ctx.state.evidence_for(leader.hypothesis_id)
                   if leader.hypothesis_id in e.supports]
        groups = [ctx.state.sources.get(e.provenance.source, e.provenance.source)
                  for e in support]
        if len(set(groups)) < MIN_INDEPENDENT_SOURCES:
            return []  # not claiming multi-source; nothing to debunk

        try:
            report = analyze_independence(groups, [e.summary for e in support], embed_fn,
                                          threshold=SEMANTIC_DUP_THRESHOLD)
        except Exception:
            return []  # embed failure is never fatal

        open_finding = self._existing_open(ctx, leader.hypothesis_id, "illusory_independence")
        if len(report.effective) < MIN_INDEPENDENT_SOURCES and report.merged:
            if open_finding is None:
                clusters = "; ".join("≈".join(c) for c in report.merged)
                prov = ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.8)
                f = SkepticFinding(
                    target_ref=leader.hypothesis_id,
                    category="illusory_independence",
                    description=(
                        f"Apparent independence is illusory: {clusters} carry near-duplicate "
                        f"content; effective independent groups = {len(report.effective)} "
                        f"(< {MIN_INDEPENDENT_SOURCES} required). Corroboration is syndicated, "
                        f"not independent."),
                    severity="blocking",
                    evidence_refs=leader.supporting_evidence,
                    provenance=prov,
                )
                ctx.state.add_finding(f, ctx.iteration)
                return [f]
        elif open_finding is not None and len(report.effective) >= MIN_INDEPENDENT_SOURCES:
            ctx.state.resolve_finding(
                open_finding.finding_id,
                f"genuinely independent corroboration confirmed ({len(report.effective)} groups)",
                ctx.iteration)
        return []

    def _challenge_with_model(self, ctx: AgentContext, leader: Hypothesis):
        """Reason-tier adversarial critique (doc 11): the model authors objections that the
        structural challenges can't — hidden assumptions, reasoning weaknesses. Advisory only:
        severity is capped below 'blocking' so the computed gates remain the sole blockers.
        Runs only when a model is configured; deterministic runs are unaffected.
        """
        if ctx.llm is None:
            return []
        from .reasoning import ReasoningModel
        evidence = [e.summary for e in ctx.state.evidence_for(leader.hypothesis_id)]
        try:
            objections = ReasoningModel(ctx.llm).critique(statement=leader.statement,
                                                          evidence=evidence)
        except Exception:
            return []
        existing = {(f.category, f.description) for f in ctx.state.findings.values()}
        out: list[SkepticFinding] = []
        for obj in objections:
            key = (obj["category"], obj["description"])
            if key in existing:
                continue
            prov = ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.6)
            f = SkepticFinding(
                target_ref=leader.hypothesis_id, category=obj["category"],
                description=obj["description"],
                severity=obj["severity"],  # already capped to <= "high" by ReasoningModel
                provenance=prov)
            ctx.state.add_finding(f, ctx.iteration)
            out.append(f)
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
