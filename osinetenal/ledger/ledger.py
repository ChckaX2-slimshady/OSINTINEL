"""Append-only, hash-chained provenance ledger.

This is the Phase 1 in-memory realization of the ledger described in doc 03 §13 and
doc 04 §1. It is the source of truth for evidentiary history: events are immutable and
chained by hash, which operationalizes "the system may not rewrite evidentiary history."
A Phase 2 SQLite-backed implementation will satisfy the same interface.
"""

from __future__ import annotations

from ..core.ids import content_hash
from ..core.schemas import LedgerEvent


class LedgerIntegrityError(RuntimeError):
    """Raised when the hash chain fails verification or an append is malformed."""


class Ledger:
    """Insert-only event log with a tamper-evident hash chain."""

    def __init__(self) -> None:
        self._events: list[LedgerEvent] = []

    def append(
        self,
        *,
        investigation_id: str,
        iteration: int,
        type: str,
        actor: str,
        payload: dict | None = None,
    ) -> LedgerEvent:
        prev_hash = self._events[-1].event_hash if self._events else None
        event = LedgerEvent(
            investigation_id=investigation_id,
            iteration=iteration,
            type=type,
            actor=actor,
            payload=payload or {},
            prev_event_hash=prev_hash,
        )
        # The event hash binds the chain link and the event content together.
        event.event_hash = content_hash(
            {
                "event_id": event.event_id,
                "investigation_id": event.investigation_id,
                "iteration": event.iteration,
                "type": event.type,
                "actor": event.actor,
                "payload": event.payload,
                "prev_event_hash": event.prev_event_hash,
                "timestamp": event.timestamp.isoformat(),
            }
        )
        self._events.append(event)
        return event

    def events(self) -> list[LedgerEvent]:
        """Return a copy of the event list (callers must not mutate history)."""
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def verify(self) -> bool:
        """Verify the hash chain end-to-end. Returns True or raises LedgerIntegrityError."""
        prev_hash: str | None = None
        for event in self._events:
            if event.prev_event_hash != prev_hash:
                raise LedgerIntegrityError(
                    f"broken chain at {event.event_id}: prev mismatch"
                )
            recomputed = content_hash(
                {
                    "event_id": event.event_id,
                    "investigation_id": event.investigation_id,
                    "iteration": event.iteration,
                    "type": event.type,
                    "actor": event.actor,
                    "payload": event.payload,
                    "prev_event_hash": event.prev_event_hash,
                    "timestamp": event.timestamp.isoformat(),
                }
            )
            if recomputed != event.event_hash:
                raise LedgerIntegrityError(
                    f"tampered event {event.event_id}: hash mismatch"
                )
            prev_hash = event.event_hash
        return True
