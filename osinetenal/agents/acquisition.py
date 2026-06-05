"""Evidence Acquisition Agent (doc 02 §5) — produces EvidenceObjects (INFORMATION).

Executes ToolPlans against adapters, charges the budget, records the call, and normalizes
results into schema-valid evidence with provenance. On adapter exhaustion it returns empty
(the planner then runs dry, a termination/uu signal) rather than fabricating evidence.
"""

from __future__ import annotations

from ..adapters.base import CollectTarget
from ..core.budget import BudgetExhausted
from ..core.schemas import AcquisitionMethod, AgentName, EvidenceObject
from .base import AgentContext


class AcquisitionAgent:
    name = AgentName.ACQUISITION

    def run(self, ctx: AgentContext, plans) -> list[EvidenceObject]:
        collected: list[EvidenceObject] = []
        for plan in plans:
            adapter = ctx.registry.get(plan.selected_adapter)
            cap = plan.arguments.get("capability", "stub.evidence")
            hits = adapter.search(cap, {"set_tag": plan.arguments.get("set_tag")})
            if not hits:
                continue

            set_id = plan.arguments["set_id"]
            hypothesis_map = {
                h.statement: h.hypothesis_id
                for h in ctx.state.active_hypotheses(set_id)
            }
            try:
                ctx.governor.check()
            except BudgetExhausted:
                break

            hit = hits[0]  # deterministic selection for replayability
            raw = adapter.collect(CollectTarget(hit_id=hit.hit_id,
                                                arguments={"hypothesis_map": hypothesis_map}))
            cost = adapter.cost_of("collect")
            ctx.governor.charge(tokens=cost.tokens, money_usd=cost.money_usd,
                                requests=cost.requests)

            prov = ctx.provenance(
                self.name,
                method=AcquisitionMethod.API,
                confidence=0.8,
                tool=adapter.id,
                derived_from=[plan.evidence_request_id],
            )
            ev: EvidenceObject = adapter.normalize(raw, prov)
            ev.addresses_query = plan.evidence_request_id
            ctx.state.add_evidence(ev, ctx.iteration)
            collected.append(ev)
        return collected
