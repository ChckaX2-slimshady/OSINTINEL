"""Semantic source-independence (doc 11 §6, Phase M milestone 2 — the `embed` tier).

Source independence is the backbone of the Confidence model, but a *declared* independence group
can lie: syndication, wire copy, and scrapes make several nominally-distinct sources carry the
**same content**. Counting them as independent over-credits a hypothesis. Embeddings expose this:
if evidence from two different declared groups is near-duplicate, those groups are not actually
independent and should be collapsed.

This module is the embed-tier capability. ``analyze_independence`` takes the declared groups and
the evidence texts plus an embedding function (the gateway's ``embed``) and returns the
*effective* independent groups after collapsing near-duplicates. It is pure and works with any
embedder, including the deterministic one — so it runs offline and in CI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

EmbedFn = Callable[[list[str]], list[list[float]]]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class _UnionFind:
    def __init__(self, items: list[str]) -> None:
        self.parent = {x: x for x in items}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


@dataclass
class IndependenceReport:
    declared: set[str]                       # declared independence groups
    effective: set[str]                      # groups after collapsing near-duplicates
    merged: list[list[str]] = field(default_factory=list)  # clusters of collapsed groups

    @property
    def illusory(self) -> bool:
        return len(self.effective) < len(self.declared)


def analyze_independence(groups: list[str], texts: list[str], embed_fn: EmbedFn, *,
                         threshold: float = 0.92) -> IndependenceReport:
    """Collapse declared groups whose evidence is near-duplicate (cosine ≥ threshold)."""
    declared = set(groups)
    if len(declared) < 2:
        return IndependenceReport(declared=declared, effective=set(declared))

    vectors = embed_fn(texts)
    uf = _UnionFind(sorted(declared))
    n = len(texts)
    for i in range(n):
        for j in range(i + 1, n):
            if groups[i] != groups[j] and cosine(vectors[i], vectors[j]) >= threshold:
                uf.union(groups[i], groups[j])

    clusters: dict[str, list[str]] = {}
    for g in sorted(declared):
        clusters.setdefault(uf.find(g), []).append(g)
    effective = set(clusters)
    merged = [sorted(members) for members in clusters.values() if len(members) > 1]
    return IndependenceReport(declared=declared, effective=effective, merged=merged)
