"""Tool Selection Agent (doc 02 §4) — produces ToolPlans.

Chooses adapters dynamically by capability; never hardcodes a path. Prefers higher
effectiveness and a source independent from those already used for the same hypotheses
(the independence bias that feeds the Confidence Agent's source_independence factor).
"""

from __future__ import annotations

from ..core.schemas import AcquisitionMethod, AgentName, ToolPlan
from .base import AgentContext


class ToolSelectionAgent:
    name = AgentName.TOOL_SELECTION

    def run(self, ctx: AgentContext, requests) -> list[ToolPlan]:
        plans: list[ToolPlan] = []
        for req in requests:
            adapter = None
            for cap in req.candidate_capabilities:
                candidates = ctx.registry.by_capability(cap)
                if candidates:
                    # Effectiveness = the seeded registry prior, refined by Investigation Memory
                    # when present (doc 05 §3 ``effectiveness(adapter_id, context)``).
                    adapter = max(candidates, key=lambda a: self._effectiveness(ctx, a.id))
                    chosen_cap = cap
                    break
            if adapter is None:
                continue
            fallbacks = [a.id for a in ctx.registry.all() if a.id != adapter.id]
            hs = ctx.state.hypothesis_sets[req.question_ref]
            prov = ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.7)
            plans.append(
                ToolPlan(
                    evidence_request_id=req.evidence_request_id,
                    selected_adapter=adapter.id,
                    operation="collect",
                    arguments={
                        "set_id": req.question_ref,
                        "set_tag": hs.question,
                        "capability": chosen_cap,
                    },
                    fallback_adapters=fallbacks,
                    rationale=f"selected {adapter.id} by capability {chosen_cap!r} "
                              f"(effectiveness {self._effectiveness(ctx, adapter.id):.2f})",
                    expected_cost=adapter.cost_of("collect"),
                    provenance=prov,
                )
            )
        return plans

    @staticmethod
    def _effectiveness(ctx: AgentContext, adapter_id: str) -> float:
        seed = ctx.registry.effectiveness(adapter_id)
        return ctx.priors.adapter_effectiveness(adapter_id, default=seed) if ctx.priors else seed
