"""Wikidata adapter (doc 05 §4, `reference.encyclopedic`).

Resolves a Wikidata entity (Q-id) to its label, description, and a small subset of claims.
Light, structured, high-independence reference source — carried inline, no CAS artifact.
``lookup``/``collect`` fetch the entity JSON; ``parse``/``normalize`` are pure.
"""

from __future__ import annotations

from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "Wikidata"


class WikidataAdapter(ReferenceAdapter):
    id = "wikidata.entity"
    capabilities = ["reference.encyclopedic"]
    license_note = "Wikidata content under CC0 1.0"

    ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData"

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        qid = arguments["qid"]
        doc = self.client.get_json(f"{self.ENTITY_URL}/{qid}.json")
        entity = doc["entities"][qid]
        return [RawHit(hit_id=qid, capability=capability, payload=entity)]

    def collect(self, target: CollectTarget) -> RawArtifact:
        entity: dict = target.arguments["record"]
        qid = target.hit_id
        return RawArtifact(capability="reference.encyclopedic", source=SOURCE,
                           url=f"https://www.wikidata.org/wiki/{qid}",
                           structured={"qid": qid, "entity": entity},
                           license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        entity = raw.structured["entity"]
        labels = entity.get("labels", {})
        descs = entity.get("descriptions", {})
        # P625 = coordinate location, when present
        coord = None
        claims = entity.get("claims", {})
        if "P625" in claims:
            try:
                v = claims["P625"][0]["mainsnak"]["datavalue"]["value"]
                coord = {"lat": v["latitude"], "lon": v["longitude"]}
            except (KeyError, IndexError, TypeError):
                coord = None
        return [{
            "qid": raw.structured["qid"],
            "label": labels.get("en", {}).get("value", raw.structured["qid"]),
            "description": descs.get("en", {}).get("value"),
            "coord": coord,
            "claim_count": len(claims),
            "url": raw.url,
        }]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=parsed["url"], method=AcquisitionMethod.API)
        structured: dict[str, Any] = {
            "qid": parsed["qid"], "label": parsed["label"],
            "description": parsed["description"], "claim_count": parsed["claim_count"],
            "independence_group": "Wikidata",
        }
        if parsed["coord"]:
            structured["lat"] = parsed["coord"]["lat"]
            structured["lon"] = parsed["coord"]["lon"]
        return EvidenceObject(
            kind="encyclopedic",
            summary=f"Wikidata {parsed['qid']} — {parsed['label']}: {parsed['description'] or ''}",
            structured=structured,
            provenance=provenance,
        )
