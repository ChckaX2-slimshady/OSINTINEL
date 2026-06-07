"""Frozen self-improvement benchmark (doc 06 Phase 8, doc 09).

A fixed set of decided cases — evidence scores for competing hypotheses plus the ground-truth
correct one — used to measure (and improve) confidence calibration *across versions*. It is
deliberately **net-overconfident** at the Confidence Agent's default temperature (0.5): several
cases have a strong-looking but wrong leader, so the raw model claims ~0.9 where it is right far
less often. A fitted temperature should reduce the calibration error without changing accuracy.

The benchmark is frozen so improvements are comparable run-to-run (the doc-09 calibration
harness contract).
"""

from __future__ import annotations

# Each case: (scores for competing hypotheses, index of the truly-correct hypothesis).
# A mix of confident-correct and confident-WRONG cases makes the default temperature overconfident.
CALIBRATION_BENCHMARK: list[tuple[list[float], int]] = [
    # confident & correct
    ([2.0, 0.1, 0.0], 0),
    ([1.8, 0.2, 0.1], 0),
    ([2.2, 0.0, 0.3], 0),
    ([1.9, 0.4, 0.0], 0),
    ([2.1, 0.1, 0.2], 0),
    # confident but WRONG (the strong leader is not the truth — misleading evidence)
    ([2.0, 0.1, 0.0], 1),
    ([1.8, 0.3, 0.1], 1),
    ([2.2, 0.0, 0.2], 2),
    ([1.9, 0.2, 0.1], 1),
    # genuinely uncertain (near-tie) cases, mixed outcomes
    ([0.6, 0.5, 0.4], 0),
    ([0.5, 0.55, 0.4], 1),
    ([0.5, 0.4, 0.55], 0),
]
