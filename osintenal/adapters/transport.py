"""Cassette-backed HTTP transport (doc 05 §5.7, §6) — replay-first networking.

Every external call goes through ``HttpClient``, which is **replay-by-default**: it looks the
request up in a cassette (a VCR-style recording keyed by request hash) and returns the recorded
response without touching the network. This is what makes a whole investigation reproducible
offline and in CI — no live endpoints, no flakiness, deterministic bytes.

Recording is opt-in: constructing with ``record=True`` (wired to ``OSINTENAL_RECORD=1``) performs
the real fetch via the stdlib (zero new dependencies) and appends it to the cassette. CI never
records. The request key deliberately ignores volatile headers so recordings stay stable.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class AdapterError(RuntimeError):
    """Typed adapter failure (doc 05 §5.4 'fail as data'): network/ToS/quota/missing-cassette."""


def request_key(method: str, url: str, params: dict[str, Any] | None,
                body: str | None = None) -> str:
    """Stable hash of a request — the cassette key. Order-insensitive over params."""
    norm_params = sorted((params or {}).items())
    canonical = json.dumps([method.upper(), url, norm_params, body], sort_keys=True,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Cassette:
    """A JSON file of ``request_key -> recorded response`` (text/json inline, bytes base64)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._entries: dict[str, dict] = {}
        if self.path.exists():
            self._entries = json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, key: str) -> dict | None:
        return self._entries.get(key)

    def put(self, key: str, entry: dict) -> None:
        self._entries[key] = entry
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._entries, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")

    def __len__(self) -> int:
        return len(self._entries)


class HttpClient:
    """Replay-first HTTP. ``record=False`` (default) never hits the network."""

    def __init__(self, cassette: Cassette, *, record: bool | None = None,
                 user_agent: str = "osintenal/0.3 (+research; contact via repo)") -> None:
        self.cassette = cassette
        self.record = (os.environ.get("OSINTENAL_RECORD") == "1") if record is None else record
        self.user_agent = user_agent

    # -- public verbs ------------------------------------------------------
    def get_json(self, url: str, params: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None) -> Any:
        body = self._fetch("GET", url, params, headers)
        return json.loads(body.decode("utf-8"))

    def get_text(self, url: str, params: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None) -> str:
        return self._fetch("GET", url, params, headers).decode("utf-8", errors="replace")

    def get_bytes(self, url: str, params: dict[str, Any] | None = None,
                  headers: dict[str, str] | None = None) -> bytes:
        return self._fetch("GET", url, params, headers)

    def post_text(self, url: str, data: str,
                  headers: dict[str, str] | None = None) -> str:
        return self._fetch("POST", url, None, headers, body=data).decode("utf-8",
                                                                         errors="replace")

    # -- core --------------------------------------------------------------
    def _fetch(self, method: str, url: str, params: dict[str, Any] | None,
               headers: dict[str, str] | None, body: str | None = None) -> bytes:
        key = request_key(method, url, params, body)
        entry = self.cassette.get(key)
        if entry is not None:
            return self._decode(entry)
        if not self.record:
            raise AdapterError(
                f"no cassette entry for {method} {url} (params={params}); "
                f"run with OSINTENAL_RECORD=1 to record (network-gated)"
            )
        data = self._live_fetch(method, url, params, headers, body)
        self.cassette.put(key, self._encode(url, data))
        return data

    # -- live network (only reached when recording) ------------------------
    def _live_fetch(self, method: str, url: str, params: dict[str, Any] | None,
                    headers: dict[str, str] | None, body: str | None) -> bytes:
        full_url = url
        if params:
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
        req_headers = {"User-Agent": self.user_agent, **(headers or {})}
        data = body.encode("utf-8") if body is not None else None
        req = urllib.request.Request(full_url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (recording only)
                return resp.read()
        except Exception as exc:  # surfaced as data, never an unhandled crash
            raise AdapterError(f"live fetch failed for {full_url}: {exc}") from exc

    # -- (de)serialization -------------------------------------------------
    @staticmethod
    def _encode(url: str, data: bytes) -> dict:
        try:
            return {"url": url, "text": data.decode("utf-8")}
        except UnicodeDecodeError:
            return {"url": url, "b64": base64.b64encode(data).decode("ascii")}

    @staticmethod
    def _decode(entry: dict) -> bytes:
        if "b64" in entry:
            return base64.b64decode(entry["b64"])
        return entry["text"].encode("utf-8")
