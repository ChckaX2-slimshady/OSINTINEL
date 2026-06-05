"""INFORMATION-class objects: Observation (doc 03 §2) and EvidenceObject (doc 03 §3)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ids import new_id
from .enums import EpistemicClass
from .provenance import Provenance


class Observation(BaseModel):
    """Aggregation Agent output — expertly aggregated data becomes nuanced information."""

    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(default_factory=new_id)
    epistemic_class: Literal[EpistemicClass.INFORMATION] = EpistemicClass.INFORMATION
    source: str
    type: str
    content: Any
    modality: str = "other"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: Provenance
    tags: list[str] = Field(default_factory=list)


class EvidenceObject(BaseModel):
    """Acquisition Agent output — structured evidence in service of a plan."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(default_factory=new_id)
    epistemic_class: Literal[EpistemicClass.INFORMATION] = EpistemicClass.INFORMATION
    kind: str
    payload_ref: str | None = None
    summary: str
    structured: dict[str, Any] = Field(default_factory=dict)
    supports: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    # signed strength in [-1, 1] per related hypothesis id
    weights: dict[str, float] = Field(default_factory=dict)
    addresses_query: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: Provenance
