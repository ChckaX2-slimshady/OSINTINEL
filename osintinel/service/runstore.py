"""Durable run history (the Sentinel remembers).

Front-door runs were in-memory only — a restart forgot everything, which undercuts the memory /
self-improvement pillars. This persists a compact, evidence-free **summary** of each run as JSON
under ``~/.osintinel/runs/`` so history survives restarts and the front doors can show a timeline.

It stores only the conclusion surface (question, ranked answers, confidence, known-unknowns,
next-steps) — never raw evidence content, keeping it on the right side of the evidence firewall.
Location is ``$OSINTINEL_HOME/runs`` (default ``~/.osintinel``); set ``OSINTINEL_NO_PERSIST=1`` to
disable, e.g. for a fully ephemeral session. Stdlib only.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path


def default_home() -> Path:
    return Path(os.environ.get("OSINTINEL_HOME") or (Path.home() / ".osintinel"))


def persistence_enabled() -> bool:
    return os.environ.get("OSINTINEL_NO_PERSIST") != "1"


class RunStore:
    """Append-only JSON-per-run history. ``save`` is best-effort and never raises into a run.

    The location is resolved **lazily** on each call (from ``$OSINTINEL_HOME`` unless an explicit
    base is given), so a process-level store instance still honors env changes (and test isolation).
    """

    def __init__(self, base: Path | None = None) -> None:
        self._explicit = base

    @property
    def base(self) -> Path:
        return ((self._explicit or default_home()) / "runs")

    @property
    def dash_base(self) -> Path:
        """Where rendered dashboards live — a sibling of ``runs`` so the compact, evidence-free
        index stays separate from the full operator-facing report HTML."""
        return ((self._explicit or default_home()) / "dashboards")

    def save(self, summary, run_id: str, *, model: str | None = None) -> Path | None:
        if not persistence_enabled():
            return None
        record = asdict(summary) if is_dataclass(summary) else dict(summary)
        record = {"id": run_id, "saved_at": time.time(), "model": model, **record}
        try:
            base = self.base
            base.mkdir(parents=True, exist_ok=True)
            path = base / f"{run_id}.json"
            path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            return path
        except OSError:
            return None  # a read-only/full disk must never break the investigation

    def list(self, limit: int = 50) -> list[dict]:
        """Saved runs, newest first (compact index fields only)."""
        base = self.base
        if not base.exists():
            return []
        records = []
        for path in base.glob("*.json"):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        records.sort(key=lambda r: r.get("saved_at", 0), reverse=True)
        return records[:limit]

    def load(self, run_id: str) -> dict | None:
        try:
            return json.loads((self.base / f"{run_id}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    # -- rendered dashboards (so a run's full report survives a restart) --------
    def save_dashboard(self, run_id: str, html: str) -> Path | None:
        """Persist a run's fully rendered, self-contained dashboard so its History link still
        reconstructs the report after the server restarts. Best-effort; honors the opt-out.

        Unlike the compact summary, this HTML carries the rendered report (evidence summaries,
        graph) — it's the operator's own record, written outside the firewalled digest the Memory
        and self-improvement systems read."""
        if not persistence_enabled():
            return None
        try:
            base = self.dash_base
            base.mkdir(parents=True, exist_ok=True)
            path = base / f"{run_id}.html"
            path.write_text(html, encoding="utf-8")
            return path
        except OSError:
            return None

    def load_dashboard(self, run_id: str) -> str | None:
        try:
            return (self.dash_base / f"{run_id}.html").read_text(encoding="utf-8")
        except OSError:
            return None

    def has_dashboard(self, run_id: str) -> bool:
        return (self.dash_base / f"{run_id}.html").is_file()
