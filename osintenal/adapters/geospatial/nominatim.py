"""Nominatim adapter (doc 05 §4, `geo.geocode` / `geo.reverse_geocode`).

Light, structured source: forward/reverse geocoding over OpenStreetMap. Responses are small
JSON, so the evidence is carried inline in ``structured`` (no CAS artifact) — the cheap end of
the versatility-vs-volume trade-off. ``search`` performs the geocode; ``parse``/``normalize``
are pure.
"""

from __future__ import annotations

from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "OpenStreetMap/Nominatim"


class NominatimAdapter(ReferenceAdapter):
    id = "osm.nominatim"
    capabilities = ["geo.geocode", "geo.reverse_geocode"]
    license_note = "© OpenStreetMap contributors, ODbL; Nominatim usage policy applies"

    SEARCH_URL = "https://nominatim.openstreetmap.org/search"
    REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        if capability == "geo.reverse_geocode":
            rec = self.client.get_json(self.REVERSE_URL, {
                "lat": arguments["lat"], "lon": arguments["lon"], "format": "jsonv2"})
            recs = [rec] if isinstance(rec, dict) else rec
        else:
            recs = self.client.get_json(self.SEARCH_URL, {
                "q": arguments["q"], "format": "jsonv2",
                "limit": arguments.get("limit", 5)})
        return [RawHit(hit_id=str(r.get("place_id", i)), capability=capability, payload=r)
                for i, r in enumerate(recs)]

    def collect(self, target: CollectTarget) -> RawArtifact:
        # Light source: the record is already in hand from search — no second fetch.
        rec: dict = target.arguments["record"]
        osm_url = (f"https://www.openstreetmap.org/{rec.get('osm_type', 'node')}/"
                   f"{rec.get('osm_id', '')}")
        return RawArtifact(capability=target.arguments.get("capability", "geo.geocode"),
                           source=SOURCE, url=osm_url, structured=rec,
                           license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        r = raw.structured
        return [{
            "display_name": r.get("display_name", ""),
            "lat": float(r["lat"]), "lon": float(r["lon"]),
            "category": r.get("category") or r.get("class"),
            "kind": r.get("type"),
            "osm_id": r.get("osm_id"),
            "importance": r.get("importance"),
            "url": raw.url,
        }]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=parsed["url"], method=AcquisitionMethod.API)
        return EvidenceObject(
            kind="geocode",
            summary=f"{parsed['display_name']} @ ({parsed['lat']:.5f}, {parsed['lon']:.5f})",
            structured={
                "lat": parsed["lat"], "lon": parsed["lon"],
                "category": parsed["category"], "feature_kind": parsed["kind"],
                "osm_id": parsed["osm_id"], "importance": parsed["importance"],
                "independence_group": "OpenStreetMap",
            },
            provenance=provenance,
        )
