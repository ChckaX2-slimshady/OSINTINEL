"""GLEIF adapter (doc 05 §4b free additions, `record.public`).

GLEIF publishes the global Legal Entity Identifier (LEI) registry. The API (free, no key) maps a
legal name to LEI records — entity name, jurisdiction, registration status — authoritative for
resolving and corroborating corporate identities. Lawful; inline.
"""

from __future__ import annotations

from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "GLEIF"


class GLEIFAdapter(ReferenceAdapter):
    id = "record.gleif"
    capabilities = ["record.public"]
    license_note = "GLEIF LEI data (CC0); honor API fair-use"

    API = "https://api.gleif.org/api/v1/lei-records"

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        data = self.client.get_json(self.API, {
            "filter[entity.legalName]": arguments["query"],
            "page[size]": arguments.get("limit", 10)})
        return [RawHit(hit_id=rec.get("id", str(i)), capability=capability, payload=rec)
                for i, rec in enumerate(data.get("data", []))]

    def acquire(self, capability, arguments, provenance):
        hits = self.search(capability, arguments)
        self.last_artifact = self.collect(CollectTarget(
            hit_id="gleif", arguments={"query": arguments["query"],
                                       "records": [h.payload for h in hits]}))
        return self._emit(provenance)

    def collect(self, target: CollectTarget) -> RawArtifact:
        return RawArtifact(capability="record.public", source=SOURCE, url=self.API,
                           structured={"query": target.arguments["query"],
                                       "records": target.arguments["records"]},
                           license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        rows = []
        for rec in raw.structured["records"]:
            attr = rec.get("attributes", {})
            entity = attr.get("entity", {})
            rows.append({
                "lei": attr.get("lei"),
                "name": (entity.get("legalName") or {}).get("name"),
                "country": (entity.get("legalAddress") or {}).get("country"),
                "status": (attr.get("registration") or {}).get("status")})
        return [{"query": raw.structured["query"], "matches": rows}]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=self.API, method=AcquisitionMethod.API)
        rows = parsed["matches"]
        top = "; ".join(f"{r['name']} [{r['lei']}] ({r['country']})" for r in rows[:3])
        return EvidenceObject(
            kind="public_record",
            summary=f"GLEIF: {len(rows)} LEI record(s) for {parsed['query']!r}"
                    + (f" — {top}" if top else ""),
            structured={**parsed, "independence_group": "gleif"},
            provenance=provenance)
