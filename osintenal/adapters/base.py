"""Standard adapter interface (doc 05 §1).

Every adapter implements the same verbs and emits standardized schemas. The network/IO
boundary (search/lookup/collect) is separated from deterministic transformation
(parse/normalize) so the latter is pure and unit-testable. Phase 1 ships a deterministic
stub; real adapters (Wayback, Nominatim, ExifTool, ...) arrive in Phase 3 behind this
same Protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..core.schemas import CostEstimate, EvidenceObject, Provenance


@dataclass
class RawHit:
    """A discovery result returned by ``search``."""

    hit_id: str
    capability: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectTarget:
    hit_id: str
    arguments: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Adapter(Protocol):
    id: str
    capabilities: list[str]

    def cost_of(self, operation: str) -> CostEstimate: ...

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]: ...

    def collect(self, target: CollectTarget) -> dict[str, Any]: ...

    def parse(self, raw: dict[str, Any]) -> list[dict[str, Any]]: ...

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject: ...
