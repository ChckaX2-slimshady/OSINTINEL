"""Phase 4 learning benchmark (doc 06): Investigation Memory makes a solved case cheaper.

> "After N runs, the planner reorders evidence requests and the selector prefers historically
> effective adapters; rerunning a solved case is measurably cheaper."

Two adapters answer the same capability (``geo.features``):

* ``geo.reliable`` — multi-source, strongly discriminating → the run reaches an INSIGHT fast.
* ``geo.noisy``   — single-source, weak/ambiguous → the gate never clears; the loop grinds to
  its patience limit, burning budget without resolving anything.

The cold registry is seeded with a *misleading* prior (the noisy adapter looks better), so the
first run picks it and is expensive. Memory ingests each run's strategy digest; because the
noisy adapter never contributes to an insight, its learned effectiveness decays below the
reliable adapter's, and subsequent runs switch to the reliable one — converging in fewer
iterations at lower cost. No ground truth or network is needed; the effect is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..adapters import AdapterRegistry, StubEvidenceAdapter
from ..core.runtime import InvestigationController
from ..core.schemas import Budgets, Investigation, InvestigationConfig
from ..memory import InvestigationMemory

QUESTION = "What is the structure at the survey coordinate?"
CORRECT = "communications mast"
CANDIDATES = [CORRECT, "wind turbine", "water tower"]

# Reliable source: two independent groups, strongly favouring the correct answer.
_RELIABLE_WORLD = [
    {"id": "r1", "set_tag": QUESTION, "capabilities": ["geo.features"], "source": "OpenStreetMap",
     "independence_group": "osm", "kind": "map", "license_note": "ODbL",
     "summary": "OSM node man_made=mast at the coordinate.",
     "weights": {CORRECT: 0.85, "wind turbine": -0.3, "water tower": -0.2}},
    {"id": "r2", "set_tag": QUESTION, "capabilities": ["geo.features"], "source": "Wikidata",
     "independence_group": "wikidata", "kind": "reference", "license_note": "CC0",
     "summary": "Wikidata radio mast entity near the coordinate.",
     "weights": {CORRECT: 0.7, "wind turbine": -0.2}},
    {"id": "r3", "set_tag": QUESTION, "capabilities": ["geo.features"], "source": "OpenStreetMap",
     "independence_group": "osm", "kind": "map", "license_note": "ODbL",
     "summary": "OSM access track to a telecom installation.",
     "weights": {CORRECT: 0.6, "water tower": -0.2}},
]

# Noisy source: a single group, weak and ambiguous — can never clear the independence gate.
_NOISY_WORLD = [
    {"id": f"n{i}", "set_tag": QUESTION, "capabilities": ["geo.features"], "source": "rumor_feed",
     "independence_group": "rumor", "kind": "chatter", "license_note": None,
     "summary": f"Unsourced chatter #{i} mentioning a structure.",
     "weights": {CORRECT: 0.12, "wind turbine": 0.1, "water tower": 0.08}}
    for i in range(1, 7)
]


def build_benchmark_investigation() -> tuple[Investigation, AdapterRegistry]:
    """A fresh investigation + registry (fresh stub state) for one benchmark round."""
    investigation = Investigation(
        title="Benchmark: structure identification",
        objective="Identify the structure at the coordinate.",
        domain="geo-benchmark",
        inputs=[{"kind": "question", "question": QUESTION, "candidates": CANDIDATES}],
        config=InvestigationConfig(
            confidence_threshold=0.7,
            probability_separation_threshold=0.4,
            no_improvement_patience=3,
            max_iterations=8,
            candidate_capabilities=["geo.features"],
            budgets=Budgets(tokens=500_000, money_usd=50.0, seconds=600.0, requests=500),
        ),
    )
    registry = AdapterRegistry()
    # Misleading seed: the noisy adapter is registered as the higher prior.
    registry.register(StubEvidenceAdapter(list(_NOISY_WORLD), adapter_id="geo.noisy",
                                          capabilities=["geo.features"]), effectiveness=0.6)
    registry.register(StubEvidenceAdapter(list(_RELIABLE_WORLD), adapter_id="geo.reliable",
                                          capabilities=["geo.features"]), effectiveness=0.5)
    return investigation, registry


@dataclass
class BenchmarkRound:
    selected_adapter: str
    iterations: int
    tokens: int
    reached_insight: bool


def run_learning_benchmark(rounds: int = 4, *, memory: InvestigationMemory | None = None
                           ) -> tuple[InvestigationMemory, list[BenchmarkRound]]:
    """Run the benchmark ``rounds`` times against a shared Memory; return per-round metrics."""
    memory = memory or InvestigationMemory()
    out: list[BenchmarkRound] = []
    for _ in range(rounds):
        investigation, registry = build_benchmark_investigation()
        result = InvestigationController(registry, memory=memory).run(investigation)
        # which geo.features adapter actually produced evidence this round
        used = {ev.provenance.tool_used for ev in result.state.evidence.values()}
        selected = "geo.reliable" if "geo.reliable" in used else (
            "geo.noisy" if "geo.noisy" in used else "none")
        reached = any(h.epistemic_class.value == "INSIGHT" for h in result.state.hypotheses.values())
        out.append(BenchmarkRound(selected_adapter=selected, iterations=result.loop.iterations,
                                  tokens=result.budget.tokens_used, reached_insight=reached))
    return memory, out
