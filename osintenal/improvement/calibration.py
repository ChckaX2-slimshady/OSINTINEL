"""Confidence calibration (doc 06 Phase 8, doc 09 calibration harness).

A confidence model is *calibrated* when, among predictions it makes at confidence p, the fraction
that turn out correct is also ≈ p. The Confidence Agent's raw softmax can be over- or
under-confident; this module measures that miscalibration (Expected Calibration Error, Brier
score, a reliability curve) and learns a **temperature** that reduces it.

Temperature scaling is the right knob here because the Confidence Agent already turns evidence
scores into probabilities via ``softmax(scores, T)``: a larger ``T`` flattens overconfident
distributions, a smaller one sharpens underconfident ones. Crucially, ``T`` does **not** change
which hypothesis leads (``argmax`` is T-invariant), so recalibration improves *calibration*
without altering *which* conclusion is reached — and it is a pure function of past
(confidence, outcome) records, never of evidence content (the Phase 4 firewall holds).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..agents.scoring import softmax

# A frozen grid of candidate temperatures (the current default is 0.5, doc 02 Confidence Agent).
TEMPERATURE_GRID = [0.3, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]


def _argmax(scores: list[float]) -> int:
    return max(range(len(scores)), key=lambda i: scores[i])


def leader_confidence(scores: list[float], temperature: float) -> tuple[int, float]:
    """The leading hypothesis index and its set-normalized probability at ``temperature``."""
    probs = softmax(scores, temperature=temperature)
    idx = _argmax(scores)
    return idx, probs[idx]


def predictions_at(cases: list[tuple[list[float], int]], temperature: float
                   ) -> list[tuple[float, bool]]:
    """(confidence, correct) for each benchmark case at a given temperature."""
    out = []
    for scores, correct_index in cases:
        idx, conf = leader_confidence(scores, temperature)
        out.append((conf, idx == correct_index))
    return out


@dataclass
class ReliabilityBin:
    lo: float
    hi: float
    count: int
    mean_confidence: float
    accuracy: float


def reliability_curve(preds: list[tuple[float, bool]], n_bins: int = 10) -> list[ReliabilityBin]:
    bins: list[ReliabilityBin] = []
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        members = [(c, ok) for c, ok in preds if (lo < c <= hi) or (b == 0 and c <= hi)]
        if not members:
            continue
        n = len(members)
        bins.append(ReliabilityBin(
            lo=lo, hi=hi, count=n,
            mean_confidence=sum(c for c, _ in members) / n,
            accuracy=sum(1 for _, ok in members if ok) / n))
    return bins


def expected_calibration_error(preds: list[tuple[float, bool]], n_bins: int = 10) -> float:
    """ECE: weighted average gap between confidence and accuracy across bins."""
    if not preds:
        return 0.0
    total = len(preds)
    return round(sum(b.count / total * abs(b.mean_confidence - b.accuracy)
                     for b in reliability_curve(preds, n_bins)), 6)


def brier_score(preds: list[tuple[float, bool]]) -> float:
    if not preds:
        return 0.0
    return round(sum((c - (1.0 if ok else 0.0)) ** 2 for c, ok in preds) / len(preds), 6)


@dataclass
class Calibrator:
    """A learned recalibration: a temperature for the Confidence Agent's softmax, plus a version."""

    temperature: float
    version: str
    fitted_ece: float = 0.0
    baseline_ece: float = 0.0
    notes: str = ""

    def confidence(self, scores: list[float]) -> float:
        return leader_confidence(scores, self.temperature)[1]


def fit_temperature(cases: list[tuple[list[float], int]], *, version: str,
                    grid: list[float] = TEMPERATURE_GRID,
                    baseline_temperature: float = 0.5) -> Calibrator:
    """Pick the temperature that minimizes ECE on the calibration cases (a frozen benchmark)."""
    baseline_ece = expected_calibration_error(predictions_at(cases, baseline_temperature))
    best_t, best_ece = baseline_temperature, baseline_ece
    for t in grid:
        ece = expected_calibration_error(predictions_at(cases, t))
        if ece < best_ece - 1e-9:
            best_t, best_ece = t, ece
    return Calibrator(temperature=best_t, version=version, fitted_ece=round(best_ece, 6),
                      baseline_ece=round(baseline_ece, 6),
                      notes=f"temperature scaling fit over {len(grid)} candidates")
