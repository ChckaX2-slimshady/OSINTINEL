"""Self-improvement systems (doc 06 Phase 8).

Recursively improves *strategy* — confidence calibration and planner efficiency — across
versions, behind the same evidence/strategy firewall as Investigation Memory (doc 06 Phase 4):
it learns from outcomes and benchmarks, never from or onto evidentiary history.
"""

from .calibration import (
    Calibrator,
    brier_score,
    expected_calibration_error,
    fit_temperature,
    reliability_curve,
)
from .firewall import assert_strategy_artifacts_only, audit_no_evidence_mutation
from .tuning import SelfImprovementReport, StrategyVersion, run_self_improvement

__all__ = [
    "Calibrator",
    "SelfImprovementReport",
    "StrategyVersion",
    "assert_strategy_artifacts_only",
    "audit_no_evidence_mutation",
    "brier_score",
    "expected_calibration_error",
    "fit_temperature",
    "reliability_curve",
    "run_self_improvement",
]
