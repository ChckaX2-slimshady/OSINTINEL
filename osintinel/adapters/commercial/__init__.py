"""Supplemental, license-gated adapters (doc 05 §4b).

The brief's commercial resources — Maltego, Pipl, PimEyes, Recorded Future, Skopenow, DarkOwl,
Analyst's Notebook, and the rest — are modeled behind the *same* adapter interface but are
**never enabled implicitly**. They are quarantined here: the operator must supply credentials
*and* attest to authorized use before any call is permitted. This package ships the gating
mechanism and a representative stub, not live integrations.
"""

from .base import LicenseGatedAdapter, LicenseGateError
from .maltego import MaltegoAdapter

__all__ = ["LicenseGateError", "LicenseGatedAdapter", "MaltegoAdapter"]
