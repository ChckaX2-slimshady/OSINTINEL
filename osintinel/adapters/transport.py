"""Cassette-backed HTTP transport (doc 05 §5.7, §6) — replay-first networking.

Every external call goes through ``HttpClient``, which is **replay-by-default**: it looks the
request up in a cassette (a VCR-style recording keyed by request hash) and returns the recorded
response without touching the network. This is what makes a whole investigation reproducible
offline and in CI — no live endpoints, no flakiness, deterministic bytes.

Recording is opt-in: constructing with ``record=True`` (wired to ``OSINTINEL_RECORD=1``) performs
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
            try:
                self._entries = json.loads(self.path.read_text(encoding="utf-8")) or {}
            except json.JSONDecodeError as exc:  # corrupt recording → clear, typed failure
                raise AdapterError(f"cassette {self.path} is not valid JSON: {exc}") from exc

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
    """Cassette-backed HTTP with three modes (doc 11 §5):

    * ``replay`` — serve from the cassette; error if missing. Deterministic/offline; the CI default.
    * ``record`` — serve from the cassette if present, else fetch live and persist it (build the
      recorded test corpus).
    * ``live``   — fetch live every call, ignoring the cassette (online-first production).

    The mode is resolved from (in order) an explicit ``mode=``, the legacy ``record=`` bool, the
    ``OSINTINEL_NET`` env (``replay``/``record``/``live``), then ``OSINTINEL_RECORD=1`` → record,
    else ``replay``.
    """

    def __init__(self, cassette: Cassette, *, record: bool | None = None,
                 mode: str | None = None,
                 user_agent: str = "osintinel/0.4 (+research; contact via repo)",
                 block_private_net: bool = False) -> None:
        self.cassette = cassette
        self.mode = self._resolve_mode(record, mode)
        self.user_agent = user_agent
        # SSRF guard for the *untrusted web* path: validate the target and every redirect hop.
        # Off by default so inference calls to a local/operator endpoint (Ollama) still work.
        self.block_private_net = block_private_net

    @staticmethod
    def _resolve_mode(record: bool | None, mode: str | None) -> str:
        if mode is not None:
            return mode
        if record is True:
            return "record"
        if record is False:
            return "replay"
        net = os.environ.get("OSINTINEL_NET")
        if net in ("replay", "record", "live"):
            return net
        return "record" if os.environ.get("OSINTINEL_RECORD") == "1" else "replay"

    @property
    def record(self) -> bool:  # backward-compatible accessor
        return self.mode == "record"

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
        if self.mode != "live":  # live always fetches fresh; replay/record consult the cassette
            entry = self.cassette.get(key)
            if entry is not None:
                return self._decode(entry)
        if self.mode == "replay":
            raise AdapterError(
                f"no cassette entry for {method} {url} (params={params}); "
                f"set OSINTINEL_NET=live to fetch, or =record to record (network-gated)"
            )
        data = self._live_fetch(method, url, params, headers, body)
        if self.mode == "record":
            self.cassette.put(key, self._encode(url, data))
        return data

    # -- live network (reached in record/live modes) -----------------------
    def _live_fetch(self, method: str, url: str, params: dict[str, Any] | None,
                    headers: dict[str, str] | None, body: str | None) -> bytes:
        full_url = url
        if params:
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
        req_headers = {"User-Agent": self.user_agent, **(headers or {})}
        data = body.encode("utf-8") if body is not None else None
        req = urllib.request.Request(full_url, data=data, headers=req_headers, method=method)
        try:
            if self.block_private_net:
                from .netguard import assert_public_url  # local import avoids an import cycle

                assert_public_url(full_url)
                opener = urllib.request.build_opener(_GuardedRedirectHandler())
                with opener.open(req, timeout=30) as resp:  # noqa: S310 (guarded, recording only)
                    return resp.read()
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


class _GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validate each redirect target so a public URL can't bounce us to a private one."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        from .netguard import assert_public_url

        assert_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)
