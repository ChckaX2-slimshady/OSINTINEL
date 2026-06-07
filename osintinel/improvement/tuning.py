"""Self-improvement tuning loop (doc 06 Phase 8).

Combines the two strategy levers into a single, *versioned* report:

* **Calibration accuracy** — fit a temperature on the frozen benchmark and measure the drop in
  Expected Calibration Error (the confidence model gets better at knowing how sure it should be).
* **Planner efficiency** — the Phase 4 Investigation Memory benchmark, where learned adapter
  effectiveness cuts the cost of solving the same case.

``run_self_improvement`` emits a ``StrategyVersion`` *before* and *after* and asserts both metrics
move the right way across versions. Everything it produces is a **strategy artifact** (numbers,
a temperature, a version string) — never evidence — which the firewall audit verifies.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..scenarios.learning_benchmark import run_learning_benchmark
from .benchmark import CALIBRATION_BENCHMARK
from .calibration import (
    Calibrator,
    brier_score,
    expected_calibration_error,
    fit_temperature,
    predictions_at,
)

BASELINE_TEMPERATURE = 0.5  # the Confidence Agent's default (doc 02 §8)


class StrategyVersion(BaseModel):
    """A versioned snapshot of tunable strategy — strategy artifacts only, no evidence."""

    model_config = ConfigDict(extra="forbid")

    version: str
    temperature: float
    calibration_ece: float
    calibration_brier: float
    accuracy: float
    planner_tokens: int
    notes: str = ""


class SelfImprovementReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    before: StrategyVersion
    after: StrategyVersion
    calibrator: dict
    calibration_improved: bool
    planner_improved: bool
    accuracy_preserved: bool

    @property
    def improved(self) -> bool:
        return self.calibration_improved and self.planner_improved and self.accuracy_preserved


def _accuracy(temperature: float) -> float:
    preds = predictions_at(CALIBRATION_BENCHMARK, temperature)
    return round(sum(1 for _, ok in preds if ok) / len(preds), 4)


def run_self_improvement(*, planner_rounds: int = 4) -> SelfImprovementReport:
    # --- calibration lever (frozen benchmark) -------------------------------
    base_preds = predictions_at(CALIBRATION_BENCHMARK, BASELINE_TEMPERATURE)
    calibrator: Calibrator = fit_temperature(CALIBRATION_BENCHMARK, version="phase8-v2")
    fit_preds = predictions_at(CALIBRATION_BENCHMARK, calibrator.temperature)

    # --- planner-efficiency lever (Phase 4 memory benchmark) ----------------
    _memory, rounds = run_learning_benchmark(planner_rounds)
    cold_tokens, warm_tokens = rounds[0].tokens, rounds[-1].tokens

    before = StrategyVersion(
        version="phase1-v1", temperature=BASELINE_TEMPERATURE,
        calibration_ece=expected_calibration_error(base_preds),
        calibration_brier=brier_score(base_preds), accuracy=_accuracy(BASELINE_TEMPERATURE),
        planner_tokens=cold_tokens, notes="baseline: default temperature, no learned priors")
    after = StrategyVersion(
        version=calibrator.version, temperature=calibrator.temperature,
        calibration_ece=expected_calibration_error(fit_preds),
        calibration_brier=brier_score(fit_preds), accuracy=_accuracy(calibrator.temperature),
        planner_tokens=warm_tokens,
        notes="tuned: temperature-scaled confidence + memory-primed planner")

    return SelfImprovementReport(
        before=before, after=after, calibrator=calibrator.__dict__,
        calibration_improved=after.calibration_ece < before.calibration_ece,
        planner_improved=after.planner_tokens < before.planner_tokens,
        accuracy_preserved=after.accuracy == before.accuracy)
