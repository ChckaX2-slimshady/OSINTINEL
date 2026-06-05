"""Aggregation Agent (doc 02 §1) — produces INFORMATION.

Turns raw investigation inputs into normalized, provenance-stamped Observations. It does
not interpret; meaning is the Connections Agent's job (Foundational Separation).
"""

from __future__ import annotations

from ..core.schemas import AcquisitionMethod, AgentName, Observation
from .base import AgentContext


class AggregationAgent:
    name = AgentName.AGGREGATION

    def run(self, ctx: AgentContext) -> list[Observation]:
        # Idempotent: seed inputs are ingested once; re-running yields the existing set.
        if ctx.state.observations:
            return list(ctx.state.observations.values())
        observations: list[Observation] = []
        for item in ctx.investigation.inputs:
            if item.get("kind") != "observation":
                continue
            prov = ctx.provenance(
                self.name,
                method=AcquisitionMethod.HUMAN_PROVIDED,
                confidence=float(item.get("confidence", 1.0)),
                source=item.get("source", "seed"),
            )
            obs = Observation(
                source=item.get("source", "seed"),
                type=item.get("type", "note"),
                content=item.get("content"),
                modality=item.get("modality", "other"),
                confidence=float(item.get("confidence", 1.0)),
                provenance=prov,
                tags=item.get("tags", []),
            )
            ctx.state.add_observation(obs, ctx.iteration)
            observations.append(obs)
        return observations
