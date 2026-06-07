"""SEC EDGAR adapter (doc 05 §4b free additions, `record.public`).

EDGAR is the U.S. SEC's filings system. Its full-text search API (free, no key) returns recent
filings matching a company/person/term — filer names, form types, dates — for corporate and
financial due diligence. SEC asks for a descriptive User-Agent (the transport sets one). Inline.
"""

from __future__ import annotations

from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "SEC EDGAR"


class SECEdgarAdapter(ReferenceAdapter):
    id = "record.sec_edgar"
    capabilities = ["record.public"]
    license_note = "U.S. SEC EDGAR (public domain); set a descriptive User-Agent per SEC policy"

    API = "https://efts.sec.gov/LATEST/search-index"

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        data = self.client.get_json(self.API, {"q": arguments["query"]})
        hits = data.get("hits", {}).get("hits", [])
        return [RawHit(hit_id=str(h.get("_id", i)), capability=capability,
                       payload=h.get("_source", {})) for i, h in enumerate(hits)]

    def acquire(self, capability, arguments, provenance):
        hits = self.search(capability, arguments)
        self.last_artifact = self.collect(CollectTarget(
            hit_id="edgar", arguments={"query": arguments["query"],
                                       "filings": [h.payload for h in hits]}))
        return self._emit(provenance)

    def collect(self, target: CollectTarget) -> RawArtifact:
        return RawArtifact(capability="record.public", source=SOURCE, url=self.API,
                           structured={"query": target.arguments["query"],
                                       "filings": target.arguments["filings"]},
                           license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        rows, filers = [], set()
        for f in raw.structured["filings"]:
            names = f.get("display_names", [])
            filers.update(names)
            rows.append({"filers": names, "form": f.get("file_type") or f.get("root_form"),
                         "date": f.get("file_date")})
        return [{"query": raw.structured["query"], "count": len(rows),
                 "filers": sorted(filers)[:6], "filings": rows[:8]}]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=self.API, method=AcquisitionMethod.API)
        return EvidenceObject(
            kind="public_record",
            summary=(f"SEC EDGAR: {parsed['count']} filing(s) match {parsed['query']!r}"
                     + (f"; filers: {', '.join(parsed['filers'][:3])}" if parsed["filers"] else "")),
            structured={**parsed, "independence_group": "sec_edgar"},
            provenance=provenance)
