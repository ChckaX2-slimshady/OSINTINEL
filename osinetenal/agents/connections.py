"""Connections Agent (doc 02 §2) — produces CONNECTION and proposes competing HYPOTHESES.

Hard requirements from the spec: preserve multiple hypotheses, resist premature
convergence, maintain alternatives. This agent therefore always seeds a set with >= 2
competing explanations and reserves residual mass for "none of the above".
"""

from __future__ import annotations

from ..core.schemas import (
    AcquisitionMethod,
    AgentName,
    EpistemicClass,
    Hypothesis,
    HypothesisSet,
)
from .base import AgentContext

INITIAL_RESIDUAL_MASS = 0.20


class ConnectionsAgent:
    name = AgentName.CONNECTIONS

    def run(self, ctx: AgentContext) -> list[HypothesisSet]:
        # Phase 1: seed competing-hypothesis sets from the investigation's questions once.
        if ctx.state.hypothesis_sets:
            return list(ctx.state.hypothesis_sets.values())

        created: list[HypothesisSet] = []
        for q in (i for i in ctx.investigation.inputs if i.get("kind") == "question"):
            candidates = q.get("candidates", [])
            if len(candidates) < 2:
                # Resist a single-explanation framing: keep the space open.
                candidates = list(candidates) + ["alternative / none of the above"]
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
                hp = ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.5)
                h = Hypothesis(
                    set_id=hs.set_id,
                    statement=statement,
                    confidence=prior,
                    epistemic_class=EpistemicClass.HYPOTHESIS,
                    origin="connections",
                    provenance=hp,
                )
                ctx.state.add_hypothesis(h, ctx.iteration)
                ctx.state.update_confidence(
                    h.hypothesis_id, prior, "initial uniform prior over competing explanations",
                    self.name, ctx.iteration,
                )
            created.append(hs)
        return created
