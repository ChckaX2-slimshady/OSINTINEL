"""Overpass adapter (doc 05 §4, `geo.features`).

Queries OpenStreetMap features near a coordinate (e.g. masts, towers, tracks) via the Overpass
API. Responses are bounded JSON — summarized inline, no CAS artifact. ``search`` issues the
Overpass QL POST; ``parse``/``normalize`` are pure.
"""

from __future__ import annotations

from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Observation, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "OpenStreetMap/Overpass"


class OverpassAdapter(ReferenceAdapter):
    id = "osm.overpass"
    capabilities = ["geo.features"]
    license_note = "© OpenStreetMap contributors, ODbL"

    API_URL = "https://overpass-api.de/api/interpreter"

    @staticmethod
    def _ql(lat: float, lon: float, radius: int, key: str | None, value: str | None) -> str:
        selector = f'["{key}"]' if key and not value else (
            f'["{key}"="{value}"]' if key else "")
        return (f"[out:json][timeout:25];"
                f"(node{selector}(around:{radius},{lat},{lon});"
                f"way{selector}(around:{radius},{lat},{lon}););out center tags;")

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        ql = self._ql(arguments["lat"], arguments["lon"], arguments.get("radius", 500),
                      arguments.get("key"), arguments.get("value"))
        resp = self.client.post_text(self.API_URL, data="data=" + ql)
        import json
        elements = json.loads(resp).get("elements", [])
        return [RawHit(hit_id=f"{e['type']}/{e['id']}", capability=capability, payload=e)
                for e in elements]

    def acquire(self, capability: str, arguments: dict[str, Any],
                provenance: Provenance) -> list[EvidenceObject | Observation]:
        # Aggregate: one Overpass fetch yields many features → one evidence object each.
        hits = self.search(capability, arguments)
        self.last_artifact = self.collect(CollectTarget(
            hit_id="overpass", arguments={"elements": [h.payload for h in hits]}))
        return self._emit(provenance)

    def collect(self, target: CollectTarget) -> RawArtifact:
        elements = target.arguments["elements"]
        return RawArtifact(capability="geo.features", source=SOURCE, url=self.API_URL,
                           structured={"elements": elements}, license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        out = []
        for e in raw.structured["elements"]:
            tags = e.get("tags", {})
            center = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
            out.append({
                "osm_ref": f"{e['type']}/{e['id']}",
                "tags": tags,
                "lat": center.get("lat"), "lon": center.get("lon"),
                "label": tags.get("man_made") or tags.get("highway")
                or tags.get("name") or "feature",
            })
        return out

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=self.API_URL, method=AcquisitionMethod.API)
        tag_str = ", ".join(f"{k}={v}" for k, v in sorted(parsed["tags"].items()))
        return EvidenceObject(
            kind="osm_feature",
            summary=f"OSM {parsed['osm_ref']} ({parsed['label']}): {tag_str}",
            structured={
                "osm_ref": parsed["osm_ref"], "tags": parsed["tags"],
                "lat": parsed["lat"], "lon": parsed["lon"],
                "independence_group": "OpenStreetMap",
            },
            provenance=provenance,
        )
