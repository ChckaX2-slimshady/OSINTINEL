"""Tool adapter framework (doc 05). Tools reach the world only through adapters."""

from .base import Adapter, RawHit
from .registry import AdapterRegistry
from .stub import StubEvidenceAdapter

__all__ = ["Adapter", "RawHit", "AdapterRegistry", "StubEvidenceAdapter"]
