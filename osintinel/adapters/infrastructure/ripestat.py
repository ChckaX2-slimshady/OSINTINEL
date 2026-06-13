"""ASN / network-registration adapter (doc 05 §4, `infra.asn`) via RIPEstat.

Maps an IP to its originating Autonomous System and announced prefix, then names the AS holder —
the network-ownership layer of an OSINT picture (who routes this address). Uses RIPE NCC's keyless,
lawful public data API (``stat.ripe.net``). A light JSON aggregate (two calls fold into one
evidence object); carried inline, no CAS artifact. Independent of DNS / Certificate Transparency,
so it adds a distinct corroboration group.
"""

from __future__ import annotations

from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Observation, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "RIPEstat (RIPE NCC)"


class AsnAdapter(ReferenceAdapter):
    id = "infra.ripestat"
    capabilities = ["infra.asn"]
    license_note = "RIPEstat public data API (free, no key); honor fair-use limits"

    NETWORK_INFO = "https://stat.ripe.net/data/network-info/data.json"
    AS_OVERVIEW = "https://stat.ripe.net/data/as-overview/data.json"

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        ip = arguments["ip"]
        info = (self.client.get_json(self.NETWORK_INFO, {"resource": ip}) or {}).get("data") or {}
        asns = [str(a) for a in (info.get("asns") or [])]
        holders: dict[str, str | None] = {}
        for asn in asns:
            ov = (self.client.get_json(self.AS_OVERVIEW,
                                       {"resource": f"AS{asn}"}) or {}).get("data") or {}
            holders[asn] = ov.get("holder")
        return [RawHit(hit_id=ip, capability=capability,
                       payload={"ip": ip, "prefix": info.get("prefix"),
                                "asns": asns, "holders": holders})]

    def acquire(self, capability: str, arguments: dict[str, Any],
                provenance: Provenance) -> list[EvidenceObject | Observation]:
        hits = self.search(capability, arguments)
        self.last_artifact = self.collect(CollectTarget(hit_id=hits[0].hit_id,
                                                         arguments={"record": hits[0].payload}))
        return self._emit(provenance)

    def collect(self, target: CollectTarget) -> RawArtifact:
        rec = target.arguments["record"]
        return RawArtifact(capability="infra.asn", source=SOURCE,
                           url=f"{self.NETWORK_INFO}?resource={rec['ip']}", structured=rec,
                           license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        r = raw.structured
        return [{"ip": r["ip"], "prefix": r.get("prefix"), "asns": r.get("asns", []),
                 "holders": r.get("holders", {}), "url": raw.url}]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=parsed["url"], method=AcquisitionMethod.API)
        asns = parsed["asns"]
        holders = parsed["holders"]
        if asns:
            named = ", ".join(f"AS{a}" + (f" ({holders[a]})" if holders.get(a) else "")
                              for a in asns)
            summary = (f"{parsed['ip']} is announced by {named}"
                       + (f" within {parsed['prefix']}" if parsed.get("prefix") else ""))
        else:
            summary = f"{parsed['ip']}: no announced ASN found (unrouted or bogon)"
        return EvidenceObject(
            kind="asn_registration",
            summary=summary,
            structured={**parsed, "independence_group": "ripestat"},
            provenance=provenance)
