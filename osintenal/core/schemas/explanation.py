"""Explanation (doc 00 §3, doc 03) — the tier between Connection and Hypothesis.

An Explanation is a possible account built from verifiable connections. Per the Foundational
Separation Principle there are exactly **two types**, distinguished by confidence:

    SPECULATION   = Low-Confidence Probability
    EXTRAPOLATION = High-Confidence Probability

Both types are synthesized *into* hypotheses by the Synthesis Agent; competing hypotheses
lead to insight. The explanation's ``epistemic_class`` is therefore always one of
{SPECULATION, EXTRAPOLATION} and is derived from its confidence. Explanations are never
merged with the hypotheses they feed (Foundational Separation).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ids import new_id
from .enums import EpistemicClass, explanation_type_for_confidence
from .provenance import Provenance


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation_id: str = Field(default_factory=new_id)
    set_id: str  # the competing-explanations group (question) it belongs to
    statement: str
    # Always SPECULATION or EXTRAPOLATION — the two explanation types (validated below).
    epistemic_class: EpistemicClass = EpistemicClass.SPECULATION
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    # The hypothesis this explanation has been synthesized into (set by Synthesis).
    hypothesis_id: str | None = None
    derived_from: list[str] = Field(default_factory=list)  # connection / observation ids
    status: Literal["active", "archived", "reactivated"] = "active"
    provenance: Provenance

    def classify(self) -> EpistemicClass:
        """Return (and set) the explanation type implied by the current confidence."""
        self.epistemic_class = explanation_type_for_confidence(self.confidence)
        return self.epistemic_class
