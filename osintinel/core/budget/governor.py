"""Budget Governor (doc 01 §1, doc 08 §5).

Tracks token, money, wall-clock, and request budgets and can preempt the loop. Phase 1
tracks tokens/requests/seconds/money; the same interface supports adaptive depth and
graceful degradation in later phases.
"""

from __future__ import annotations

import time

from ..schemas import BudgetSnapshot, Budgets


class BudgetExhausted(RuntimeError):
    """Raised when a budget dimension is exhausted."""

    def __init__(self, dimension: str) -> None:
        super().__init__(f"budget exhausted: {dimension}")
        self.dimension = dimension


class BudgetGovernor:
    def __init__(self, budgets: Budgets) -> None:
        self.budgets = budgets
        self.tokens_used = 0
        self.money_usd = 0.0
        self.requests = 0
        self._start = time.monotonic()

    @property
    def seconds(self) -> float:
        return time.monotonic() - self._start

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            tokens_used=self.tokens_used,
            money_usd=round(self.money_usd, 6),
            seconds=round(self.seconds, 3),
            requests=self.requests,
        )

    def charge(self, *, tokens: int = 0, money_usd: float = 0.0, requests: int = 0) -> None:
        self.tokens_used += tokens
        self.money_usd += money_usd
        self.requests += requests

    def exhausted_dimension(self) -> str | None:
        if self.tokens_used >= self.budgets.tokens:
            return "tokens"
        if self.money_usd >= self.budgets.money_usd:
            return "money_usd"
        if self.seconds >= self.budgets.seconds:
            return "seconds"
        if self.requests >= self.budgets.requests:
            return "requests"
        return None

    def is_exhausted(self) -> bool:
        return self.exhausted_dimension() is not None

    def check(self) -> None:
        dim = self.exhausted_dimension()
        if dim is not None:
            raise BudgetExhausted(dim)
