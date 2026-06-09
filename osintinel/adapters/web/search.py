"""Web research adapters (`web.search` / `web.fetch`) — autonomous open-web evidence.

The piece that lets an investigation *gather its own evidence*: search the open web for a query,
fetch the top results, extract readable text, and emit it as provenance-stamped evidence. Two
lawful, free, **no-key** backends:

* **Wikipedia** (default) — the documented MediaWiki search API + REST page-summary API, returning
  clean plaintext. Unambiguously ToS-compliant.
* **DuckDuckGo** (``lite.duckduckgo.com``) — HTML results parsed best-effort, giving *diverse
  domains* (so multiple independent source groups). Respect robots/ToS and rate limits.

Like every adapter it rides the cassette ``HttpClient`` (record/replay) and stores fetched page
bytes in the content-addressed store; only a snippet + a ``cas:`` ref flow onward. Evidence is
grouped by **registrable domain**, so the embed-tier independence check treats two pages from the
same site as one source (doc 11 §6).
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter
from ..netguard import BlockedRequestError, assert_public_url
from ..transport import AdapterError

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_DDG_RESULT = re.compile(r'<a[^>]+class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                         re.IGNORECASE | re.DOTALL)


def strip_html(raw: str) -> str:
    """Plain text from HTML: drop scripts/styles/tags, unescape entities, collapse whitespace."""
    no_blocks = _SCRIPT_STYLE.sub(" ", raw)
    text = html.unescape(_TAG.sub(" ", no_blocks))
    return _WS.sub(" ", text).strip()


def registrable_domain(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else (host or "web")


class WebSearchAdapter(ReferenceAdapter):
    id = "web.research"
    capabilities = ["web.search", "web.fetch"]
    license_note = "open web via Wikipedia API / DuckDuckGo; respect robots, ToS, rate limits"

    WIKI_SEARCH = "https://en.wikipedia.org/w/api.php"
    WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
    DDG_LITE = "https://lite.duckduckgo.com/lite/"

    def __init__(self, client, cas=None, *, backend: str = "wikipedia") -> None:
        super().__init__(client, cas)
        self.backend = backend

    # -- discovery ---------------------------------------------------------
    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        query = arguments["query"]
        limit = int(arguments.get("limit", 5))
        backend = arguments.get("backend", self.backend)
        hits = self._wikipedia(query, limit) if backend == "wikipedia" \
            else self._duckduckgo(query, limit)
        return [RawHit(hit_id=h["url"], capability="web.search", payload=h) for h in hits]

    def _wikipedia(self, query: str, limit: int) -> list[dict]:
        data = self.client.get_json(self.WIKI_SEARCH, {
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": limit})
        out = []
        for row in data.get("query", {}).get("search", []):
            title = row["title"]
            out.append({"title": title, "snippet": strip_html(row.get("snippet", "")),
                        "url": "https://en.wikipedia.org/wiki/"
                               + urllib.parse.quote(title.replace(" ", "_"))})
        return out

    def _duckduckgo(self, query: str, limit: int) -> list[dict]:
        html_text = self.client.post_text(self.DDG_LITE, data="q=" + urllib.parse.quote(query))
        out = []
        for url, label in _DDG_RESULT.findall(html_text)[:limit]:
            out.append({"title": strip_html(label), "snippet": "", "url": html.unescape(url)})
        return out

    def acquire(self, capability: str, arguments: dict[str, Any], provenance):
        """Search → fetch the top-k results → one evidence object per page (diverse sources)."""
        hits = self.search(capability, arguments)
        out: list = []
        for hit in hits[: int(arguments.get("limit", 5))]:
            self.last_artifact = self.collect(CollectTarget(hit_id=hit.hit_id,
                                                            arguments={"record": hit.payload}))
            out.extend(self._emit(provenance))
        return out

    # -- fetch + extract ---------------------------------------------------
    def collect(self, target: CollectTarget) -> RawArtifact:
        rec = target.arguments["record"]
        url = rec["url"]
        if url.startswith("https://en.wikipedia.org/wiki/"):
            title = url.rsplit("/", 1)[-1]
            data = self.client.get_json(self.WIKI_SUMMARY + title)
            text = data.get("extract", "") or rec.get("snippet", "")
            raw_bytes = json.dumps(data).encode("utf-8")
        else:
            try:  # SSRF guard: never let a discovered URL point at our own/LAN services
                assert_public_url(url)
            except BlockedRequestError as exc:
                raise AdapterError(str(exc)) from exc
            raw_bytes = self.client.get_bytes(url)
            text = strip_html(raw_bytes.decode("utf-8", errors="replace"))
        digest = self.cas.put(raw_bytes) if self.cas is not None else None
        return RawArtifact(
            capability="web.fetch", source=registrable_domain(url), url=url,
            content_hash=digest, payload_ref=self.cas.ref(digest) if digest else None,
            structured={"title": rec.get("title", url), "domain": registrable_domain(url),
                        "text": text[:2000], "snippet": rec.get("snippet", "")},
            license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        s = raw.structured
        excerpt = (s.get("text") or s.get("snippet") or "").strip()
        return [{"title": s["title"], "domain": s["domain"], "url": raw.url,
                 "excerpt": excerpt[:400], "content_hash": raw.content_hash,
                 "payload_ref": raw.payload_ref}]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=parsed["domain"], url=parsed["url"],
                    method=AcquisitionMethod.SCRAPE, content_hash=parsed["content_hash"])
        return EvidenceObject(
            kind="web_page", summary=f"{parsed['title']} — {parsed['excerpt']}",
            payload_ref=parsed["payload_ref"],
            structured={"title": parsed["title"], "url": parsed["url"],
                        "domain": parsed["domain"], "independence_group": parsed["domain"]},
            provenance=provenance)
