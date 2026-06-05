"""Synthesis Agent (doc 02 §6) — merges evidence, preserves provenance, generates findings.

Never fabricates missing evidence: it only links evidence already acquired to the
hypotheses it bears on. It does not finalize confidence (that is the Confidence Agent) and
cannot promote past the Skeptic gate. At termination it composes the InsightReport.
"""

from __future__ import annotations

from ..core.schemas import AgentName
from .base import AgentContext


class SynthesisAgent:
    name = AgentName.SYNTHESIS

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
