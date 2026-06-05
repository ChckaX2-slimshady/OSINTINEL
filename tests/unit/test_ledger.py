"""Unit tests for the append-only, hash-chained provenance ledger (doc 09 §2)."""

from __future__ import annotations

import pytest

from osinetenal.ledger import Ledger
from osinetenal.ledger.ledger import LedgerIntegrityError


def test_chain_verifies():
    led = Ledger()
    for i in range(5):
        led.append(investigation_id="inv", iteration=i, type="node_add",
                   actor="runtime", payload={"i": i})
    assert led.verify() is True
    assert len(led) == 5


def test_tamper_detected():
    led = Ledger()
    led.append(investigation_id="inv", iteration=0, type="node_add", actor="runtime",
               payload={"x": 1})
    led.append(investigation_id="inv", iteration=1, type="node_add", actor="runtime",
               payload={"x": 2})
    # Mutating recorded history must break the chain (no rewriting evidentiary history).
    led._events[0].payload["x"] = 999
    with pytest.raises(LedgerIntegrityError):
        led.verify()
