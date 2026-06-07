"""Confidence-calibration records (doc 06 Phase 4 scope): predicted confidence vs. outcome."""

from __future__ import annotations

from osintinel.core.runtime import InvestigationController
from osintinel.memory import InvestigationMemory, build_run_digest
from osintinel.scenarios.learning_benchmark import CORRECT, build_benchmark_investigation


def test_ground_truth_yields_calibration_records():
    investigation, registry = build_benchmark_investigation()
    result = InvestigationController(registry).run(investigation)
    set_id = next(iter(result.state.hypothesis_sets))

    digest = build_run_digest(result, ground_truth={set_id: CORRECT})
    assert len(digest.calibration) == 1
    rec = digest.calibration[0]
    assert 0.0 <= rec.predicted_confidence <= 1.0
    assert isinstance(rec.correct, bool)


def test_calibration_summary_aggregates_across_runs():
    memory = InvestigationMemory()
    for _ in range(3):
        investigation, registry = build_benchmark_investigation()
        result = InvestigationController(registry).run(investigation)
        set_id = next(iter(result.state.hypothesis_sets))
        memory.ingest(build_run_digest(result, ground_truth={set_id: CORRECT}))

    summary = memory.calibration_summary()
    assert summary["records"] == 3
    assert 0.0 <= summary["accuracy"] <= 1.0


def test_no_ground_truth_means_no_calibration():
    investigation, registry = build_benchmark_investigation()
    result = InvestigationController(registry).run(investigation)
    assert build_run_digest(result).calibration == []
