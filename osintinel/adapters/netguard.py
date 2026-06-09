"""SSRF guard (doc 07) — refuse outbound fetches that resolve to non-public addresses.

The autonomous web path follows URLs the operator never vetted — search results, links, an
arbitrary ``web.fetch`` target. Left unguarded, a malicious page could point the fetcher at the
operator's *own* machine: ``http://localhost:11434`` (Ollama), cloud metadata at
``169.254.169.254``, or anything on the private LAN. This module classifies a URL's destination
and blocks loopback / private / link-local / reserved targets **before** the socket is opened, and
re-checks every redirect hop.

It is deliberately **opt-in** on the untrusted web client only — inference calls go to an
operator-configured endpoint (often local Ollama) through the *same* transport, and must keep
working. Set ``OSINTINEL_ALLOW_PRIVATE_NET=1`` to disable the guard (only when you trust the
target — e.g. fetching from a server on your own LAN on purpose). Pure stdlib; no dependency.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import urllib.parse

ALLOW_ENV = "OSINTINEL_ALLOW_PRIVATE_NET"


class BlockedRequestError(RuntimeError):
    """A request was refused because its destination is not a public address (SSRF guard)."""


def _ip_block_reason(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # unwrap ::ffff:127.0.0.1 and friends
    if ip.is_loopback:
        return "loopback"
    if ip.is_link_local:
        return "link-local"
    if ip.is_private:
        return "private"
    if ip.is_reserved:
        return "reserved"
    if ip.is_multicast:
        return "multicast"
    if ip.is_unspecified:
        return "unspecified"
    return None


def classify_ip(ip_str: str) -> str | None:
    """Return a block reason if ``ip_str`` is a non-public literal, else ``None`` (incl. non-IPs)."""
    try:
        return _ip_block_reason(ipaddress.ip_address(ip_str))
    except ValueError:
        return None


def _resolve(host: str) -> list[str]:
    return list({info[4][0] for info in socket.getaddrinfo(host, None)})


def url_block_reason(url: str, *, resolver=_resolve) -> str | None:
    """Reason the URL should be blocked, or ``None`` if it targets a public host."""
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return f"scheme {scheme!r} not allowed"
    host = parsed.hostname
    if not host:
        return "missing host"
    literal = classify_ip(host)
    if literal is not None:
        return literal
    try:
        addresses = resolver(host)
    except OSError:
        return None  # unresolvable → let the normal fetch fail; don't false-block
    for addr in addresses:
        reason = classify_ip(addr)
        if reason is not None:
            return f"{reason} ({addr})"
    return None


def assert_public_url(url: str, *, resolver=_resolve) -> None:
    """Raise :class:`BlockedRequestError` unless ``url`` targets a public address.

    No-op when ``OSINTINEL_ALLOW_PRIVATE_NET=1`` (operator override for trusted private targets)."""
    if os.environ.get(ALLOW_ENV) == "1":
        return
    reason = url_block_reason(url, resolver=resolver)
    if reason is not None:
        raise BlockedRequestError(
            f"refusing to fetch {url}: destination is a non-public address ({reason}). "
            f"Set {ALLOW_ENV}=1 to override (only if you trust the target).")
