"""Deterministic stub evidence adapter (Phase 1).

Provides a replayable "world" of latent evidence so the full recursive loop can run and be
tested offline with no network or model dependency (doc 06 Phase 1; doc 09 replay). Each
world item declares signed weights against *hypothesis statements*; ``normalize`` maps those
statements onto the live hypothesis ids supplied by the Acquisition Agent and emits a
schema-valid ``EvidenceObject`` with full provenance.

Real Phase 3 adapters replace this while honoring the same ``Adapter`` Protocol.
"""

from __future__ import annotations

from typing import Any

from ..core.schemas import AcquisitionMethod, CostEstimate, EvidenceObject, Provenance
from .base import Adapter, CollectTarget, RawHit


class StubEvidenceAdapter:
    """An ``Adapter`` whose world is a fixed list of latent evidence specs."""

    id = "stub.evidence"
    capabilities = ["stub.evidence", "geo.features", "archive.snapshot", "reference.encyclopedic"]

    def __init__(self, world: list[dict[str, Any]]) -> None:
        self._world = world
        self._consumed: set[str] = set()

    def cost_of(self, operation: str) -> CostEstimate:
        return CostEstimate(tokens=200, money_usd=0.0, seconds=0.05, requests=1)

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        set_tag = arguments.get("set_tag")
        hits: list[RawHit] = []
        for item in self._world:
            if item["id"] in self._consumed:
                continue
            if capability not in item.get("capabilities", ["stub.evidence"]):
                continue
            if set_tag is not None and item.get("set_tag") != set_tag:
                continue
            hits.append(RawHit(hit_id=item["id"], capability=capability, payload=item))
        return hits

    def collect(self, target: CollectTarget) -> dict[str, Any]:
        item = next(i for i in self._world if i["id"] == target.hit_id)
        self._consumed.add(item["id"])
        merged = dict(item)
        merged["hypothesis_map"] = target.arguments.get("hypothesis_map", {})
        return merged

    def parse(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        return [raw]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        hypothesis_map: dict[str, str] = parsed.get("hypothesis_map", {})
        supports: list[str] = []
        contradicts: list[str] = []
        weights: dict[str, float] = {}
        for statement, w in parsed.get("weights", {}).items():
            hid = hypothesis_map.get(statement)
            if hid is None:
                continue
            weights[hid] = float(w)
            (supports if w >= 0 else contradicts).append(hid)
        provenance.source = parsed.get("source", provenance.source)
        provenance.acquisition_method = AcquisitionMethod.API
        provenance.tool_used = self.id
        provenance.license_note = parsed.get("license_note")
        return EvidenceObject(
            kind=parsed.get("kind", "reference"),
            summary=parsed.get("summary", ""),
            structured={
                "independence_group": parsed.get("independence_group", parsed.get("source")),
                "raw_id": parsed["id"],
            },
            supports=supports,
            contradicts=contradicts,
            weights=weights,
            provenance=provenance,
        )

    def remaining(self, set_tag: str | None = None) -> int:
        return len(self.search("stub.evidence", {"set_tag": set_tag}))


# satisfy the runtime Protocol check at import time
_: Adapter = StubEvidenceAdapter(world=[])
