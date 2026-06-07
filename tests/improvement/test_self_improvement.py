"""Phase 8 — Self-Improvement (doc 06): calibration + planner efficiency improve across versions,
strictly behind the evidence/strategy firewall."""

from __future__ import annotations

import pytest

from osintenal.core.runtime import InvestigationController
from osintenal.improvement import (
    assert_strategy_artifacts_only,
    audit_no_evidence_mutation,
    brier_score,
    expected_calibration_error,
    fit_temperature,
    run_self_improvement,
)
from osintenal.improvement.benchmark import CALIBRATION_BENCHMARK
from osintenal.improvement.calibration import predictions_at, reliability_curve
from osintenal.improvement.firewall import FirewallViolation
from osintenal.scenarios import build_demo_investigation


# -- calibration math --------------------------------------------------------
def test_ece_zero_for_perfect_calibration():
    # a prediction at 1.0 that is correct, and at 0.0 that is wrong → perfectly calibrated
    assert expected_calibration_error([(1.0, True), (0.0, False)]) == 0.0


def test_fit_reduces_ece_and_preserves_accuracy():
    before = expected_calibration_error(predictions_at(CALIBRATION_BENCHMARK, 0.5))
    cal = fit_temperature(CALIBRATION_BENCHMARK, version="v2")
    after = expected_calibration_error(predictions_at(CALIBRATION_BENCHMARK, cal.temperature))
    assert after < before                       # calibration error drops
    assert cal.fitted_ece < cal.baseline_ece
    # temperature scaling never changes which hypothesis leads → accuracy is invariant
    acc = lambda t: sum(ok for _, ok in predictions_at(CALIBRATION_BENCHMARK, t))  # noqa: E731
    assert acc(0.5) == acc(cal.temperature)


def test_reliability_curve_and_brier():
    curve = reliability_curve(predictions_at(CALIBRATION_BENCHMARK, 0.5))
    assert curve and all(0 <= b.accuracy <= 1 for b in curve)
    assert brier_score([(1.0, True)]) == 0.0


# -- the tuning loop (exit criterion #1) -------------------------------------
def test_self_improvement_improves_both_levers_across_versions():
    report = run_self_improvement(planner_rounds=4)
    assert report.before.version == "phase1-v1" and report.after.version == "phase8-v2"
    assert report.calibration_improved          # ECE down
    assert report.planner_improved              # tokens down (memory)
    assert report.accuracy_preserved            # calibration ≠ accuracy change
    assert report.improved
    assert report.after.planner_tokens < report.before.planner_tokens
    assert report.after.calibration_ece < report.before.calibration_ece


def test_self_improvement_is_deterministic():
    a, b = run_self_improvement(planner_rounds=3), run_self_improvement(planner_rounds=3)
    assert a.after.model_dump() == b.after.model_dump()


# -- the firewall (exit criterion #2) ----------------------------------------
def test_report_contains_no_evidence_content():
    assert_strategy_artifacts_only(run_self_improvement(planner_rounds=2))  # must not raise


def test_audit_passes_for_strategy_only_action():
    _, registry = build_demo_investigation()
    result = InvestigationController(registry).run(build_demo_investigation()[0])
    # running tuning over a finished investigation touches no evidentiary history
    audit_no_evidence_mutation(result, lambda: run_self_improvement(planner_rounds=2))


def test_audit_detects_evidence_mutation():
    _, registry = build_demo_investigation()
    result = InvestigationController(registry).run(build_demo_investigation()[0])

    def rogue():  # a forbidden action that rewrites recorded confidence history
        h = next(iter(result.state.hypotheses.values()))
        h.confidence_history[0].confidence = 0.999

    with pytest.raises(FirewallViolation):
        audit_no_evidence_mutation(result, rogue)


# -- the calibrator feeds the Confidence model (without changing defaults) ----
def test_calibrator_recalibrates_a_live_run():
    inv, reg = build_demo_investigation()
    default = InvestigationController(reg).run(inv)
    default_conf = default.report.connective_probability_scores[0].ranked_hypotheses[0].confidence

    cal = fit_temperature(CALIBRATION_BENCHMARK, version="phase8-v2")
    inv2, reg2 = build_demo_investigation()
    calibrated = InvestigationController(reg2, calibrator=cal).run(inv2)
    leader = calibrated.report.connective_probability_scores[0].ranked_hypotheses[0]

    assert leader.confidence < default_conf      # less overconfident after recalibration


def test_default_run_is_unchanged_without_a_calibrator(demo_result):
    # no calibrator → default temperature/version → the established demo behavior holds
    leader = demo_result.report.connective_probability_scores[0].ranked_hypotheses[0]
    assert leader.epistemic_class.value == "INSIGHT"
