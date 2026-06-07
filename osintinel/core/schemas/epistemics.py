"""KnowledgeStateSnapshot (doc 03 §11) — Knowns / Known Unknowns / UU indicators."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ids import new_id
from .provenance import Provenance


class Known(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str
    evidence_refs: list[str] = Field(default_factory=list)


class KnownUnknown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    blocking: bool = False
    suggested_capabilities: list[str] = Field(default_factory=list)


class UnknownUnknownIndicator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: str
    detail: str
    severity: Literal["low", "medium", "high"] = "low"


class KnowledgeStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = Field(default_factory=new_id)
    investigation_id: str
    iteration: int
    knowns: list[Known] = Field(default_factory=list)
    known_unknowns: list[KnownUnknown] = Field(default_factory=list)
    unknown_unknown_indicators: list[UnknownUnknownIndicator] = Field(default_factory=list)
    hidden_assumptions: list[str] = Field(default_factory=list)
    provenance: Provenance
