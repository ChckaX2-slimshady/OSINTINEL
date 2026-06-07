"""Phase 2 exit criterion: the graph is fully reconstructable from the ledger (doc 06).

Run an investigation, persist the ledger to disk, reload it, replay → state, and assert a
byte-identical state and an identical materialized graph. This is the "kill the process,
reload from the ledger" guarantee.
"""

from __future__ import annotations

from osintinel.graph import build_graph
from osintinel.ledger import Ledger, replay_state


def test_in_memory_replay_is_byte_identical(demo_result):
    replayed = replay_state(demo_result.ledger)
    assert replayed.snapshot() == demo_result.state.snapshot()


def test_disk_roundtrip_reload_and_replay(demo_result, tmp_path):
    path = tmp_path / "ledger.jsonl"
    demo_result.ledger.save(path)

    reloaded = Ledger.load(path)  # verifies the hash chain on load
    assert len(reloaded) == len(demo_result.ledger)
    assert reloaded.verify() is True

    replayed = replay_state(reloaded)
    assert replayed.snapshot() == demo_result.state.snapshot()


def test_graph_reconstructed_from_ledger_matches_live(demo_result):
    live = build_graph(demo_result.state)
    from_ledger = build_graph(replay_state(demo_result.ledger))
    assert from_ledger.summary() == live.summary()


def test_streaming_ledger_file_matches_in_memory(tmp_path):
    # A ledger that streams to disk as it runs reloads to the same events.
    from osintinel.core.runtime import InvestigationController
    from osintinel.scenarios import build_demo_investigation

    inv, reg = build_demo_investigation()
    path = tmp_path / "live.jsonl"
    result = InvestigationController(reg, ledger_path=path).run(inv)

    reloaded = Ledger.load(path)
    assert len(reloaded) == len(result.ledger)
    assert replay_state(reloaded).snapshot() == result.state.snapshot()
