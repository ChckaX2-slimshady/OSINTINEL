"""Connections Agent (doc 02 §2) — produces CONNECTIONs and competing EXPLANATIONS.

Information is used to make connections; verifiable connections logically sequenced are
possible *explanations*. This agent frames a question and emits >= 2 competing explanations
for it, reserving residual mass for "none of the above" (resist premature convergence).

Per the Foundational Separation Principle each explanation is one of the two explanation
types — SPECULATION (low confidence) or EXTRAPOLATION (high confidence) — derived from its
confidence. The Synthesis Agent later synthesizes these competing explanations *into*
hypotheses; this agent never creates hypotheses directly.
"""

from __future__ import annotations

from ..core.schemas import (
    AcquisitionMethod,
    AgentName,
    Explanation,
    HypothesisSet,
)
from .base import AgentContext

INITIAL_RESIDUAL_MASS = 0.20


class ConnectionsAgent:
    name = AgentName.CONNECTIONS

    def run(self, ctx: AgentContext) -> list[HypothesisSet]:
        # Phase 1: frame each question once and seed its competing explanations.
        if ctx.state.hypothesis_sets:
            return list(ctx.state.hypothesis_sets.values())

        created: list[HypothesisSet] = []
        for q in (i for i in ctx.investigation.inputs if i.get("kind") == "question"):
            candidates = q.get("candidates", [])
            if len(candidates) < 2:
                # Resist a single-explanation framing: keep the space open.
                candidates = list(candidates) + ["alternative / none of the above"]
            # Reason tier (Phase M): when a model is present, generate *additional* competing
            # explanations beyond those handed in — open-ended hypothesis generation. Falls back
            # to the given candidates when no model is configured (deterministic default).
            candidates = self._augment_candidates(ctx, q.get("question", ""), candidates)
            prov = ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.5)
            hs = HypothesisSet(
                question=q["question"],
                residual_mass=INITIAL_RESIDUAL_MASS,
                provenance=prov,
            )
            ctx.state.add_set(hs, ctx.iteration)

            usable = max(1.0 - INITIAL_RESIDUAL_MASS, 0.0)
            prior = usable / len(candidates)
            for statement in candidates:
                ep = ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.5)
                explanation = Explanation(
                    set_id=hs.set_id,
                    statement=statement,
                    confidence=prior,
                    derived_from=list(ctx.state.observations.keys()),
                    provenance=ep,
                )
                explanation.classify()  # low prior => SPECULATION initially
                ctx.state.add_explanation(explanation, ctx.iteration)
            created.append(hs)
        return created

    def _augment_candidates(self, ctx: AgentContext, question: str,
                            candidates: list[str]) -> list[str]:
        if ctx.llm is None:
            return candidates
        from .reasoning import ReasoningModel
        observations = [f"{o.type}: {o.content}" for o in ctx.state.observations.values()]
        extra = ReasoningModel(ctx.llm).propose_explanations(
            question=question, observations=observations, existing=candidates, limit=2)
        return candidates + extra
