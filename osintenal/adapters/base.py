"""Standard adapter interface (doc 05 §1).

Every adapter implements the same verbs and emits standardized schemas. The network/IO
boundary (``search``/``lookup``/``collect``) is separated from deterministic transformation
(``parse``/``normalize``) so the latter is pure and unit-testable. The Phase 1 deterministic
``StubEvidenceAdapter`` and the Phase 3 reference adapters (Nominatim, Overpass, Wayback,
Wikidata, crt.sh) all satisfy this Protocol; the IO verbs go through the cassette transport so
runs replay offline (doc 05 §6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..core.schemas import AcquisitionMethod, CostEstimate, EvidenceObject, Observation, Provenance
from .storage import ContentAddressedStore
from .transport import AdapterError, HttpClient

__all__ = [
    "Adapter",
    "AdapterError",
    "CollectTarget",
    "RawArtifact",
    "RawHit",
    "ReferenceAdapter",
]


@dataclass
class RawHit:
    """A discovery result returned by ``search`` (a candidate/reference, not yet collected)."""

    hit_id: str
    capability: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectTarget:
    hit_id: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawArtifact:
    """The output of ``collect``: structured fields plus, for heavy fetches, a CAS reference.

    Light adapters fill ``structured`` only. Heavy adapters (e.g. a Wayback page snapshot) push
    the raw bytes into the content-addressed store and carry only ``content_hash``/``payload_ref``
    here, so the bytes never travel through the ledger (doc 05 §5.6)."""

    capability: str
    source: str
    structured: dict[str, Any] = field(default_factory=dict)
    url: str | None = None
    content_hash: str | None = None
    payload_ref: str | None = None
    license_note: str | None = None

    def digest(self) -> str:
        """A verifiable hash for this fetch: the CAS digest for heavy artifacts, else a hash of
        the structured payload (so light fetches still carry an integrity reference)."""
        if self.content_hash is not None:
            return self.content_hash
        import hashlib
        import json
        canonical = json.dumps(self.structured, sort_keys=True, separators=(",", ":"),
                               default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@runtime_checkable
class Adapter(Protocol):
    id: str
    capabilities: list[str]

    def cost_of(self, operation: str) -> CostEstimate: ...

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]: ...

    def collect(self, target: CollectTarget) -> Any: ...

    def parse(self, raw: Any) -> list[dict[str, Any]]: ...

    def normalize(self, parsed: dict[str, Any],
                  provenance: Provenance) -> EvidenceObject | Observation: ...


class ReferenceAdapter:
    """Shared base for lawful, public-source Phase 3 adapters (doc 05 §4).

    Holds the cassette-backed HTTP client and (for heavy adapters) the content-addressed store.
    Subclasses implement the verbs; this base supplies cost defaults and a provenance stamp so
    every emitted object carries ``source``/``tool_used``/``content_hash``/``license_note``
    (doc 05 §5.1).
    """

    id: str = "reference.base"
    capabilities: list[str] = []
    license_note: str = "public source; respect provider ToS and rate limits"
    default_cost = CostEstimate(tokens=150, money_usd=0.0, seconds=0.4, requests=1)

    def __init__(self, client: HttpClient | None = None,
                 cas: ContentAddressedStore | None = None) -> None:
        self.client = client
        self.cas = cas
        self.last_artifact: RawArtifact | None = None

    def cost_of(self, operation: str) -> CostEstimate:
        return self.default_cost

    def acquire(self, capability: str, arguments: dict[str, Any],
                provenance: Provenance) -> list[EvidenceObject | Observation]:
        """End-to-end: search → collect (top hit) → parse → normalize.

        The single-record default fits light/heavy point lookups (Nominatim, Wayback, Wikidata).
        Aggregating adapters (Overpass, crt.sh) override this to fold many hits into one fetch.
        ``last_artifact`` is set so the caller can record a lean ``raw_response`` ledger event.
        """
        hits = self.search(capability, arguments)
        if not hits:
            self.last_artifact = None
            return []
        hit = hits[0]
        self.last_artifact = self.collect(CollectTarget(
            hit_id=hit.hit_id,
            arguments={**arguments, "capability": capability, "record": hit.payload}))
        return self._emit(provenance)

    def _emit(self, provenance: Provenance) -> list[EvidenceObject | Observation]:
        """Normalize the parsed items of ``last_artifact``, ensuring every object carries a
        content hash for integrity (doc 05 §5.1) — the CAS digest for heavy fetches, else a
        hash of the structured payload."""
        out: list[EvidenceObject | Observation] = []
        for parsed in self.parse(self.last_artifact):
            obj = self.normalize(parsed, provenance.model_copy(deep=True))
            if obj.provenance.content_hash is None and self.last_artifact is not None:
                obj.provenance.content_hash = self.last_artifact.digest()
            out.append(obj)
        return out

    def _stamp(self, prov: Provenance, *, source: str, url: str | None = None,
               method: AcquisitionMethod = AcquisitionMethod.API,
               content_hash: str | None = None) -> Provenance:
        prov.source = source
        prov.url = url
        prov.acquisition_method = method
        prov.tool_used = self.id
        prov.content_hash = content_hash
        prov.license_note = self.license_note
        return prov
