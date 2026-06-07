"""Content-addressed artifact store (doc 05 §5.6) — the integral storage decision.

Heavy adapter artifacts (HTML snapshots, images, datasets) are stored here by the SHA-256 of
their bytes, **not** in the ledger. The ledger keeps only a lean ``raw_response`` event holding
the content hash, so:

* the knowledge graph/state stays small and replays byte-identically (doc 06 Phase 2), while
* the exact bytes remain recoverable by hash for audit, and
* identical fetches deduplicate automatically.

A ``cas:<sha256>`` ref is what an ``EvidenceObject.payload_ref`` carries; ``provenance.content_hash``
carries the same digest. Files are sharded by the first two hex chars to avoid huge directories.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

CAS_SCHEME = "cas:"


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ContentAddressedStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, digest: str) -> Path:
        return self.root / digest[:2] / digest[2:]

    def put(self, data: bytes) -> str:
        """Store bytes, returning their digest. Idempotent — re-storing dedupes."""
        digest = digest_bytes(data)
        path = self._path(digest)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return digest

    def has(self, digest: str) -> bool:
        return self._path(digest).exists()

    def get(self, digest: str) -> bytes:
        return self._path(digest).read_bytes()

    @staticmethod
    def ref(digest: str) -> str:
        """The ``cas:<digest>`` reference stored on an EvidenceObject."""
        return f"{CAS_SCHEME}{digest}"

    def resolve(self, ref: str) -> bytes:
        """Fetch bytes for a ``cas:<digest>`` ref (or a bare digest)."""
        digest = ref[len(CAS_SCHEME):] if ref.startswith(CAS_SCHEME) else ref
        return self.get(digest)
