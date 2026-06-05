"""Phase 2 exit criterion: hash-chain integrity holds across persistence (doc 04 §7.6)."""

from __future__ import annotations

import pytest

from osintenal.ledger import Ledger
from osintenal.ledger.ledger import LedgerIntegrityError


def test_save_load_roundtrip_preserves_chain(tmp_path):
    led = Ledger()
    for i in range(6):
        led.append(investigation_id="inv", iteration=i, type="node_add", actor="runtime",
                   payload={"i": i, "nested": {"k": [1, 2, 3]}})
    path = led.save(tmp_path / "l.jsonl")

    reloaded = Ledger.load(path)
    assert len(reloaded) == 6
    assert reloaded.verify() is True
    # event hashes survive the JSON round-trip exactly
    assert [e.event_hash for e in reloaded.events()] == [e.event_hash for e in led.events()]


def test_tampering_with_persisted_file_is_detected(tmp_path):
    led = Ledger()
    led.append(investigation_id="inv", iteration=0, type="node_add", actor="runtime",
               payload={"x": 1})
    led.append(investigation_id="inv", iteration=1, type="node_add", actor="runtime",
               payload={"x": 2})
    path = led.save(tmp_path / "l.jsonl")

    # Forge the payload of the first line; the chain must fail to verify on load.
    lines = path.read_text().splitlines()
    lines[0] = lines[0].replace('"x":1', '"x":999')
    path.write_text("\n".join(lines) + "\n")

    with pytest.raises(LedgerIntegrityError):
        Ledger.load(path)


def test_streaming_append_writes_each_event(tmp_path):
    path = tmp_path / "stream.jsonl"
    led = Ledger(path)
    for i in range(3):
        led.append(investigation_id="inv", iteration=i, type="node_add", actor="runtime",
                   payload={"i": i})
    # the file already holds every event without an explicit save()
    assert len(path.read_text().splitlines()) == 3
    assert Ledger.load(path).verify() is True
