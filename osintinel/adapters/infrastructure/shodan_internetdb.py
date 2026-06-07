"""Shodan InternetDB adapter (doc 05 §4b free additions, `infra.exposure`).

InternetDB is Shodan's **free, no-key** endpoint: given an IP it returns open ports, hostnames,
detected CPEs (software), tags, and known CVEs — a fast host-exposure snapshot. Lawful and
rate-limited; carried inline (small JSON).
"""

from __future__ import annotations

from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "Shodan InternetDB"


class ShodanInternetDBAdapter(ReferenceAdapter):
    id = "infra.internetdb"
    capabilities = ["infra.exposure"]
    license_note = "Shodan InternetDB (free, no key); honor rate limits"

    API = "https://internetdb.shodan.io"

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        ip = arguments["ip"]
        data = self.client.get_json(f"{self.API}/{ip}")
        return [RawHit(hit_id=ip, capability=capability, payload=data)]

    def acquire(self, capability, arguments, provenance):
        hits = self.search(capability, arguments)
        self.last_artifact = self.collect(CollectTarget(
            hit_id=hits[0].hit_id, arguments={"record": hits[0].payload}))
        return self._emit(provenance)

    def collect(self, target: CollectTarget) -> RawArtifact:
        rec = target.arguments["record"]
        return RawArtifact(capability="infra.exposure", source=SOURCE,
                           url=f"{self.API}/{rec.get('ip', '')}", structured=rec,
                           license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        r = raw.structured
        return [{"ip": r.get("ip"), "ports": r.get("ports", []),
                 "hostnames": r.get("hostnames", []), "cpes": r.get("cpes", []),
                 "tags": r.get("tags", []), "vulns": r.get("vulns", []), "url": raw.url}]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=parsed["url"], method=AcquisitionMethod.API)
        ports = ", ".join(str(p) for p in parsed["ports"][:12])
        vulns = parsed["vulns"]
        vuln_note = f"; {len(vulns)} known CVE(s): {', '.join(vulns[:5])}" if vulns else ""
        return EvidenceObject(
            kind="host_exposure",
            summary=(f"{parsed['ip']}: {len(parsed['ports'])} open port(s) [{ports}]; "
                     f"{len(parsed['hostnames'])} hostname(s){vuln_note}"),
            structured={**parsed, "independence_group": "shodan"},
            provenance=provenance)
