"""Transport robustness: retry transient failures with backoff; throttle per host; fail clean."""

from __future__ import annotations

import urllib.error

import pytest

from osintinel.adapters.transport import AdapterError, Cassette, HttpClient


def _client(tmp_path, **kw) -> HttpClient:
    c = HttpClient(Cassette(tmp_path / "c.json"), mode="live", **kw)
    c._sleep = lambda _s: None  # don't actually sleep in tests
    return c


def test_retries_transient_then_succeeds(tmp_path):
    client = _client(tmp_path, max_retries=2)
    calls = {"n": 0}

    def flaky(_req):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.URLError("connection reset")
        return b"ok"

    client._open = flaky
    assert client.get_bytes("https://example.com/x") == b"ok"
    assert calls["n"] == 3


def test_permanent_error_is_not_retried(tmp_path):
    client = _client(tmp_path, max_retries=3)
    calls = {"n": 0}

    def not_found(_req):
        calls["n"] += 1
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)

    client._open = not_found
    with pytest.raises(AdapterError):
        client.get_bytes("https://example.com/missing")
    assert calls["n"] == 1  # 404 is permanent — one attempt only


def test_retries_exhaust_and_raise(tmp_path):
    client = _client(tmp_path, max_retries=2)

    def always_503(_req):
        raise urllib.error.HTTPError("u", 503, "Unavailable", {}, None)

    client._open = always_503
    with pytest.raises(AdapterError):
        client.get_bytes("https://example.com/x")


def test_min_interval_throttles_same_host(tmp_path):
    client = _client(tmp_path, min_interval=1.0)
    slept: list[float] = []
    client._sleep = slept.append
    client._open = lambda _req: b"ok"
    client.get_bytes("https://throttle.example/a")
    client.get_bytes("https://throttle.example/b")  # second hit within the window → sleeps
    assert any(s > 0 for s in slept)
