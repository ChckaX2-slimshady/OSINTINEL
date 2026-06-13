"""Wikimedia Commons media adapter (doc 05 §4, `archive.media`) via the MediaWiki API.

Searches the free media repository (Wikimedia Commons) for files matching a query — imagery,
maps, diagrams that can corroborate or illustrate an entity, all openly licensed. Uses the keyless
MediaWiki ``api.php`` search endpoint (File namespace). A light JSON list folded into one evidence
object listing the top matches and their Commons pages; carried inline, no CAS artifact.
"""

from __future__ import annotations

from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Observation, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "Wikimedia Commons"
_FILE_NAMESPACE = 6  # MediaWiki "File:" namespace


class WikimediaCommonsAdapter(ReferenceAdapter):
    id = "archive.commons"
    capabilities = ["archive.media"]
    license_note = "Wikimedia Commons (free, no key); media under open licenses — check each file"

    API = "https://commons.wikimedia.org/w/api.php"
    FILE_PAGE = "https://commons.wikimedia.org/wiki/"

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        limit = int(arguments.get("limit", 5))
        data = self.client.get_json(self.API, {
            "action": "query", "list": "search", "srsearch": arguments["query"],
            "srnamespace": _FILE_NAMESPACE, "srlimit": limit, "format": "json"})
        results = ((data or {}).get("query") or {}).get("search") or []
        return [RawHit(hit_id="commons", capability=capability,
                       payload={"query": arguments["query"], "results": results})]

    def acquire(self, capability: str, arguments: dict[str, Any],
                provenance: Provenance) -> list[EvidenceObject | Observation]:
        # Aggregate: many file hits → one evidence object listing the top matches.
        hits = self.search(capability, arguments)
        self.last_artifact = self.collect(CollectTarget(hit_id="commons",
                                                        arguments={"record": hits[0].payload}))
        return self._emit(provenance)

    def collect(self, target: CollectTarget) -> RawArtifact:
        rec = target.arguments["record"]
        return RawArtifact(capability="archive.media", source=SOURCE, url=self.API,
                           structured=rec, license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        files = []
        for r in raw.structured["results"]:
            title = r.get("title", "")
            files.append({"title": title,
                          "page": self.FILE_PAGE + title.replace(" ", "_")})
        return [{"query": raw.structured["query"], "files": files, "count": len(files)}]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=self.API, method=AcquisitionMethod.API)
        titles = "; ".join(f["title"] for f in parsed["files"][:3])
        summary = (f"{parsed['count']} Commons media match(es) for {parsed['query']!r}"
                   + (f": {titles}" if titles else ""))
        return EvidenceObject(
            kind="media_archive",
            summary=summary,
            structured={**parsed, "independence_group": "wikimedia"},
            provenance=provenance)
