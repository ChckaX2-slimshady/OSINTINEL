"""AlienVault OTX adapter (doc 05 §4b free additions, `threat.intel`).

OTX is a large open threat-exchange. The indicators API reports how many community "pulses"
(threat reports) reference a domain/IP and their names/tags — a quick reputation/triage signal.
Uses a **free** API key (``OTX_API_KEY``) sent as a header (never recorded); works in replay
without one. Lawful; carried inline.
"""

from __future__ import annotations

import os
from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "AlienVault OTX"


class OTXAdapter(ReferenceAdapter):
    id = "threat.otx"
    capabilities = ["threat.intel"]
    license_note = "AlienVault OTX (free API key); honor ToS"

    API = "https://otx.alienvault.com/api/v1/indicators"

    def _headers(self) -> dict[str, str]:
        key = os.environ.get("OTX_API_KEY")
        return {"X-OTX-API-KEY": key} if key else {}

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        indicator = arguments["indicator"]
        itype = arguments.get("type", "domain")
        data = self.client.get_json(f"{self.API}/{itype}/{indicator}/general",
                                    headers=self._headers())
        return [RawHit(hit_id=indicator, capability=capability,
                       payload={"indicator": indicator, "type": itype, "data": data})]

    def acquire(self, capability, arguments, provenance):
        hits = self.search(capability, arguments)
        self.last_artifact = self.collect(CollectTarget(
            hit_id=hits[0].hit_id, arguments={"record": hits[0].payload}))
        return self._emit(provenance)

    def collect(self, target: CollectTarget) -> RawArtifact:
        rec = target.arguments["record"]
        return RawArtifact(capability="threat.intel", source=SOURCE,
                           url=f"{self.API}/{rec['type']}/{rec['indicator']}/general",
                           structured=rec, license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        rec = raw.structured
        pulse_info = rec["data"].get("pulse_info", {}) if isinstance(rec["data"], dict) else {}
        pulses = pulse_info.get("pulses", []) or []
        names = [p.get("name", "") for p in pulses if p.get("name")]
        tags = sorted({t for p in pulses for t in (p.get("tags") or [])})
        return [{"indicator": rec["indicator"], "type": rec["type"],
                 "pulse_count": pulse_info.get("count", len(pulses)),
                 "pulse_names": names[:6], "tags": tags[:10], "url": raw.url}]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=parsed["url"], method=AcquisitionMethod.API)
        n = parsed["pulse_count"]
        verdict = "no threat reports" if n == 0 else f"{n} threat report(s)"
        names = f": {'; '.join(parsed['pulse_names'])}" if parsed["pulse_names"] else ""
        return EvidenceObject(
            kind="threat_intel",
            summary=f"OTX — {verdict} reference {parsed['indicator']}{names}",
            structured={**parsed, "independence_group": "otx"},
            provenance=provenance)
