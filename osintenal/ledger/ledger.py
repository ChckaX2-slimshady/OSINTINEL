"""Append-only, hash-chained provenance ledger (doc 03 §13, doc 04 §1).

The single source of truth for evidentiary history: events are immutable and chained by hash,
which operationalizes "the system may not rewrite evidentiary history." Phase 2 makes the
ledger **durable** — it can be flushed to an append-only JSONL file and reloaded into a
byte-identical event stream, from which the entire knowledge graph is replayable
(``osintenal.ledger.replay``). The same interface admits a SQLite/graph backend later
(doc 04 §1) without touching callers.
"""

from __future__ import annotations

from pathlib import Path

from ..core.ids import content_hash
from ..core.schemas import LedgerEvent


class LedgerIntegrityError(RuntimeError):
    """Raised when the hash chain fails verification or an append is malformed."""


class Ledger:
    """Insert-only event log with a tamper-evident hash chain."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._events: list[LedgerEvent] = []
        # When set, every appended event is also flushed to an append-only JSONL file so the
        # run survives process death (doc 06 Phase 2 vertical slice).
        self._path: Path | None = Path(path) if path is not None else None
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text("")  # start a fresh durable log

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
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(event.model_dump_json() + "\n")
        return event

    # -- durability (doc 04 §8: rebuild-from-ledger is corruption recovery) --
    def save(self, path: str | Path) -> Path:
        """Flush the whole event stream to an append-only JSONL file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            for event in self._events:
                fh.write(event.model_dump_json() + "\n")
        return p

    @classmethod
    def load(cls, path: str | Path, *, verify: bool = True) -> "Ledger":
        """Reconstruct a ledger from a JSONL file; the hash chain is verified on load."""
        led = cls()
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                led._events.append(LedgerEvent.model_validate_json(line))
        if verify:
            led.verify()
        return led

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
