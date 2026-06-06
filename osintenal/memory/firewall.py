"""The evidence/strategy firewall (doc 06 Phase 4 exit criterion, doc 07 §"Tampering").

Two guarantees, enforced structurally rather than by convention:

1. **No evidence content crosses into Memory.** A ``RunDigest`` may carry only whitelisted
   strategy/metric fields; anything that looks like evidence payload (summaries, structured
   blobs, raw content, payload refs) is rejected at ingest.
2. **Memory has no write path to evidentiary history.** The priors object handed to agents
   exposes no mutation surface and holds no reference to a Ledger or InvestigationState, so it
   *cannot* rewrite recorded evidence or past confidence values.
"""

from __future__ import annotations

from .store import RunDigest

# Attribute/key names that would indicate leaked evidence content.
EVIDENCE_CONTENT_KEYS = frozenset({
    "summary", "payload", "payload_ref", "structured", "content", "raw",
    "supporting_evidence", "contradicting_evidence", "confidence_history", "weights",
})
# Mutation/handle names a read-only priors view must never expose.
FORBIDDEN_PRIORS_SURFACE = frozenset({
    "ledger", "state", "ingest", "append", "save", "write", "update_confidence",
    "add_evidence", "record",
})


class FirewallViolation(RuntimeError):
    """Raised when Memory would receive evidence content or gain a mutation path."""


def _scan(value, path: str = "") -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            if k in EVIDENCE_CONTENT_KEYS:
                raise FirewallViolation(
                    f"evidence-content key {k!r} present in digest at {path or '<root>'}")
            _scan(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _scan(v, f"{path}[{i}]")


def assert_strategy_only(digest: RunDigest) -> None:
    """Reject a digest that is not a RunDigest or that smuggles evidence content."""
    if not isinstance(digest, RunDigest):
        raise FirewallViolation(
            f"Memory accepts only RunDigest, got {type(digest).__name__}")
    _scan(digest.model_dump())


def assert_no_evidence_leak(digest: RunDigest, *forbidden_texts: str) -> None:
    """Assert none of the given evidence strings appear anywhere in the digest (test guard)."""
    blob = digest.model_dump_json()
    for text in forbidden_texts:
        if text and text in blob:
            raise FirewallViolation(f"evidence text leaked into digest: {text!r}")


def verify_read_only(priors: object) -> None:
    """Assert a priors object exposes no mutation surface / evidentiary handle."""
    for name in FORBIDDEN_PRIORS_SURFACE:
        if hasattr(priors, name):
            raise FirewallViolation(
                f"priors object exposes forbidden surface {name!r} — not firewall-safe")
