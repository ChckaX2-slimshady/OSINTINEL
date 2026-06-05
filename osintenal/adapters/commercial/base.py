"""License gate for supplemental adapters (doc 05 §4b, doc 07).

A licensed source may run only when BOTH are true:

1. credentials are present (an env var named by ``auth_env``), and
2. the operator has attested to authorized use (``OSINTENAL_ATTEST_AUTHORIZED=1``).

Otherwise every verb raises ``LicenseGateError`` — the source is invisible to selection, never
called implicitly. This keeps OSINTENAL lawful-by-default while leaving the door open to
operator-authorized commercial intelligence. Which licensed source was used is always recorded
in provenance.
"""

from __future__ import annotations

import os
from typing import Any

from ...core.schemas import CostEstimate
from ..base import ReferenceAdapter

ATTESTATION_ENV = "OSINTENAL_ATTEST_AUTHORIZED"


class LicenseGateError(RuntimeError):
    """Raised when a license-gated adapter is used without credentials + authorization."""


class LicenseGatedAdapter(ReferenceAdapter):
    """Base for commercial adapters. Subclasses set ``id``, ``capabilities``, ``auth_env``."""

    auth_env: str = "OSINTENAL_UNCONFIGURED"
    vendor: str = "unknown"
    default_cost = CostEstimate(tokens=300, money_usd=0.05, seconds=1.0, requests=1)

    def is_enabled(self) -> bool:
        return bool(os.environ.get(self.auth_env)) and os.environ.get(ATTESTATION_ENV) == "1"

    def require_enabled(self) -> None:
        if not os.environ.get(self.auth_env):
            raise LicenseGateError(
                f"{self.id}: missing credentials (set {self.auth_env}); licensed source "
                f"'{self.vendor}' stays disabled")
        if os.environ.get(ATTESTATION_ENV) != "1":
            raise LicenseGateError(
                f"{self.id}: authorized-use attestation required "
                f"(set {ATTESTATION_ENV}=1) before querying licensed source '{self.vendor}'")

    def search(self, capability: str, arguments: dict[str, Any]):  # noqa: D102
        self.require_enabled()
        raise NotImplementedError(f"{self.id} live integration not bundled")
