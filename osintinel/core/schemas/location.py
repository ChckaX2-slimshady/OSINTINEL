"""Location node (doc 04 §2) — a geographic place with a calibrated confidence radius.

Produced by geospatial reasoning (doc 06 Phase 6): intersecting several *independent* spatial
constraints narrows the feasible region to a centroid plus an uncertainty radius. The radius is
the headline honesty feature — a point estimate without a radius would overclaim precision.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..ids import new_id
from .enums import EpistemicClass
from .provenance import Provenance


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: str = Field(default_factory=new_id)
    # A located place is a conclusion, not raw information — it carries an epistemic class.
    epistemic_class: EpistemicClass = EpistemicClass.HYPOTHESIS
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    confidence_radius_km: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    label: str | None = None
    admin: dict = Field(default_factory=dict)          # admin hierarchy (country/region/…)
    constraint_refs: list[str] = Field(default_factory=list)  # constraints that narrowed it
    provenance: Provenance | None = None
