"""Unit tests for deterministic scoring math (doc 09 §2)."""

from __future__ import annotations

import math

from osintinel.agents.scoring import entropy, normalize_with_residual, softmax


def test_softmax_sums_to_one():
    p = softmax([1.0, 2.0, 3.0])
    assert math.isclose(sum(p), 1.0, abs_tol=1e-9)
    assert p[2] > p[1] > p[0]


def test_entropy_uniform_is_max():
    assert math.isclose(entropy([0.5, 0.5]), 1.0, abs_tol=1e-9)
    assert entropy([1.0]) == 0.0


def test_normalize_with_residual_reserves_mass():
    out = normalize_with_residual([0.6, 0.4], residual_mass=0.2)
    assert math.isclose(sum(out), 0.8, abs_tol=1e-9)
