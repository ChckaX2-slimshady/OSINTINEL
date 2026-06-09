"""SSRF guard: block fetches that resolve to non-public addresses, allow public ones."""

from __future__ import annotations

import pytest

from osintinel.adapters.netguard import (
    ALLOW_ENV,
    BlockedRequestError,
    assert_public_url,
    classify_ip,
    url_block_reason,
)


def test_classify_ip_flags_non_public_literals():
    assert classify_ip("127.0.0.1") == "loopback"
    assert classify_ip("169.254.169.254") == "link-local"   # cloud metadata endpoint
    assert classify_ip("10.0.0.5") == "private"
    assert classify_ip("192.168.1.10") == "private"
    assert classify_ip("::1") == "loopback"
    assert classify_ip("::ffff:127.0.0.1") == "loopback"     # IPv4-mapped loopback
    assert classify_ip("8.8.8.8") is None                    # public
    assert classify_ip("not-an-ip") is None                  # names handled by resolution


def test_url_block_reason_uses_injected_resolver():
    public = lambda host: ["93.184.216.34"]      # noqa: E731  (example.com)
    private = lambda host: ["127.0.0.1"]         # noqa: E731  (host resolves to loopback)
    assert url_block_reason("https://example.com/x", resolver=public) is None
    assert "loopback" in url_block_reason("https://sneaky.example/x", resolver=private)
    assert "scheme" in url_block_reason("file:///etc/passwd", resolver=public)
    assert url_block_reason("http://169.254.169.254/latest/meta-data", resolver=public)


def test_assert_public_url_raises_and_can_be_overridden(monkeypatch):
    loopback = lambda host: ["127.0.0.1"]        # noqa: E731
    with pytest.raises(BlockedRequestError):
        assert_public_url("http://internal.local/secret", resolver=loopback)
    monkeypatch.setenv(ALLOW_ENV, "1")           # operator override for trusted LAN targets
    assert_public_url("http://internal.local/secret", resolver=loopback)  # no raise


def test_web_adapter_blocks_private_fetch(monkeypatch):
    from osintinel.adapters.base import CollectTarget
    from osintinel.adapters.transport import AdapterError
    from osintinel.adapters.web.search import WebSearchAdapter

    monkeypatch.setattr("osintinel.adapters.web.search.assert_public_url",
                        lambda url: (_ for _ in ()).throw(BlockedRequestError("loopback")))
    adapter = WebSearchAdapter(client=object(), backend="duckduckgo")
    target = CollectTarget(hit_id="x", arguments={"record": {"url": "http://127.0.0.1:11434/x"}})
    with pytest.raises(AdapterError):
        adapter.collect(target)
