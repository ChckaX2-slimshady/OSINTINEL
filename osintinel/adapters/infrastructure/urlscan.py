"""URLScan.io adapter (doc 05 §4b free additions, `infra.urlscan`).

URLScan's **search API is free and no-key** (rate-limited): it returns prior scans of a domain —
the URLs seen, page titles, ASNs, and dates — useful for mapping a target's web surface and
spotting phishing/lookalikes. An optional ``URLSCAN_API_KEY`` raises limits (header only; never
recorded). Lawful; carried inline.
"""

from __future__ import annotations

import os
from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "URLScan.io"


class UrlscanAdapter(ReferenceAdapter):
    id = "infra.urlscan"
    capabilities = ["infra.urlscan"]
    license_note = "URLScan.io public search (free); honor rate limits & ToS"

    API = "https://urlscan.io/api/v1/search/"

    def _headers(self) -> dict[str, str]:
        key = os.environ.get("URLSCAN_API_KEY")
        return {"API-Key": key} if key else {}

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        domain = arguments["domain"]
        data = self.client.get_json(self.API, {"q": f"domain:{domain}",
                                               "size": arguments.get("limit", 10)},
                                    headers=self._headers())
        return [RawHit(hit_id=str(r.get("_id", i)), capability=capability, payload=r)
                for i, r in enumerate(data.get("results", []))]

    def acquire(self, capability, arguments, provenance):
        hits = self.search(capability, arguments)
        self.last_artifact = self.collect(CollectTarget(
            hit_id="urlscan", arguments={"domain": arguments["domain"],
                                         "results": [h.payload for h in hits]}))
        return self._emit(provenance)

    def collect(self, target: CollectTarget) -> RawArtifact:
        return RawArtifact(capability="infra.urlscan", source=SOURCE, url=self.API,
                           structured={"domain": target.arguments["domain"],
                                       "results": target.arguments["results"]},
                           license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        domain = raw.structured["domain"]
        urls, asns = set(), set()
        for r in raw.structured["results"]:
            page = r.get("page", {})
            if page.get("url"):
                urls.add(page["url"])
            if page.get("asnname"):
                asns.add(page["asnname"])
            task = r.get("task", {})
            if task.get("url"):
                urls.add(task["url"])
        return [{"domain": domain, "scans": len(raw.structured["results"]),
                 "urls": sorted(urls)[:15], "asns": sorted(asns)}]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=self.API, method=AcquisitionMethod.API)
        return EvidenceObject(
            kind="urlscan_result",
            summary=(f"{parsed['scans']} prior URLScan(s) of {parsed['domain']}; "
                     f"{len(parsed['urls'])} distinct URL(s)"
                     + (f", ASNs: {', '.join(parsed['asns'][:3])}" if parsed['asns'] else "")),
            structured={**parsed, "independence_group": "urlscan"},
            provenance=provenance)
