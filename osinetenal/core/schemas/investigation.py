"""Investigation root and its configuration (doc 03 §14)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ids import new_id
from .provenance import utcnow


class Budgets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tokens: int = 1_000_000
    money_usd: float = 100.0
    seconds: float = 3600.0
    requests: int = 1000


class InvestigationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    probability_separation_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    no_improvement_patience: int = Field(default=3, ge=1)
    max_iterations: int = Field(default=25, ge=1)
    budgets: Budgets = Field(default_factory=Budgets)


class Investigation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: str = Field(default_factory=new_id)
    title: str
    objective: str
    domain: str | None = None
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    config: InvestigationConfig = Field(default_factory=InvestigationConfig)
    status: Literal[
        "created", "running", "paused", "terminated", "completed", "error"
    ] = "created"
    current_iteration: int = 0
    hypothesis_sets: list[str] = Field(default_factory=list)
    knowledge_state: str | None = None
    report_ref: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
