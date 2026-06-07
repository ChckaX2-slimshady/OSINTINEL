"""Confidence Agent (doc 02 §8) — explainable, mostly-deterministic confidence.

Confidence is computed in code from six factors and an evidence-weight score, then turned
into a set-normalized probability. The numbers are reproducible; an LLM (when present) would
only author the prose explanation.

Two epistemic effects per update:
* It re-types each hypothesis' backing **explanation** as SPECULATION (low confidence) or
  EXTRAPOLATION (high confidence) — the two explanation types (doc 00 §3).
* It honors the **Skeptic gate**: a hypothesis is promoted to INSIGHT (the backed conclusion)
  only when it reaches the confidence threshold AND has no unresolved blocking finding AND
  has independent corroboration. Otherwise it stays HYPOTHESIS, regardless of confidence
  (doc 03 §16.5).
"""

from __future__ import annotations

from ..core.schemas import (
    AcquisitionMethod,
    AgentName,
    ConfidenceAssessment,
    ConfidenceFactors,
    EpistemicClass,
)
from .base import AgentContext
from .scoring import normalize_with_residual, softmax

CALIBRATION_MODEL_VERSION = "phase1-v1"
INITIAL_RESIDUAL_MASS = 0.20
SOFTMAX_TEMPERATURE = 0.5
MIN_INDEPENDENT_SOURCES = 2  # shared with the Skeptic gate (doc 02 §7)


class ConfidenceAgent:
    name = AgentName.CONFIDENCE

    def run(self, ctx: AgentContext) -> list[ConfidenceAssessment]:
        assessments: list[ConfidenceAssessment] = []
        # A fitted Calibrator (Phase 8) recalibrates the softmax temperature + model version;
        # absent one, the defaults are used (deterministic, unchanged).
        temperature = self._temperature(ctx)
        model_version = self._version(ctx)
        for hs in ctx.state.hypothesis_sets.values():
            active = ctx.state.active_hypotheses(hs.set_id)
            if not active:
                continue

            scores, factors_by_h = [], {}
            for h in active:
                evidence = ctx.state.evidence_for(h.hypothesis_id)
                score = sum(ev.weights.get(h.hypothesis_id, 0.0) for ev in evidence)
                scores.append(score)
                factors_by_h[h.hypothesis_id] = self._factors(ctx, h, evidence)

            probs = softmax(scores, temperature=temperature)

            total_evidence = sum(len(ctx.state.evidence_for(h.hypothesis_id)) for h in active)
            residual = max(0.05, INITIAL_RESIDUAL_MASS * (0.6 ** total_evidence))
            probs = normalize_with_residual(probs, residual)
            ctx.state.set_residual_mass(hs.set_id, round(residual, 4), ctx.iteration)

            for h, p, raw in zip(active, probs, scores):
                conf = round(p, 4)
                ctx.state.update_confidence(
                    h.hypothesis_id, conf,
                    f"recomputed from {len(h.supporting_evidence)} supporting / "
                    f"{len(h.contradicting_evidence)} contradicting evidence (raw score {raw:+.2f})",
                    self.name, ctx.iteration,
                )
                # Record the gated tier (HYPOTHESIS or INSIGHT) as a ledger event so the
                # promotion is auditable and replayable (doc 03 §16.7).
                ctx.state.set_epistemic_class(
                    h.hypothesis_id, self._gated_class(ctx, h, conf), ctx.iteration, self.name)
                # Re-type the backing explanation(s) by confidence (SPECULATION/EXTRAPOLATION).
                for ex_id in h.derived_from_explanations:
                    ctx.state.reclassify_explanation(ex_id, conf, ctx.iteration)

                f = factors_by_h[h.hypothesis_id]
                assessments.append(
                    ConfidenceAssessment(
                        target_ref=h.hypothesis_id,
                        confidence=conf,
                        factors=f,
                        method=f"softmax(score, T={temperature}) * (1 - residual)",
                        explanation=self._explain(h.statement, conf, f, raw),
                        calibration_model_version=model_version,
                        provenance=ctx.provenance(self.name, method=AcquisitionMethod.COMPUTATION,
                                                  confidence=0.9),
                    )
                )
        return assessments

    @staticmethod
    def _temperature(ctx) -> float:
        cal = getattr(ctx, "calibrator", None)
        return cal.temperature if cal is not None else SOFTMAX_TEMPERATURE

    @staticmethod
    def _version(ctx) -> str:
        cal = getattr(ctx, "calibrator", None)
        return cal.version if cal is not None else CALIBRATION_MODEL_VERSION

    def _gated_class(self, ctx, h, conf) -> EpistemicClass:
        """A hypothesis is HYPOTHESIS, or INSIGHT once it is the gate-cleared conclusion.

        Insight emerges from competing hypotheses: the leader is promoted to INSIGHT only when
        it reaches the confidence threshold AND clears the Skeptic gate — no unresolved
        blocking finding AND independent corroboration. The gate is enforced on any confidence
        trajectory, closing the hole where confidence jumps past the threshold before the
        Skeptic has flagged a single-source leader.
        """
        threshold = ctx.investigation.config.confidence_threshold
        if conf >= threshold:
            blocked = ctx.state.unresolved_blocking_findings(h.hypothesis_id)
            independent = len(ctx.state.independent_source_groups(h.hypothesis_id))
            if not blocked and independent >= MIN_INDEPENDENT_SOURCES:
                return EpistemicClass.INSIGHT  # gate cleared: backed conclusion
        return EpistemicClass.HYPOTHESIS  # gate holds promotion

    def _factors(self, ctx, h, evidence) -> ConfidenceFactors:
        support = [e for e in evidence if h.hypothesis_id in e.supports]
        contra = [e for e in evidence if h.hypothesis_id in e.contradicts]
        groups = ctx.state.independent_source_groups(h.hypothesis_id)
        kinds = {e.kind for e in support}
        avg_src = (sum(e.provenance.confidence for e in support) / len(support)) if support else 0.0
        contra_mag = sum(abs(e.weights.get(h.hypothesis_id, 0.0)) for e in contra)
        return ConfidenceFactors(
            source_quality=round(avg_src, 3),
            evidence_diversity=round(min(1.0, len(kinds) / 2.0), 3),
            evidence_quantity=round(min(1.0, len(support) / 3.0), 3),
            contradiction_penalty=round(min(1.0, contra_mag), 3),
            source_independence=round(min(1.0, len(groups) / 2.0), 3),
            temporal_relevance=1.0,
        )

    def _explain(self, statement, conf, f: ConfidenceFactors, raw) -> str:
        return (
            f"{statement!r}: confidence {conf:.2f}. Evidence-weight score {raw:+.2f}; "
            f"quantity {f.evidence_quantity:.2f}, diversity {f.evidence_diversity:.2f}, "
            f"source independence {f.source_independence:.2f}, source quality "
            f"{f.source_quality:.2f}, contradiction penalty {f.contradiction_penalty:.2f}, "
            f"temporal relevance {f.temporal_relevance:.2f}."
        )
