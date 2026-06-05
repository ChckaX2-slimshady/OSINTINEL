"""SkepticFinding (doc 03 §9) and ConfidenceAssessment (doc 03 §10)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ids import new_id
from .provenance import Provenance


class SkepticFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(default_factory=new_id)
    target_ref: str
    category: Literal[
        "contradiction",
        "hidden_assumption",
        "reasoning_weakness",
        "source_dependency",
        "alt_explanation",
        "overfit",
    ]
    description: str
    severity: Literal["low", "medium", "high", "blocking"]
    proposed_alternative: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    resolved: bool = False
    provenance: Provenance


class ConfidenceFactors(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_quality: float = 0.0
    evidence_diversity: float = 0.0
    evidence_quantity: float = 0.0
    contradiction_penalty: float = 0.0
    source_independence: float = 0.0
    temporal_relevance: float = 0.0


class ConfidenceAssessment(BaseModel):
    """Explainable confidence — never a bare scalar (doc 02 §8)."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(default_factory=new_id)
    target_ref: str  # hypothesis_id
    confidence: float = Field(ge=0.0, le=1.0)
    factors: ConfidenceFactors
    method: str
    explanation: str
    calibration_model_version: str
    provenance: Provenance
