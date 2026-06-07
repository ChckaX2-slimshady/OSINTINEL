"""Hypothesis, HypothesisSet, SpeculationItem (doc 03 §5, §6).

The central objects of the system. The Hypothesis Preservation Rule is enforced here and
by the runtime: confidence may only be raised, lowered, or archived — never deleted, and
``confidence_history`` is append-only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ids import new_id
from .enums import AgentName, EpistemicClass
from .provenance import Provenance, utcnow


class ConfidenceHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iteration: int
    confidence: float = Field(ge=0.0, le=1.0)
    delta_reason: str
    by_agent: AgentName
    timestamp: datetime = Field(default_factory=utcnow)
    ledger_event_id: str | None = None


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str = Field(default_factory=new_id)
    set_id: str
    statement: str
    # A hypothesis is HYPOTHESIS, or INSIGHT once it is the gate-cleared backed conclusion.
    # It is never SPECULATION/EXTRAPOLATION — those classify the explanations it is built from.
    epistemic_class: EpistemicClass = EpistemicClass.HYPOTHESIS
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: Literal["active", "archived", "reactivated"] = "active"
    # The competing explanations synthesized into this hypothesis (doc 00 §3).
    derived_from_explanations: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    confidence_history: list[ConfidenceHistoryEntry] = Field(default_factory=list)
    skeptic_findings: list[str] = Field(default_factory=list)
    origin: Literal["connections", "skeptic", "speculation", "reactivation"] = "connections"
    provenance: Provenance


class HypothesisSet(BaseModel):
    """A group of competing explanations for a single discriminating question."""

    model_config = ConfigDict(extra="forbid")

    set_id: str = Field(default_factory=new_id)
    question: str
    explanations: list[str] = Field(default_factory=list)  # competing explanations (the tier below)
    hypotheses: list[str] = Field(default_factory=list)     # synthesized from the explanations
    normalized: bool = True
    # Probability reserved for "none of the above" — a first-class UU indicator.
    residual_mass: float = Field(default=0.0, ge=0.0, le=1.0)
    provenance: Provenance


class SpeculationItem(BaseModel):
    """Quarantined possibility. Separate confidence model; never auto-promoted."""

    model_config = ConfigDict(extra="forbid")

    speculation_id: str = Field(default_factory=new_id)
    epistemic_class: Literal[EpistemicClass.SPECULATION] = EpistemicClass.SPECULATION
    statement: str
    speculative_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_limitations: list[str] = Field(default_factory=list)
    would_promote_if: list[str] = Field(default_factory=list)
    provenance: Provenance
