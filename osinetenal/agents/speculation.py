"""Speculative Possibility Engine (doc 02 §10) — produces quarantined SPECULATION.

Invoked on demand (e.g. when the planner runs dry) to expand the possibility space — never
to establish truth. Items are clearly labeled, use a separate confidence model, state their
evidence limitations, and never flow into an INSIGHT unless re-derived as a hypothesis.
"""

from __future__ import annotations

from ..core.schemas import AcquisitionMethod, AgentName, SpeculationItem
from .base import AgentContext


class SpeculationAgent:
    name = AgentName.SPECULATION

    def run(self, ctx: AgentContext) -> list[SpeculationItem]:
        out: list[SpeculationItem] = []
        for hs in ctx.state.hypothesis_sets.values():
            if hs.residual_mass < 0.05:
                continue
            prov = ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.2)
            item = SpeculationItem(
                statement=f"An explanation outside the current set may account for "
                          f"the residual mass in {hs.question!r}.",
                speculative_confidence=round(hs.residual_mass, 3),
                evidence_limitations=[
                    "No acquired evidence directly supports this possibility.",
                    "Derived only from unexplained residual probability mass.",
                ],
                would_promote_if=[
                    "Discriminating evidence is acquired that an existing hypothesis "
                    "cannot account for."
                ],
                provenance=prov,
            )
            ctx.state.add_speculation(item, ctx.iteration)
            out.append(item)
        return out
