"""Phase 4 exit criterion #1: Memory measurably improves selection/cost (doc 06)."""

from __future__ import annotations

from osintinel.memory import InvestigationMemory, MemoryPriors, RunDigest
from osintinel.memory.store import AdapterStat
from osintinel.scenarios.learning_benchmark import run_learning_benchmark


def test_memory_learns_effective_adapter_and_lowers_cost():
    memory, rounds = run_learning_benchmark(5)

    # The misleading seed makes the first run pick the noisy adapter; learning corrects it.
    assert rounds[0].selected_adapter == "geo.noisy"
    assert rounds[-1].selected_adapter == "geo.reliable"

    # Learned effectiveness ranks the reliable adapter well above the noisy one.
    assert (memory.adapter_effectiveness("geo.reliable")
            > memory.adapter_effectiveness("geo.noisy"))

    # Rerunning the solved case is measurably cheaper (fewer iterations / tokens).
    assert rounds[-1].tokens < rounds[0].tokens
    assert rounds[-1].iterations < rounds[0].iterations


def test_cost_curve_is_monotonically_non_increasing_after_correction():
    _, rounds = run_learning_benchmark(5)
    tokens = [r.tokens for r in rounds]
    # once corrected (round 1+), cost never climbs back
    assert tokens[1:] == sorted(tokens[1:], reverse=True) or max(tokens[1:]) == min(tokens[1:])
    assert all(t <= tokens[0] for t in tokens[1:])


def _digest_with(adapter_id, capability, contributed) -> RunDigest:
    return RunDigest(
        investigation_id="x", domain="d", reached_insight=contributed,
        leading_confidence=0.9 if contributed else 0.2,
        adapter_stats=[AdapterStat(adapter_id=adapter_id, capabilities=[capability],
                                   evidence_produced=2, contributed=contributed)])


def test_priors_reorder_candidate_capabilities_by_learned_effectiveness():
    memory = InvestigationMemory()
    for _ in range(3):
        memory.ingest(_digest_with("good", "geo.features", True))
    memory.ingest(_digest_with("bad", "stub.evidence", False))
    priors = MemoryPriors(memory)

    assert priors.capability_score("geo.features") > priors.capability_score("stub.evidence")
    # the planner's candidate list gets reordered most-effective-first
    assert priors.ranked_capabilities("d", ["stub.evidence", "geo.features"]) == [
        "geo.features", "stub.evidence"]


def test_unseen_adapter_falls_back_to_default():
    priors = MemoryPriors(InvestigationMemory())
    assert priors.adapter_effectiveness("never.seen", default=0.42) == 0.42


def test_memory_persists_and_reloads(tmp_path):
    memory, _ = run_learning_benchmark(3)
    path = memory.save(tmp_path / "memory.jsonl")

    reloaded = InvestigationMemory(path)
    assert len(reloaded) == len(memory)
    assert (reloaded.adapter_effectiveness("geo.reliable")
            == memory.adapter_effectiveness("geo.reliable"))
