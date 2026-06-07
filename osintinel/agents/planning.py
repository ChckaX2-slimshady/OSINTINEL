"""Evidence Planning Agent (doc 02 §3) — produces EvidenceRequests.

Answers "what evidence would most efficiently differentiate the competing hypotheses?"
Optimizes information gain per cost — discriminate, don't accumulate. Expected information
gain is approximated by the current entropy of each set (an undecided set is worth probing);
the score is gain / cost so cheap, discriminating evidence ranks first.
"""

from __future__ import annotations

from ..core.schemas import (
    AcquisitionMethod,
    AgentName,
    CostEstimate,
    EvidenceRequest,
)
from .base import AgentContext
from .scoring import entropy


class EvidencePlanningAgent:
    name = AgentName.EVIDENCE_PLANNING

    def run(self, ctx: AgentContext) -> list[EvidenceRequest]:
        requests: list[EvidenceRequest] = []
        for hs in ctx.state.hypothesis_sets.values():
            active = ctx.state.active_hypotheses(hs.set_id)
            if len(active) < 2:
                continue
            probs = [h.confidence for h in active]
            gain = entropy(probs)  # bits of uncertainty available to resolve
            if gain <= 0.01:
                continue  # already decided; nothing to discriminate

            # Target the two leading competitors — the pair most worth separating.
            top = sorted(active, key=lambda h: h.confidence, reverse=True)[:2]
            cost = CostEstimate(tokens=200, money_usd=0.0, seconds=0.05, requests=1)
            denom = max(cost.tokens, 1)
            prov = ctx.provenance(self.name, method=AcquisitionMethod.DERIVED, confidence=0.7)

            # Candidate capabilities for this investigation; Investigation Memory (if present)
            # reorders them so the historically most effective is tried first, and boosts the
            # request's score so productive lines of inquiry are planned earlier (doc 06 Phase 4).
            fallback = ctx.investigation.config.candidate_capabilities or ["stub.evidence"]
            caps = (ctx.priors.ranked_capabilities(ctx.investigation.domain, fallback)
                    if ctx.priors else fallback)
            score = gain / denom * 1000.0  # info-gain per kilo-token
            if ctx.priors:
                best_cap = max((ctx.priors.capability_score(c) for c in caps), default=0.5)
                score *= 0.5 + best_cap  # learned-effectiveness boost

            req = EvidenceRequest(
                question_ref=hs.set_id,
                description=f"Acquire evidence discriminating: {top[0].statement!r} vs "
                            f"{top[1].statement!r}",
                discriminates_between=[h.hypothesis_id for h in top],
                expected_information_gain=gain,
                estimated_cost=cost,
                score=score,
                candidate_capabilities=caps,
                priority=0,
                provenance=prov,
            )
            requests.append(req)

        requests.sort(key=lambda r: r.score, reverse=True)
        for i, r in enumerate(requests):
            r.priority = i
        return requests
