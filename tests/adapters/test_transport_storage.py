"""The integral storage/replay infrastructure: content-addressed store + cassette transport."""

from __future__ import annotations

import pytest

from osintenal.adapters.storage import CAS_SCHEME, ContentAddressedStore, digest_bytes
from osintenal.adapters.transport import AdapterError, Cassette, HttpClient, request_key


# -- content-addressed store -------------------------------------------------
def test_cas_put_is_deduplicating_and_recoverable(tmp_path):
    cas = ContentAddressedStore(tmp_path)
    data = b"<html>a heavy artifact</html>"
    d1 = cas.put(data)
    d2 = cas.put(data)  # identical bytes
    assert d1 == d2 == digest_bytes(data)
    assert cas.has(d1)
    assert cas.get(d1) == data
    assert cas.resolve(cas.ref(d1)) == data
    assert cas.ref(d1).startswith(CAS_SCHEME)


def test_cas_distinguishes_distinct_content(tmp_path):
    cas = ContentAddressedStore(tmp_path)
    assert cas.put(b"one") != cas.put(b"two")


# -- request keying ----------------------------------------------------------
def test_request_key_is_order_insensitive_over_params():
    a = request_key("GET", "http://x/y", {"a": 1, "b": 2})
    b = request_key("GET", "http://x/y", {"b": 2, "a": 1})
    assert a == b
    assert a != request_key("GET", "http://x/y", {"a": 1, "b": 3})


# -- cassette replay ---------------------------------------------------------
def test_replay_serves_recorded_response(tmp_path):
    cas_path = tmp_path / "c.json"
    cassette = Cassette(cas_path)
    key = request_key("GET", "http://api/x", {"q": "1"})
    cassette.put(key, {"url": "http://api/x", "text": '{"ok": true}'})

    client = HttpClient(Cassette(cas_path), record=False)
    assert client.get_json("http://api/x", {"q": "1"}) == {"ok": True}


def test_missing_cassette_entry_fails_as_data_offline(tmp_path):
    client = HttpClient(Cassette(tmp_path / "empty.json"), record=False)
    with pytest.raises(AdapterError):
        client.get_json("http://api/never-recorded", {"q": "1"})


def test_binary_response_roundtrips_via_base64(tmp_path):
    cas_path = tmp_path / "c.json"
    cassette = Cassette(cas_path)
    raw = bytes(range(256))  # not valid utf-8
    key = request_key("GET", "http://api/blob", None)
    cassette.put(key, HttpClient._encode("http://api/blob", raw))

    client = HttpClient(Cassette(cas_path), record=False)
    assert client.get_bytes("http://api/blob") == raw
