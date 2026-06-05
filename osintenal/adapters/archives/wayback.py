"""Wayback Machine adapter (doc 05 §4, `archive.timemap` / `archive.snapshot`).

This adapter is the worked example of the **integral storage decision**:

* ``search`` hits the CDX index — a small JSON list of snapshots (timestamp, digest). Light.
* ``collect`` fetches a *concrete page snapshot* — potentially large HTML. Those raw bytes are
  pushed into the content-addressed store and the artifact carries only ``content_hash`` /
  ``payload_ref`` (``cas:<sha256>``). The bytes never enter the ledger, so state still replays
  byte-identically while the exact page remains recoverable by hash (doc 05 §5.6).

``parse``/``normalize`` are pure: they read the title/length from the stored bytes and emit a
schema-valid ``EvidenceObject`` whose ``payload_ref`` points at the CAS.
"""

from __future__ import annotations

import re
from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "Internet Archive/Wayback Machine"
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


class WaybackAdapter(ReferenceAdapter):
    id = "archive.wayback"
    capabilities = ["archive.timemap", "archive.snapshot"]
    license_note = "Internet Archive snapshots; cite original publisher & capture timestamp"

    CDX_URL = "http://web.archive.org/cdx/search/cdx"
    SNAPSHOT_URL = "https://web.archive.org/web"

    # -- discovery (light) -------------------------------------------------
    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        rows = self.client.get_json(self.CDX_URL, {
            "url": arguments["url"], "output": "json",
            "limit": arguments.get("limit", 10), "fl": "timestamp,original,digest,statuscode"})
        if not rows:
            return []
        header, *data = rows  # CDX returns a header row first
        hits = []
        for row in data:
            rec = dict(zip(header, row))
            hits.append(RawHit(hit_id=f"{rec['timestamp']}:{rec['original']}",
                               capability="archive.timemap", payload=rec))
        return hits

    # -- fetch the heavy artifact (bytes -> CAS) ---------------------------
    def collect(self, target: CollectTarget) -> RawArtifact:
        rec: dict = target.arguments["record"]
        snap_url = f"{self.SNAPSHOT_URL}/{rec['timestamp']}id_/{rec['original']}"
        body = self.client.get_bytes(snap_url)  # potentially large HTML
        if self.cas is None:
            raise RuntimeError("WaybackAdapter.collect requires a content-addressed store")
        digest = self.cas.put(body)  # dedupes on the page's content hash
        return RawArtifact(
            capability="archive.snapshot", source=SOURCE, url=snap_url,
            content_hash=digest, payload_ref=self.cas.ref(digest),
            structured={"timestamp": rec["timestamp"], "original": rec["original"],
                        "bytes": len(body), "cdx_digest": rec.get("digest")},
            license_note=self.license_note,
        )

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        title = None
        if self.cas is not None and raw.content_hash is not None:
            text = self.cas.get(raw.content_hash).decode("utf-8", errors="replace")
            m = _TITLE_RE.search(text)
            title = m.group(1).strip() if m else None
        return [{
            "title": title, "timestamp": raw.structured["timestamp"],
            "original": raw.structured["original"], "bytes": raw.structured["bytes"],
            "url": raw.url, "content_hash": raw.content_hash, "payload_ref": raw.payload_ref,
        }]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=parsed["url"],
                    method=AcquisitionMethod.ARCHIVE_FETCH, content_hash=parsed["content_hash"])
        ts = parsed["timestamp"]
        human_ts = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        return EvidenceObject(
            kind="archive_snapshot",
            summary=(f"Wayback snapshot of {parsed['original']} captured {human_ts}: "
                     f"{parsed['title'] or '(untitled)'}"),
            payload_ref=parsed["payload_ref"],  # cas:<sha256> — bytes live out-of-band
            structured={
                "timestamp": ts, "original": parsed["original"],
                "title": parsed["title"], "bytes": parsed["bytes"],
                "independence_group": "InternetArchive",
            },
            provenance=provenance,
        )
