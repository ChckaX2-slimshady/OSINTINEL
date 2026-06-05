"""Bus envelope (doc 03 §12) and the append-only ledger event (doc 03 §13)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ids import new_id
from .enums import AgentName, EpistemicClass
from .provenance import utcnow


class BudgetSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tokens_used: int = 0
    money_usd: float = 0.0
    seconds: float = 0.0
    requests: int = 0


class AgentMessage(BaseModel):
    """Every inter-agent message rides this envelope; the bus validates it on each hop."""

    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(default_factory=new_id)
    investigation_id: str
    iteration: int
    from_agent: AgentName
    to_agent: AgentName
    intent: Literal["task", "result", "challenge", "error"]
    epistemic_class: EpistemicClass | None = None
    payload: Any = None
    payload_type: str | None = None
    budget_snapshot: BudgetSnapshot = Field(default_factory=BudgetSnapshot)
    timestamp: datetime = Field(default_factory=utcnow)


class LedgerEvent(BaseModel):
    """Append-only provenance ledger event with a tamper-evident hash chain."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=new_id)
    investigation_id: str
    iteration: int
    type: str
    actor: str
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_event_hash: str | None = None
    event_hash: str | None = None
    timestamp: datetime = Field(default_factory=utcnow)
