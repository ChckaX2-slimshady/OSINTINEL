"""Investigation Memory store (doc 01 §2.5, doc 06 Phase 4).

Memory learns *strategy* — which adapters, capabilities, and plans tend to work — from the
**structure and metrics** of completed runs. It never holds evidence content, and it has no
write path to the ledger or graph (the firewall, ``memory/firewall.py``): it can inform *how*
the system investigates, but it may not rewrite evidentiary history.

The unit of learning is a ``RunDigest``: a whitelist of strategy/outcome metrics produced by
``memory.digest.build_run_digest`` (the only bridge from a live run). Aggregated priors are
exposed to the planner/selector through ``memory.priors.MemoryPriors``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..core.schemas.provenance import utcnow


class AdapterStat(BaseModel):
    """Per-adapter strategy metrics for one run. No evidence content — counts and ids only."""

    model_config = ConfigDict(extra="forbid")

    adapter_id: str
    capabilities: list[str] = Field(default_factory=list)
    evidence_produced: int = 0
    # Did this adapter produce evidence supporting the leader of a *resolved* run (one that
    # reached the confidence threshold or a gate-cleared insight)? The effectiveness signal.
    contributed: bool = False
    cost_tokens: int = 0


class CalibrationRecord(BaseModel):
    """A confidence-vs-outcome point, recorded only when a benchmark ground truth is known."""

    model_config = ConfigDict(extra="forbid")

    predicted_confidence: float = Field(ge=0.0, le=1.0)
    correct: bool


class RunDigest(BaseModel):
    """The firewalled summary of a completed run — strategy/metrics only (no evidence text)."""

    model_config = ConfigDict(extra="forbid")

    investigation_id: str
    domain: str | None = None
    set_count: int = 0
    iterations: int = 0
    termination_reason: str = ""
    reached_insight: bool = False
    leading_confidence: float = 0.0
    cost: dict[str, float] = Field(default_factory=dict)  # tokens/money_usd/requests/seconds
    adapter_stats: list[AdapterStat] = Field(default_factory=list)
    capability_sequence: list[str] = Field(default_factory=list)
    calibration: list[CalibrationRecord] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: utcnow().isoformat())


class InvestigationMemory:
    """Append-only collection of ``RunDigest``s with learned-strategy aggregates.

    Effectiveness is a smoothed success rate (Beta/Laplace prior of 0.5), so a single result
    never swings a prior and an unseen adapter falls back to the caller's default.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.runs: list[RunDigest] = []
        self._path = Path(path) if path is not None else None
        if self._path is not None and self._path.exists():
            self.load(self._path)

    # -- ingest (firewalled) ------------------------------------------------
    def ingest(self, digest: RunDigest) -> None:
        from .firewall import assert_strategy_only  # local import avoids cycle at module load
        assert_strategy_only(digest)
        self.runs.append(digest)
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(digest.model_dump_json() + "\n")

    # -- learned priors -----------------------------------------------------
    def _adapter_counts(self, adapter_id: str) -> tuple[int, int]:
        uses = successes = 0
        for run in self.runs:
            for s in run.adapter_stats:
                if s.adapter_id == adapter_id:
                    uses += 1
                    successes += int(s.contributed)
        return successes, uses

    def adapter_effectiveness(self, adapter_id: str, default: float = 0.5) -> float:
        successes, uses = self._adapter_counts(adapter_id)
        if uses == 0:
            return default
        return (successes + 1) / (uses + 2)  # Laplace-smoothed, prior mean 0.5

    def _capability_counts(self, capability: str) -> tuple[int, int]:
        uses = successes = 0
        for run in self.runs:
            for s in run.adapter_stats:
                if capability in s.capabilities:
                    uses += 1
                    successes += int(s.contributed)
        return successes, uses

    def capability_effectiveness(self, capability: str, default: float = 0.5) -> float:
        successes, uses = self._capability_counts(capability)
        if uses == 0:
            return default
        return (successes + 1) / (uses + 2)

    def expected_cost(self, capability: str, default: float = 0.0) -> float:
        costs = [s.cost_tokens for run in self.runs for s in run.adapter_stats
                 if capability in s.capabilities and s.cost_tokens > 0]
        return sum(costs) / len(costs) if costs else default

    def planner_stats(self, domain: str | None = None) -> dict[str, float]:
        runs = [r for r in self.runs if domain is None or r.domain == domain]
        if not runs:
            return {"runs": 0}
        n = len(runs)
        return {
            "runs": n,
            "avg_iterations": sum(r.iterations for r in runs) / n,
            "avg_tokens": sum(r.cost.get("tokens", 0) for r in runs) / n,
            "insight_rate": sum(int(r.reached_insight) for r in runs) / n,
        }

    def calibration_summary(self) -> dict[str, float]:
        recs = [c for r in self.runs for c in r.calibration]
        if not recs:
            return {"records": 0}
        confident = [c for c in recs if c.predicted_confidence >= 0.7]
        return {
            "records": len(recs),
            "accuracy": sum(int(c.correct) for c in recs) / len(recs),
            "high_confidence_accuracy": (
                sum(int(c.correct) for c in confident) / len(confident) if confident else 0.0),
        }

    # -- persistence (JSONL of digests) -------------------------------------
    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            for run in self.runs:
                fh.write(run.model_dump_json() + "\n")
        return p

    def load(self, path: str | Path) -> None:
        self.runs = [RunDigest.model_validate_json(line)
                     for line in Path(path).read_text(encoding="utf-8").splitlines()
                     if line.strip()]

    def __len__(self) -> int:
        return len(self.runs)
