"""GraphStore backends (doc 04 §1). Phase 2 ships the embedded in-memory store."""

from .memory import InMemoryGraphStore

__all__ = ["InMemoryGraphStore"]
