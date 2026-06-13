"""DNS-over-HTTPS adapter (doc 05 §4, `infra.dns`) via Google Public DNS.

Resolves a domain's records (A / AAAA / MX / NS / TXT by default) over the keyless, lawful
DNS-over-HTTPS JSON API at ``https://dns.google/resolve``. DNS is an independent corroboration
source (distinct ``independence_group`` from Certificate Transparency or registrar data), so it
strengthens the Confidence Agent's source-independence factor when an entity is a domain. A light
JSON aggregate — many record types fold into one evidence object; carried inline, no CAS artifact.
"""

from __future__ import annotations

from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Observation, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "Google Public DNS (DoH)"
# Record types worth pulling for OSINT: addresses, mail, nameservers, and TXT (SPF/verification).
DEFAULT_TYPES = ("A", "AAAA", "MX", "NS", "TXT")


class DnsAdapter(ReferenceAdapter):
    id = "infra.dns"
    capabilities = ["infra.dns"]
    license_note = "Google Public DNS DoH (free, no key); honor rate limits"

    API = "https://dns.google/resolve"

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        domain = arguments["domain"]
        types = [t.upper() for t in arguments.get("types") or DEFAULT_TYPES]
        records: list[dict[str, Any]] = []
        for rtype in types:
            data = self.client.get_json(self.API, {"name": domain, "type": rtype})
            for ans in data.get("Answer") or []:
                records.append({"type": rtype, "name": ans.get("name"),
                                "data": ans.get("data"), "ttl": ans.get("TTL")})
        return [RawHit(hit_id=domain, capability=capability,
                       payload={"domain": domain, "records": records})]

    def acquire(self, capability: str, arguments: dict[str, Any],
                provenance: Provenance) -> list[EvidenceObject | Observation]:
        # Aggregate: one evidence object summarizing every record type for the domain.
        hits = self.search(capability, arguments)
        self.last_artifact = self.collect(CollectTarget(hit_id=hits[0].hit_id,
                                                         arguments={"record": hits[0].payload}))
        return self._emit(provenance)

    def collect(self, target: CollectTarget) -> RawArtifact:
        rec = target.arguments["record"]
        return RawArtifact(capability="infra.dns", source=SOURCE,
                           url=f"{self.API}?name={rec['domain']}", structured=rec,
                           license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        records = raw.structured["records"]
        by_type: dict[str, list[str]] = {}
        for r in records:
            by_type.setdefault(r["type"], []).append(str(r.get("data", "")))
        return [{
            "domain": raw.structured["domain"],
            "records": records,
            "by_type": by_type,
            "ipv4": by_type.get("A", []),
            "ipv6": by_type.get("AAAA", []),
            "mx": by_type.get("MX", []),
            "ns": by_type.get("NS", []),
            "txt": by_type.get("TXT", []),
            "url": raw.url,
        }]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=parsed["url"], method=AcquisitionMethod.API)
        present = [f"{t}×{len(v)}" for t, v in parsed["by_type"].items() if v]
        kinds = ", ".join(present) if present else "no records"
        ips = ", ".join(parsed["ipv4"][:4])
        ip_note = f"; A → {ips}" if ips else ""
        return EvidenceObject(
            kind="dns_records",
            summary=f"DNS for {parsed['domain']}: {kinds}{ip_note}",
            structured={**parsed, "independence_group": "dns"},
            provenance=provenance)
