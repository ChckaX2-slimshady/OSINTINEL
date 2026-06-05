"""InsightReport (doc 03 §15) — the final deliverable. Every report exposes uncertainty."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ids import new_id
from .enums import EpistemicClass
from .epistemics import KnownUnknown, UnknownUnknownIndicator
from .provenance import utcnow


class RankedHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    statement: str
    confidence: float = Field(ge=0.0, le=1.0)
    epistemic_class: EpistemicClass


class ConnectiveProbabilityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    set_id: str
    question: str
    ranked_hypotheses: list[RankedHypothesis] = Field(default_factory=list)
    residual_mass: float = Field(default=0.0, ge=0.0, le=1.0)


class ReasoningStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int
    claim: str
    epistemic_class: EpistemicClass
    supports: list[str] = Field(default_factory=list)
    agent: str


class InsightReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(default_factory=new_id)
    investigation_id: str
    epistemic_class: Literal[EpistemicClass.INSIGHT] = EpistemicClass.INSIGHT
    executive_summary: str
    information_summary: str
    connective_probability_scores: list[ConnectiveProbabilityScore] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    known_unknowns: list[KnownUnknown] = Field(default_factory=list)
    unknown_unknown_indicators: list[UnknownUnknownIndicator] = Field(default_factory=list)
    speculations: list[str] = Field(default_factory=list)
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    recommended_next_investigations: list[str] = Field(default_factory=list)
    source_appendix: list[dict[str, Any]] = Field(default_factory=list)
    confidence_calibration_note: str = ""
    generated_at: datetime = Field(default_factory=utcnow)
