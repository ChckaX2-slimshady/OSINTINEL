"""Planning artifacts: EvidenceRequest (doc 03 §7) and ToolPlan (doc 03 §8)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ids import new_id
from .provenance import Provenance


class CostEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tokens: int = 0
    money_usd: float = 0.0
    seconds: float = 0.0
    requests: int = 0


class EvidenceRequest(BaseModel):
    """Planner output — discriminating-evidence proposals. Discriminate, don't accumulate."""

    model_config = ConfigDict(extra="forbid")

    evidence_request_id: str = Field(default_factory=new_id)
    question_ref: str  # set_id
    description: str
    discriminates_between: list[str] = Field(default_factory=list)
    expected_information_gain: float = Field(default=0.0, ge=0.0)
    estimated_cost: CostEstimate = Field(default_factory=CostEstimate)
    score: float = 0.0  # info_gain / cost — the planner ranking key
    candidate_capabilities: list[str] = Field(default_factory=list)
    priority: int = 0
    provenance: Provenance


class ToolPlan(BaseModel):
    """Tool Selection output — a concrete, interchangeable adapter choice."""

    model_config = ConfigDict(extra="forbid")

    tool_plan_id: str = Field(default_factory=new_id)
    evidence_request_id: str
    selected_adapter: str
    operation: Literal["search", "lookup", "collect", "parse", "normalize"]
    arguments: dict[str, Any] = Field(default_factory=dict)
    fallback_adapters: list[str] = Field(default_factory=list)
    rationale: str = ""
    expected_cost: CostEstimate = Field(default_factory=CostEstimate)
    provenance: Provenance
