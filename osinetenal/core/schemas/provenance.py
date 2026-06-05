"""Provenance (doc 03 §1) — attached to everything. Nothing enters state without it."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from .enums import AcquisitionMethod, AgentName


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Provenance(BaseModel):
    """The single most important schema. Every conclusion is traceable through this."""

    model_config = ConfigDict(extra="forbid")

    source: str
    url: str | None = None
    timestamp: datetime = Field(default_factory=utcnow)
    acquisition_method: AcquisitionMethod
    tool_used: str | None = None
    agent_responsible: AgentName
    confidence: float = Field(ge=0.0, le=1.0)
    investigation_id: str
    ledger_event_id: str | None = None  # set by the runtime when persisted
    derived_from: list[str] = Field(default_factory=list)
    content_hash: str | None = None
    license_note: str | None = None
