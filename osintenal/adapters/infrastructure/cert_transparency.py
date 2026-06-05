"""Certificate Transparency adapter (doc 05 §4, `infra.certs`) via crt.sh.

Looks up logged TLS certificates for a domain — a light JSON list yielding subdomains and
issuance timeline. Public CT logs are an independent corroboration source (distinct
``independence_group`` from DNS/registrar data), which feeds the Confidence Agent's
source-independence factor. Carried inline, no CAS artifact.
"""

from __future__ import annotations

from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Observation, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "crt.sh (Certificate Transparency)"


class CertTransparencyAdapter(ReferenceAdapter):
    id = "infra.crtsh"
    capabilities = ["infra.certs"]
    license_note = "public Certificate Transparency logs"

    API_URL = "https://crt.sh/"

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        rows = self.client.get_json(self.API_URL, {
            "q": arguments["domain"], "output": "json"})
        return [RawHit(hit_id=str(r.get("id", i)), capability=capability, payload=r)
                for i, r in enumerate(rows)]

    def acquire(self, capability: str, arguments: dict[str, Any],
                provenance: Provenance) -> list[EvidenceObject | Observation]:
        # Aggregate: many CT log rows → one evidence object (subdomain/issuer summary).
        hits = self.search(capability, arguments)
        self.last_artifact = self.collect(CollectTarget(
            hit_id="crtsh", arguments={"domain": arguments["domain"],
                                       "rows": [h.payload for h in hits]}))
        return self._emit(provenance)

    def collect(self, target: CollectTarget) -> RawArtifact:
        rows = target.arguments["rows"]
        return RawArtifact(capability="infra.certs", source=SOURCE, url=self.API_URL,
                           structured={"domain": target.arguments["domain"], "rows": rows},
                           license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        names: set[str] = set()
        issuers: set[str] = set()
        earliest = None
        for r in raw.structured["rows"]:
            for nm in str(r.get("name_value", "")).splitlines():
                nm = nm.strip().lstrip("*.")
                if nm:
                    names.add(nm)
            if r.get("issuer_name"):
                issuers.add(r["issuer_name"])
            entry = r.get("not_before")
            if entry and (earliest is None or entry < earliest):
                earliest = entry
        return [{
            "domain": raw.structured["domain"],
            "subdomains": sorted(names),
            "issuers": sorted(issuers),
            "earliest_not_before": earliest,
            "cert_count": len(raw.structured["rows"]),
        }]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, url=self.API_URL, method=AcquisitionMethod.API)
        return EvidenceObject(
            kind="ct_certificates",
            summary=(f"{parsed['cert_count']} CT log entries for {parsed['domain']}; "
                     f"{len(parsed['subdomains'])} distinct names, "
                     f"earliest {parsed['earliest_not_before'] or 'n/a'}"),
            structured={
                "domain": parsed["domain"], "subdomains": parsed["subdomains"],
                "issuers": parsed["issuers"],
                "earliest_not_before": parsed["earliest_not_before"],
                "independence_group": "CertificateTransparency",
            },
            provenance=provenance,
        )
