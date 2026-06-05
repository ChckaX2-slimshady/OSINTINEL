"""Synthesis Agent (doc 02 §6) — synthesizes explanations into hypotheses, merges evidence.

Two responsibilities, called at two points of the loop:

* ``synthesize_hypotheses`` (HYPOTHESIZE stage) — synthesizes the competing EXPLANATIONS
  framed by the Connections Agent *into* HYPOTHESES (doc 00 §3). Both explanation types
  (SPECULATION and EXTRAPOLATION) feed this step. For Phase 1 each competing explanation maps
  to one hypothesis carrying a back-reference to it; the architecture supports many:1.
* ``run`` (SYNTHESIZE stage) — merges acquired evidence onto the hypotheses it bears on. It
  never fabricates missing evidence, does not finalize confidence (Confidence Agent's job),
  and cannot promote a hypothesis past the Skeptic gate.
"""

from __future__ import annotations

from ..core.schemas import AcquisitionMethod, AgentName, EpistemicClass, Hypothesis
from .base import AgentContext


class SynthesisAgent:
    name = AgentName.SYNTHESIS

    def synthesize_hypotheses(self, ctx: AgentContext) -> list[Hypothesis]:
        """Synthesize competing explanations into hypotheses (explanations -> hypotheses)."""
        created: list[Hypothesis] = []
        for hs in ctx.state.hypothesis_sets.values():
            for ex in ctx.state.unsynthesized_explanations(hs.set_id):
                prov = ctx.provenance(
                    self.name, method=AcquisitionMethod.DERIVED, confidence=0.5,
                    derived_from=[ex.explanation_id],
                )
                h = Hypothesis(
                    set_id=hs.set_id,
                    statement=ex.statement,
                    confidence=ex.confidence,
                    epistemic_class=EpistemicClass.HYPOTHESIS,
                    derived_from_explanations=[ex.explanation_id],
                    origin="connections",
                    provenance=prov,
                )
                ctx.state.add_hypothesis(h, ctx.iteration)
                ctx.state.update_confidence(
                    h.hypothesis_id, ex.confidence,
                    "synthesized from competing explanation (initial prior)",
                    self.name, ctx.iteration,
                )
                created.append(h)
        return created

    def run(self, ctx: AgentContext) -> None:
        """Attach accumulated evidence to the hypotheses it supports/contradicts."""
        for h in ctx.state.hypotheses.values():
            supporting: list[str] = []
            contradicting: list[str] = []
            for ev in ctx.state.evidence.values():
                if h.hypothesis_id in ev.supports:
                    supporting.append(ev.evidence_id)
                if h.hypothesis_id in ev.contradicts:
                    contradicting.append(ev.evidence_id)
            h.supporting_evidence = supporting
            h.contradicting_evidence = contradicting
