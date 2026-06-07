"""Deterministic scoring math shared by the planner and the confidence agent (doc 08 §2).

Keeping these computations in plain code (not in an LLM) makes confidence reproducible and
auditable: the model, when present, only authors explanations — never the numbers.
"""

from __future__ import annotations

import math


def softmax(scores: list[float], temperature: float = 1.0) -> list[float]:
    if not scores:
        return []
    t = max(temperature, 1e-6)
    m = max(scores)
    exps = [math.exp((s - m) / t) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]


def entropy(probs: list[float]) -> float:
    """Shannon entropy in bits; a measure of how undecided a hypothesis set is."""
    return -sum(p * math.log2(p) for p in probs if p > 0.0)


def normalize_with_residual(probs: list[float], residual_mass: float) -> list[float]:
    """Scale a probability vector so it sums to ``1 - residual_mass``."""
    scale = max(0.0, 1.0 - residual_mass)
    total = sum(probs)
    if total <= 0:
        n = len(probs)
        return [scale / n for _ in probs] if n else []
    return [p / total * scale for p in probs]
