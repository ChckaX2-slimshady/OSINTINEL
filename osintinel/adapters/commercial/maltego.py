"""Maltego — representative license-gated link-analysis adapter (doc 05 §4b).

Stub demonstrating the gating pattern only: declares capabilities and cost so the planner can
*reason about* it, but refuses to run unless the operator supplies a Maltego key and attests to
authorized use. No live transforms are bundled.
"""

from __future__ import annotations

from .base import LicenseGatedAdapter


class MaltegoAdapter(LicenseGatedAdapter):
    id = "maltego.transforms"
    vendor = "Maltego"
    capabilities = ["identity.profile", "infra.dns", "link.analysis"]
    auth_env = "MALTEGO_API_KEY"
    license_note = "Maltego commercial license; operator-authorized use only"
