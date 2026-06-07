"""Phase 4 exit criterion #2: the evidence/strategy firewall (doc 06, doc 07).

Memory may not read evidence content nor alter past evidentiary history. These tests assert the
guarantee structurally: digests carry no evidence text, ingest rejects non-digests, the priors
view exposes no mutation surface, and a real run's ledger/confidence history is untouched by
Memory.
"""

from __future__ import annotations

import pytest

from osintinel.core.runtime import InvestigationController
from osintinel.memory import (
    FirewallViolation,
    InvestigationMemory,
    MemoryPriors,
    assert_strategy_only,
    build_run_digest,
    verify_read_only,
)
from osintinel.memory.firewall import assert_no_evidence_leak
from osintinel.scenarios.learning_benchmark import build_benchmark_investigation


def _run_with_memory():
    investigation, registry = build_benchmark_investigation()
    memory = InvestigationMemory()
    result = InvestigationController(registry, memory=memory).run(investigation)
    return result, memory


def test_digest_contains_no_evidence_content():
    result, _ = _run_with_memory()
    digest = build_run_digest(result, registry=None)

    # none of the actual evidence summaries may appear anywhere in the digest
    summaries = [ev.summary for ev in result.state.evidence.values()]
    assert summaries  # the run did acquire evidence
    assert_no_evidence_leak(digest, *summaries)  # raises on leak

    blob = digest.model_dump()
    for forbidden in ("summary", "structured", "weights", "confidence_history", "payload_ref"):
        assert forbidden not in str(blob)


def test_ingest_rejects_non_digest_objects():
    memory = InvestigationMemory()
    result, _ = _run_with_memory()
    some_evidence = next(iter(result.state.evidence.values()))
    with pytest.raises(FirewallViolation):
        memory.ingest(some_evidence)  # an EvidenceObject is not a RunDigest
    with pytest.raises(FirewallViolation):
        memory.ingest({"investigation_id": "x"})  # a raw dict is not a RunDigest


def test_assert_strategy_only_rejects_smuggled_evidence_keys():
    from osintinel.memory.store import RunDigest

    # A subclass that tries to smuggle evidence content past the metric-only contract.
    class Smuggler(RunDigest):
        def model_dump(self, *a, **k):
            data = super().model_dump(*a, **k)
            data["adapter_stats"] = [{"adapter_id": "x", "summary": "secret evidence text"}]
            return data

    with pytest.raises(FirewallViolation):
        assert_strategy_only(Smuggler(investigation_id="x"))


def test_priors_expose_no_mutation_surface():
    priors = MemoryPriors(InvestigationMemory())
    verify_read_only(priors)  # must not raise
    for forbidden in ("ledger", "state", "ingest", "add_evidence", "update_confidence", "save"):
        assert not hasattr(priors, forbidden)


def test_priors_object_with_mutation_surface_is_rejected():
    class LeakyPriors:
        ledger = object()

        def adapter_effectiveness(self, *a, **k):
            return 0.5

    with pytest.raises(FirewallViolation):
        verify_read_only(LeakyPriors())


def test_memory_does_not_alter_ledger_or_confidence_history():
    result, memory = _run_with_memory()

    # the run already ingested into memory; evidentiary history must be intact and verifiable
    assert result.ledger.verify() is True
    before = {h.hypothesis_id: [c.confidence for c in h.confidence_history]
              for h in result.state.hypotheses.values()}

    # any amount of further memory activity touches nothing in the run
    for _ in range(3):
        memory.ingest(build_run_digest(result))
        _ = MemoryPriors(memory).adapter_effectiveness("geo.reliable")

    after = {h.hypothesis_id: [c.confidence for c in h.confidence_history]
             for h in result.state.hypotheses.values()}
    assert after == before
    assert result.ledger.verify() is True
