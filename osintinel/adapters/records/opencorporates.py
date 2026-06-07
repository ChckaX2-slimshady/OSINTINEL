"""OpenCorporates adapter (doc 05 §4b free additions, `record.public`).

OpenCorporates is the largest open database of companies. The search API returns matching legal
entities — name, jurisdiction, company number, status — for due-diligence and entity resolution.
Free tier (optional ``OPENCORPORATES_API_TOKEN`` as a query param raises limits). Lawful; inline.
"""

from __future__ import annotations

import os
from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "OpenCorporates"


class OpenCorporatesAdapter(ReferenceAdapter):
    id = "record.opencorporates"
    capabilities = ["record.public"]
    license_note = "OpenCorporates (open data, CC BY-SA where applicable); honor ToS"

    API = "https://api.opencorporates.com/v0.4/companies/search"

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        params = {"q": arguments["query"], "per_page": arguments.get("limit", 10)}
        token = os.environ.get("OPENCORPORATES_API_TOKEN")
        if token:
            params["api_token"] = token
        data = self.client.get_json(self.API, params)
        companies = [c.get("company", {})
                     for c in data.get("results", {}).get("companies", [])]
        return [RawHit(hit_id=c.get("company_number", str(i)), capability=capability, payload=c)
                for i, c in enumerate(companies)]

    def acquire(self, capability, arguments, provenance):
        hits = self.search(capability, arguments)
        self.last_artifact = self.collect(CollectTarget(
            hit_id="opencorporates", arguments={"query": arguments["query"],
                                                "companies": [h.payload for h in hits]}))
        return self._emit(provenance)

    def collect(self, target: CollectTarget) -> RawArtifact:
        return RawArtifact(capability="record.public", source=SOURCE, url=self.API,
                           structured={"query": target.arguments["query"],
                                       "companies": target.arguments["companies"]},
                           license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        rows = [{"name": c.get("name"), "jurisdiction": c.get("jurisdiction_code"),
                 "number": c.get("company_number"), "status": c.get("current_status")}
                for c in raw.structured["companies"]]
        return [{"query": raw.structured["query"], "matches": rows}]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=self.API, method=AcquisitionMethod.API)
        rows = parsed["matches"]
        top = "; ".join(f"{r['name']} ({r['jurisdiction']}, {r['status']})" for r in rows[:3])
        return EvidenceObject(
            kind="public_record",
            summary=f"OpenCorporates: {len(rows)} company match(es) for {parsed['query']!r}"
                    + (f" — {top}" if top else ""),
            structured={**parsed, "independence_group": "opencorporates"},
            provenance=provenance)
